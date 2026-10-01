from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from nacl.exceptions import CryptoError
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random
from sqlalchemy.orm import Session
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from database import Database
from models.contact import ContactMessage
from models.control_plane import LicenseRecord
from models.notification import AdminNotification, AdminNotificationPreferences, DiagnosticReport
from settings import config


logger = logging.getLogger(__name__)

_ALLOWED_SEVERITIES = {"info", "warning", "urgent"}
_REASON_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MAX_METADATA_BYTES = 64 * 1024
_MAX_ZIP_ENTRIES = 1000
_MAX_UNCOMPRESSED_FACTOR = 10


class NotificationDeliveryError(RuntimeError):
    pass


class AdminNotificationService:
    PREFERENCES_ID = 1

    @staticmethod
    def _secret_box() -> SecretBox:
        key = hashlib.blake2b(
            config.SECRET_KEY.encode("utf-8"),
            digest_size=SecretBox.KEY_SIZE,
            person=b"jsint-push-token",
        ).digest()
        return SecretBox(key)

    @classmethod
    def _encrypt_token(cls, token: str) -> str:
        if not token:
            return ""
        encrypted = cls._secret_box().encrypt(
            token.encode("utf-8"),
            nacl_random(SecretBox.NONCE_SIZE),
        )
        return base64.urlsafe_b64encode(bytes(encrypted)).decode("ascii")

    @classmethod
    def _decrypt_token(cls, value: str | None) -> str:
        if not value:
            return ""
        try:
            payload = base64.urlsafe_b64decode(value.encode("ascii"))
            return cls._secret_box().decrypt(payload).decode("utf-8")
        except (ValueError, UnicodeDecodeError, CryptoError) as exc:
            raise NotificationDeliveryError(
                "Не удалось расшифровать token push-канала"
            ) from exc

    @staticmethod
    def _validate_push_url(value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        loopback = host in {"127.0.0.1", "localhost", "::1"}
        allowed_schemes = {"http", "https"} if loopback else {"https"}
        if (
            parsed.scheme not in allowed_schemes
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError(
                "Push URL должен быть HTTPS topic URL; HTTP разрешён только для localhost"
            )
        return value

    @classmethod
    def preferences(
        cls,
        db: Session,
        *,
        create: bool = True,
    ) -> AdminNotificationPreferences | None:
        record = (
            db.query(AdminNotificationPreferences)
            .filter(AdminNotificationPreferences.id == cls.PREFERENCES_ID)
            .first()
        )
        if record is not None or not create:
            return record

        record = AdminNotificationPreferences(
            id=cls.PREFERENCES_ID,
            push_enabled=bool(config.ADMIN_PUSH_URL),
            push_url=config.ADMIN_PUSH_URL or None,
            push_token_encrypted=(
                cls._encrypt_token(config.ADMIN_PUSH_TOKEN)
                if config.ADMIN_PUSH_TOKEN
                else None
            ),
            notify_contact=True,
            notify_diagnostic=True,
            notify_urgent=True,
        )
        db.add(record)
        db.flush()
        return record

    @classmethod
    def update_preferences(
        cls,
        db: Session,
        *,
        push_enabled: bool,
        push_url: str,
        push_token: str | None,
        clear_token: bool,
        notify_contact: bool,
        notify_diagnostic: bool,
        notify_urgent: bool,
    ) -> AdminNotificationPreferences:
        push_url = cls._validate_push_url(push_url)
        if push_enabled and not push_url:
            raise ValueError("Для включения push укажите URL темы ntfy")

        record = cls.preferences(db)
        assert record is not None
        record.push_enabled = bool(push_enabled)
        record.push_url = push_url or None
        record.notify_contact = bool(notify_contact)
        record.notify_diagnostic = bool(notify_diagnostic)
        record.notify_urgent = bool(notify_urgent)

        if clear_token:
            record.push_token_encrypted = None
        elif push_token is not None and push_token.strip():
            record.push_token_encrypted = cls._encrypt_token(push_token.strip())

        db.add(record)
        db.flush()
        return record

    @classmethod
    def push_state(cls, db: Session) -> dict:
        record = cls.preferences(db)
        assert record is not None
        return {
            "enabled": bool(record.push_enabled and record.push_url),
            "url": record.push_url or "",
            "token_configured": bool(record.push_token_encrypted),
            "notify_contact": bool(record.notify_contact),
            "notify_diagnostic": bool(record.notify_diagnostic),
            "notify_urgent": bool(record.notify_urgent),
        }

    @classmethod
    def _delivery_config(
        cls,
        db: Session,
        record: AdminNotification,
    ) -> tuple[str, str] | None:
        preferences = cls.preferences(db)
        assert preferences is not None

        if not preferences.push_enabled or not preferences.push_url:
            return None

        force = bool((record.details or {}).get("force_push"))
        allowed = force
        if record.severity == "urgent" and preferences.notify_urgent:
            allowed = True
        elif record.kind == "contact" and preferences.notify_contact:
            allowed = True
        elif record.kind == "diagnostic" and preferences.notify_diagnostic:
            allowed = True

        if not allowed:
            return None

        return (
            preferences.push_url,
            cls._decrypt_token(preferences.push_token_encrypted),
        )

    @staticmethod
    def create(
        db: Session,
        *,
        kind: str,
        title: str,
        summary: str,
        source_type: str,
        source_id: str,
        severity: str = "info",
        site_id=None,
        details: dict | None = None,
    ) -> AdminNotification:
        severity = severity if severity in _ALLOWED_SEVERITIES else "info"
        record = AdminNotification(
            site_id=site_id,
            kind=kind[:32],
            severity=severity,
            title=title[:200],
            summary=summary[:4000],
            source_type=source_type[:32],
            source_id=source_id[:64],
            status="new",
            details=details or {},
            push_status="pending",
        )
        db.add(record)
        db.flush()
        return record

    @classmethod
    def for_contact(
        cls,
        db: Session,
        message: ContactMessage,
    ) -> AdminNotification:
        subject = (message.subject or "").strip() or "Новое обращение"
        return cls.create(
            db,
            kind="contact",
            severity="info",
            title=subject,
            summary=f"{message.name} · новое сообщение с формы обратной связи",
            source_type="contact",
            source_id=str(message.id),
            site_id=message.site_id,
            details={
                "name": message.name,
                "reply_to": message.reply_to,
            },
        )

    @classmethod
    def for_diagnostic(
        cls,
        db: Session,
        report: DiagnosticReport,
    ) -> AdminNotification:
        customer = (report.customer or "").strip() or "неизвестный клиент"
        version = (report.client_version or "").strip() or "неизвестная версия"
        installation_tail = str(report.installation_id)[-8:]
        severity = (
            "urgent"
            if report.reason in {
                "startup_failed",
                "database_failed",
                "update_rollback",
                "storage_failed",
            }
            else "warning"
        )
        return cls.create(
            db,
            kind="diagnostic",
            severity=severity,
            title=f"Диагностика Notes · {customer}",
            summary=(
                f"Notes {version}, installation …{installation_tail}, "
                f"причина: {report.reason}"
            ),
            source_type="diagnostic",
            source_id=str(report.id),
            details={
                "installation_id": str(report.installation_id),
                "license_id": report.license_id,
                "customer": report.customer,
                "client_version": report.client_version,
                "reason": report.reason,
            },
        )

    @classmethod
    def create_test_push(cls, db: Session) -> AdminNotification:
        return cls.create(
            db,
            kind="system",
            severity="info",
            title="Тест push-уведомлений",
            summary="Канал уведомлений JSInteractive работает.",
            source_type="system",
            source_id=uuid4().hex,
            details={"force_push": True},
        )

    @staticmethod
    def enqueue_push(notification_id: UUID | str) -> None:
        try:
            from celery_app import celery_app

            celery_app.send_task(
                "tasks.system.deliver_admin_push",
                args=[str(notification_id)],
            )
        except Exception as exc:
            logger.warning(
                "Не удалось поставить push-уведомление %s в очередь: %s",
                notification_id,
                exc,
            )

    @staticmethod
    def _click_url(notification_id: UUID) -> str:
        return (
            f"{config.SITE_BASE_URL}{config.ADMIN_ROUTE_PREFIX}"
            f"/inbox/{notification_id}"
        )

    @classmethod
    def deliver_push(cls, notification_id: UUID | str) -> bool:
        try:
            notification_uuid = UUID(str(notification_id))
        except ValueError as exc:
            raise NotificationDeliveryError(
                "Некорректный ID уведомления"
            ) from exc

        db = Database.connect_database()
        try:
            record = (
                db.query(AdminNotification)
                .filter(AdminNotification.id == notification_uuid)
                .first()
            )
            if record is None:
                return False

            delivery = cls._delivery_config(db, record)
            if delivery is None:
                record.push_status = "skipped"
                record.push_error = None
                db.commit()
                return False

            push_url, push_token = delivery
            push_text = f"{record.title}\n{record.summary}"
            headers = {
                "Content-Type": "text/plain; charset=utf-8",
                "User-Agent": "jsint-site/admin-notifications",
                "X-Title": "JSInteractive",
                "X-Priority": {
                    "info": "default",
                    "warning": "high",
                    "urgent": "max",
                }.get(record.severity, "default"),
                "X-Tags": f"inbox,{record.kind}",
                "X-Click": cls._click_url(record.id),
            }
            if push_token:
                headers["Authorization"] = f"Bearer {push_token}"

            request = Request(
                push_url,
                data=push_text.encode("utf-8"),
                headers=headers,
                method="POST",
            )

            try:
                with urlopen(
                    request,
                    timeout=config.ADMIN_PUSH_TIMEOUT_SECONDS,
                ) as response:
                    status = int(getattr(response, "status", 200))
                    if status < 200 or status >= 300:
                        raise NotificationDeliveryError(
                            f"Push endpoint вернул HTTP {status}"
                        )
            except HTTPError as exc:
                raise NotificationDeliveryError(
                    f"Push endpoint вернул HTTP {exc.code}"
                ) from exc
            except (URLError, TimeoutError, OSError) as exc:
                raise NotificationDeliveryError(
                    "Push endpoint временно недоступен"
                ) from exc

            record.push_status = "sent"
            record.push_sent_at = datetime.now(timezone.utc)
            record.push_error = None
            db.commit()
            return True
        except Exception as exc:
            try:
                db.rollback()
                record = (
                    db.query(AdminNotification)
                    .filter(AdminNotification.id == notification_uuid)
                    .first()
                )
                if record is not None:
                    record.push_status = "failed"
                    record.push_error = str(exc)[:500]
                    db.commit()
            except Exception:
                db.rollback()
            raise
        finally:
            db.close()


class DiagnosticService:
    @staticmethod
    def _storage_root() -> Path:
        root = Path(config.NOTES_DIAGNOSTIC_STORAGE_PATH)
        root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(root, 0o750)
        except OSError:
            pass
        return root.resolve()

    @staticmethod
    def _validate_metadata(metadata: dict) -> dict:
        if not isinstance(metadata, dict):
            raise ValueError("metadata должна быть JSON-объектом")
        encoded = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
        if len(encoded) > _MAX_METADATA_BYTES:
            raise ValueError("metadata слишком велика")
        return metadata

    @classmethod
    def _store_package(
        cls,
        report_id: UUID,
        upload: FileStorage,
    ) -> tuple[str, str, int, str]:
        original_name = secure_filename(upload.filename or "diagnostic.zip")
        if not original_name.lower().endswith(".zip"):
            raise ValueError("Диагностический пакет должен быть ZIP-архивом")

        root = cls._storage_root()
        target = root / f"{report_id}.zip"
        temporary = root / f".{report_id}.{uuid4().hex[:8]}.part"

        digest = hashlib.sha256()
        size = 0
        max_bytes = config.NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES

        try:
            with temporary.open("xb") as handle:
                while True:
                    chunk = upload.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(
                            f"Диагностика превышает лимит {max_bytes // (1024 * 1024)} МБ"
                        )
                    handle.write(chunk)
                    digest.update(chunk)
                handle.flush()
                os.fsync(handle.fileno())

            if size < 22:
                raise ValueError("Диагностический ZIP пуст или повреждён")

            try:
                with zipfile.ZipFile(temporary, "r") as archive:
                    infos = archive.infolist()
                    if len(infos) > _MAX_ZIP_ENTRIES:
                        raise ValueError("В диагностическом ZIP слишком много файлов")

                    uncompressed = 0
                    for info in infos:
                        path = Path(info.filename.replace("\\", "/"))
                        if (
                            path.is_absolute()
                            or ".." in path.parts
                            or "\x00" in info.filename
                        ):
                            raise ValueError("Диагностический ZIP содержит небезопасный путь")
                        uncompressed += int(info.file_size)

                    if uncompressed > max_bytes * _MAX_UNCOMPRESSED_FACTOR:
                        raise ValueError("Диагностический ZIP имеет подозрительный размер распаковки")

                    bad_member = archive.testzip()
                    if bad_member is not None:
                        raise ValueError(
                            f"Диагностический ZIP повреждён: {bad_member[:120]}"
                        )
            except zipfile.BadZipFile as exc:
                raise ValueError("Диагностический пакет не является корректным ZIP") from exc

            os.chmod(temporary, 0o640)
            os.replace(temporary, target)
            return (
                original_name[:220],
                str(target),
                size,
                digest.hexdigest(),
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _read_diagnostic_preview(path: Path) -> dict:
        """Читает только небольшой whitelist безопасных JSON-файлов из ZIP."""
        allowed = {
            "manifest.json",
            "health.json",
            "maintenance.json",
            "hosting-profile.json",
            "privacy.json",
        }
        preview: dict = {}
        try:
            with zipfile.ZipFile(path, "r") as archive:
                by_name = {info.filename: info for info in archive.infolist()}
                for name in sorted(allowed):
                    info = by_name.get(name)
                    if info is None or info.file_size > 256 * 1024:
                        continue
                    try:
                        payload = json.loads(archive.read(info).decode("utf-8"))
                    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                        continue
                    if isinstance(payload, dict):
                        preview[name.removesuffix(".json")] = payload
        except (OSError, zipfile.BadZipFile):
            return {}
        return preview

    @classmethod
    def create_report(
        cls,
        db: Session,
        *,
        license_record: LicenseRecord,
        client_version: str | None,
        client_version_code: int | None,
        reason: str,
        summary: str,
        metadata: dict,
        upload: FileStorage | None,
    ) -> tuple[DiagnosticReport, AdminNotification]:
        reason = reason.strip().lower()
        if _REASON_RE.fullmatch(reason) is None:
            raise ValueError("Некорректная причина диагностики")

        summary = summary.replace("\x00", "").strip()
        if not summary:
            summary = "Диагностический отчёт отправлен администратором Notes"
        if len(summary) > 4000:
            raise ValueError("Слишком длинное описание диагностики")

        metadata = cls._validate_metadata(metadata)

        report = DiagnosticReport(
            installation_id=license_record.installation_id,
            license_id=license_record.license_id,
            customer=license_record.customer,
            client_version=client_version,
            client_version_code=client_version_code,
            reason=reason,
            summary=summary,
            metadata_json=metadata,
        )
        db.add(report)
        db.flush()

        stored_path: str | None = None
        try:
            if upload is not None:
                name, stored_path, size, sha256 = cls._store_package(
                    report.id,
                    upload,
                )
                report.package_name = name
                report.package_path = stored_path
                report.package_size = size
                report.package_sha256 = sha256
                preview = cls._read_diagnostic_preview(Path(stored_path))
                if preview:
                    report.metadata_json = {
                        **metadata,
                        "preview": preview,
                    }

            notification = AdminNotificationService.for_diagnostic(db, report)
            return report, notification
        except Exception:
            if stored_path:
                Path(stored_path).unlink(missing_ok=True)
            raise

    @classmethod
    def package_path(cls, report: DiagnosticReport) -> Path | None:
        if not report.package_path:
            return None
        root = cls._storage_root()
        candidate = Path(report.package_path).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise FileNotFoundError("Диагностический пакет недоступен")
        return candidate
