from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from database import Database
from models.contact import ContactMessage
from models.control_plane import LicenseRecord
from models.notification import AdminNotification, DiagnosticReport
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
            push_status="pending" if config.ADMIN_PUSH_URL else "skipped",
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
            if report.reason in {"startup_failed", "database_failed", "update_rollback", "storage_failed"}
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

    @staticmethod
    def enqueue_push(notification_id: UUID | str) -> None:
        if not config.ADMIN_PUSH_URL:
            return
        try:
            from celery_app import celery_app

            celery_app.send_task(
                "tasks.system.deliver_admin_push",
                args=[str(notification_id)],
            )
        except Exception as exc:
            # Событие уже сохранено в БД. Недоступный broker не должен
            # ломать форму связи или загрузку диагностики.
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
            raise NotificationDeliveryError("Некорректный ID уведомления") from exc

        db = Database.connect_database()
        try:
            record = (
                db.query(AdminNotification)
                .filter(AdminNotification.id == notification_uuid)
                .first()
            )
            if record is None:
                return False

            if not config.ADMIN_PUSH_URL:
                record.push_status = "skipped"
                record.push_error = None
                db.commit()
                return False

            payload = {
                "title": record.title,
                "message": record.summary,
                "priority": {
                    "info": "default",
                    "warning": "high",
                    "urgent": "max",
                }.get(record.severity, "default"),
                "tags": ["inbox", record.kind],
                "click": cls._click_url(record.id),
            }
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "jsint-site/admin-notifications",
            }
            if config.ADMIN_PUSH_TOKEN:
                headers["Authorization"] = f"Bearer {config.ADMIN_PUSH_TOKEN}"

            request = Request(
                config.ADMIN_PUSH_URL,
                data=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
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
