from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from werkzeug.utils import secure_filename

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from sqlalchemy.orm import Session

from config.notes_trust import LICENSE_TRUSTED_KEYS, UPDATE_TRUSTED_KEYS
from models.control_plane import LicenseRecord, ReleaseRecord
from settings import config


_LICENSE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_UPDATE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
_VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")
_LICENSE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_EDITION_RE = re.compile(r"^[a-z][a-z0-9._-]{1,63}$")
_FEATURE_RE = re.compile(r"^[a-z][a-z0-9._-]{1,63}$")
_ARTIFACT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,200}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SIGNATURE_DOMAIN = b"WorkspaceOrganizerUpdateManifest/v1\n"
_CLOCK_SKEW_SECONDS = 300
_MAX_MANIFEST_BYTES = 131072
_MAX_PACKAGE_BYTES = 536870912
_PRESENCE_ONLINE_SECONDS = 15 * 60
_PRESENCE_RECENT_SECONDS = 24 * 60 * 60


class ControlPlaneError(RuntimeError):
    def __init__(self, message: str, *, status: int = 400, code: str = "invalid_request"):
        super().__init__(message)
        self.status = status
        self.code = code


def _b64url_decode(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ControlPlaneError("Некорректная base64url-строка")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise ControlPlaneError("Некорректная base64url-строка") from exc


def _public_key(registry: dict[str, str], key_id: str, pattern: re.Pattern[str]) -> bytes:
    if pattern.fullmatch(key_id) is None:
        raise ControlPlaneError("Некорректный идентификатор ключа подписи")
    encoded = registry.get(key_id)
    if encoded is None:
        raise ControlPlaneError("Неизвестный публичный ключ подписи", status=403, code="unknown_key")
    raw = _b64url_decode(encoded)
    if len(raw) != 32:
        raise ControlPlaneError("Некорректный публичный Ed25519 ключ", status=503, code="trust_misconfigured")
    return raw


def verify_license_token(
    token: str,
    expected_installation: str | None = None,
    trusted_keys: dict[str, str] | None = None,
    *,
    allow_not_yet_valid: bool = False,
) -> dict[str, Any]:
    token = token.strip()
    if not token or len(token) > 16384:
        raise ControlPlaneError("Некорректный лицензионный токен")
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "wo1":
        raise ControlPlaneError("Некорректный формат лицензионного токена")

    _, key_id, payload_encoded, signature_encoded = parts
    registry = LICENSE_TRUSTED_KEYS if trusted_keys is None else trusted_keys
    public_key = _public_key(registry, key_id, _LICENSE_KEY_RE)
    signature = _b64url_decode(signature_encoded)
    if len(signature) != 64:
        raise ControlPlaneError("Некорректная подпись лицензии")

    signed = f"wo1.{key_id}.{payload_encoded}".encode("ascii")
    try:
        VerifyKey(public_key).verify(signed, signature)
    except BadSignatureError as exc:
        raise ControlPlaneError("Подпись лицензии недействительна", status=403, code="invalid_signature") from exc

    try:
        payload = json.loads(_b64url_decode(payload_encoded).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControlPlaneError("Payload лицензии повреждён") from exc
    if not isinstance(payload, dict):
        raise ControlPlaneError("Payload лицензии должен быть JSON-объектом")

    for key in ("v", "license_id", "installation_id", "issued_at", "expires_at", "edition"):
        if key not in payload:
            raise ControlPlaneError(f"В лицензии отсутствует поле {key}")
    if payload["v"] != 1:
        raise ControlPlaneError("Версия лицензии не поддерживается")
    if not isinstance(payload["license_id"], str) or _LICENSE_ID_RE.fullmatch(payload["license_id"]) is None:
        raise ControlPlaneError("Некорректный license_id")
    try:
        installation = str(UUID(str(payload["installation_id"]))).lower()
    except ValueError as exc:
        raise ControlPlaneError("Некорректный installation_id") from exc
    if expected_installation is not None and not hmac.compare_digest(
        installation, str(UUID(expected_installation)).lower()
    ):
        raise ControlPlaneError("Лицензия выпущена для другой установки", status=403, code="wrong_installation")
    if not isinstance(payload["issued_at"], int) or payload["issued_at"] <= 0:
        raise ControlPlaneError("Некорректный issued_at")
    if payload["expires_at"] is not None and (
        not isinstance(payload["expires_at"], int) or payload["expires_at"] <= payload["issued_at"]
    ):
        raise ControlPlaneError("Некорректный expires_at")
    not_before = payload.get("not_before", payload["issued_at"])
    if not isinstance(not_before, int) or not_before <= 0:
        raise ControlPlaneError("Некорректный not_before")
    if not isinstance(payload["edition"], str) or _EDITION_RE.fullmatch(payload["edition"]) is None:
        raise ControlPlaneError("Некорректный edition")

    features = payload.get("features", [])
    if not isinstance(features, list) or any(
        not isinstance(item, str) or _FEATURE_RE.fullmatch(item) is None for item in features
    ) or len(set(features)) != len(features):
        raise ControlPlaneError("Некорректный список features")

    max_users = payload.get("max_users")
    if max_users is not None and (
        not isinstance(max_users, int) or max_users < 1 or max_users > 1_000_000
    ):
        raise ControlPlaneError("Некорректный max_users")

    now = int(datetime.now(timezone.utc).timestamp())
    if payload["issued_at"] > now + _CLOCK_SKEW_SECONDS:
        raise ControlPlaneError("Лицензия выпущена в будущем", status=403, code="not_yet_valid")
    if not allow_not_yet_valid and not_before > now + _CLOCK_SKEW_SECONDS:
        raise ControlPlaneError("Лицензия ещё не вступила в силу", status=403, code="not_yet_valid")
    if payload["expires_at"] is not None and now > payload["expires_at"] + _CLOCK_SKEW_SECONDS:
        raise ControlPlaneError("Срок действия лицензии истёк", status=403, code="expired")

    payload["installation_id"] = installation
    payload["_key_id"] = key_id
    return payload


def verify_update_manifest(
    manifest_bytes: str,
    signature_token: str,
    trusted_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    encoded = manifest_bytes.encode("utf-8")
    if not encoded or len(encoded) > _MAX_MANIFEST_BYTES:
        raise ControlPlaneError("Некорректный размер update manifest")

    parts = signature_token.strip().split(".")
    if len(parts) != 3 or parts[0] != "wou1":
        raise ControlPlaneError("Некорректный формат подписи update manifest")
    _, key_id, signature_encoded = parts
    registry = UPDATE_TRUSTED_KEYS if trusted_keys is None else trusted_keys
    public_key = _public_key(registry, key_id, _UPDATE_KEY_RE)
    signature = _b64url_decode(signature_encoded)
    if len(signature) != 64:
        raise ControlPlaneError("Некорректная подпись update manifest")

    try:
        VerifyKey(public_key).verify(_SIGNATURE_DOMAIN + encoded, signature)
    except BadSignatureError as exc:
        raise ControlPlaneError(
            "Подпись update manifest недействительна", status=403, code="invalid_signature"
        ) from exc

    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        raise ControlPlaneError("Update manifest не является корректным JSON") from exc
    if not isinstance(manifest, dict):
        raise ControlPlaneError("Update manifest должен быть JSON-объектом")

    required = (
        "schema", "product", "version", "version_code", "channel", "issued_at",
        "source_commit", "min_source_version_code", "requires_php", "package",
    )
    for key in required:
        if key not in manifest:
            raise ControlPlaneError(f"В update manifest отсутствует поле {key}")
    if manifest["schema"] != 1 or manifest["product"] != "workspace-organizer":
        raise ControlPlaneError("Неподдерживаемый update manifest")
    if not isinstance(manifest["version"], str) or _VERSION_RE.fullmatch(manifest["version"]) is None:
        raise ControlPlaneError("Некорректная версия релиза")
    if not isinstance(manifest["version_code"], int) or manifest["version_code"] <= 0:
        raise ControlPlaneError("Некорректный version_code")
    if manifest["channel"] not in {"alpha", "beta", "stable"}:
        raise ControlPlaneError("Некорректный release channel")
    if not isinstance(manifest["issued_at"], int) or manifest["issued_at"] <= 0:
        raise ControlPlaneError("Некорректный issued_at")
    now = int(datetime.now(timezone.utc).timestamp())
    if manifest["issued_at"] > now + _CLOCK_SKEW_SECONDS:
        raise ControlPlaneError("Update manifest выпущен в будущем")
    if not isinstance(manifest["source_commit"], str) or _SHA_RE.fullmatch(manifest["source_commit"]) is None:
        raise ControlPlaneError("Некорректный source_commit")
    if not isinstance(manifest["min_source_version_code"], int) or manifest["min_source_version_code"] <= 0:
        raise ControlPlaneError("Некорректный min_source_version_code")
    if not isinstance(manifest["requires_php"], str) or re.fullmatch(r"\d+\.\d+(?:\.\d+)?", manifest["requires_php"]) is None:
        raise ControlPlaneError("Некорректный requires_php")

    package = manifest["package"]
    if not isinstance(package, dict):
        raise ControlPlaneError("Некорректный package в update manifest")
    for key in ("filename", "sha256", "size", "format"):
        if key not in package:
            raise ControlPlaneError(f"В package отсутствует поле {key}")
    if not isinstance(package["filename"], str) or _ARTIFACT_RE.fullmatch(package["filename"]) is None or not package["filename"].endswith(".zip"):
        raise ControlPlaneError("Некорректное имя ZIP-пакета")
    if not isinstance(package["sha256"], str) or _SHA256_RE.fullmatch(package["sha256"]) is None:
        raise ControlPlaneError("Некорректный SHA-256 пакета")
    if not isinstance(package["size"], int) or package["size"] <= 0 or package["size"] > _MAX_PACKAGE_BYTES:
        raise ControlPlaneError("Некорректный размер пакета")
    if package["format"] != "zip":
        raise ControlPlaneError("Поддерживаются только ZIP-пакеты")

    manifest["_key_id"] = key_id
    return manifest


def _datetime_from_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def _build_release_manifest(
    *,
    package_path: str,
    version: str,
    version_code: int,
    channel: str,
    source_commit: str,
    min_source_version_code: int,
    requires_php: str,
) -> tuple[str, Path]:
    version = version.strip()
    channel = channel.strip().lower()
    source_commit = source_commit.strip().lower()
    requires_php = requires_php.strip()

    if _VERSION_RE.fullmatch(version) is None:
        raise ControlPlaneError("Некорректная версия релиза")
    if version_code <= 0:
        raise ControlPlaneError("version_code должен быть положительным")
    if channel not in {"alpha", "beta", "stable"}:
        raise ControlPlaneError("Канал должен быть alpha, beta или stable")
    if _SHA_RE.fullmatch(source_commit) is None:
        raise ControlPlaneError("source_commit должен быть полным 40-символьным Git SHA")
    if min_source_version_code <= 0:
        raise ControlPlaneError("min_source_version_code должен быть положительным")
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", requires_php) is None:
        raise ControlPlaneError("requires_php должен иметь вид 8.1 или 8.1.0")

    resolved = _resolve_package(package_path)
    size, sha256 = _hash_file(resolved)
    manifest = {
        "schema": 1,
        "product": "workspace-organizer",
        "version": version,
        "version_code": version_code,
        "channel": channel,
        "issued_at": int(datetime.now(timezone.utc).timestamp()),
        "source_commit": source_commit,
        "min_source_version_code": min_source_version_code,
        "requires_php": requires_php,
        "package": {
            "filename": resolved.name,
            "sha256": sha256,
            "size": size,
            "format": "zip",
        },
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
    ) + "\n"
    return manifest_bytes, resolved


def _release_storage_root() -> Path:
    root = Path(config.NOTES_RELEASE_STORAGE_PATH).expanduser()
    if not root.is_absolute():
        raise ControlPlaneError("NOTES_RELEASE_STORAGE_PATH должен быть абсолютным", status=503, code="storage_misconfigured")
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ControlPlaneError("Хранилище релизов недоступно", status=503, code="storage_unavailable") from exc
    app_root = Path(config.BASE_DIR).resolve()
    if resolved == app_root or app_root in resolved.parents:
        raise ControlPlaneError("Хранилище релизов должно быть вне application tree", status=503, code="storage_misconfigured")
    return resolved


def _resolve_package(path_value: str) -> Path:
    source = Path(path_value).expanduser()
    if not source.is_absolute() or source.is_symlink():
        raise ControlPlaneError("Package path должен быть абсолютным regular file без symlink")
    root = _release_storage_root()
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ControlPlaneError("Пакет должен находиться внутри NOTES_RELEASE_STORAGE_PATH") from exc
    if not resolved.is_file():
        raise ControlPlaneError("Release package не найден")
    return resolved


def _hash_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        magic = handle.read(4)
        if magic not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
            raise ControlPlaneError("Release package не является ZIP-архивом")
        digest.update(magic)
        size += len(magic)
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if size > _MAX_PACKAGE_BYTES:
                raise ControlPlaneError("Release package превышает допустимый размер")
    return size, digest.hexdigest()


class NotesControlPlane:
    @staticmethod
    def register_license(
        session: Session,
        signed_license: str,
        *,
        updates_until: datetime | None,
        max_version: int | None,
        updates_follow_license_expiry: bool = False,
    ) -> tuple[LicenseRecord, str]:
        payload = verify_license_token(signed_license, allow_not_yet_valid=True)
        license_expires_at = _datetime_from_timestamp(payload.get("expires_at"))
        if updates_follow_license_expiry:
            if license_expires_at is None:
                raise ControlPlaneError("Для обычного выпуска требуется срок действия лицензии")
            updates_until = license_expires_at
        if max_version is not None and max_version <= 0:
            raise ControlPlaneError("max_version должен быть положительным")
        if updates_until is not None and updates_until <= datetime.now(timezone.utc):
            raise ControlPlaneError("updates_until должен быть в будущем")

        installation_uuid = UUID(payload["installation_id"])
        record = (
            session.query(LicenseRecord)
            .filter(LicenseRecord.installation_id == installation_uuid)
            .first()
        )
        if record is None:
            record = LicenseRecord(installation_id=installation_uuid, license_id=payload["license_id"])
        elif record.license_id != payload["license_id"]:
            record.license_id = payload["license_id"]

        activation_code = secrets.token_hex(32)
        record.signed_license = signed_license.strip()
        record.key_id = payload["_key_id"]
        record.status = "active"
        record.updates_until = updates_until
        record.max_version = max_version
        record.customer = str(payload.get("customer") or "").strip() or None
        record.edition = payload["edition"]
        record.max_users = payload.get("max_users")
        record.features = list(payload.get("features", []))
        record.license_not_before = _datetime_from_timestamp(payload.get("not_before", payload["issued_at"]))
        record.license_expires_at = license_expires_at
        record.activation_hash = hashlib.sha256(activation_code.encode("ascii")).hexdigest()
        record.credential_hash = None
        record.activated_at = None

        session.add(record)
        session.commit()
        session.refresh(record)
        return record, activation_code

    @staticmethod
    def presence(record: LicenseRecord, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        if record.last_seen_at is None:
            return {
                "code": "unknown",
                "label": "Нет данных",
                "detail": "Клиент ещё не обращался к control plane.",
                "age_seconds": None,
            }

        last_seen = record.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        age = max(0, int((now - last_seen).total_seconds()))
        if age <= _PRESENCE_ONLINE_SECONDS:
            code, label = "online", "На связи"
        elif age <= _PRESENCE_RECENT_SECONDS:
            code, label = "recent", "Недавно"
        else:
            code, label = "offline", "Нет связи"
        return {
            "code": code,
            "label": label,
            "detail": "Статус основан на последнем исходящем запросе клиента к серверу.",
            "age_seconds": age,
        }

    @staticmethod
    def touch_seen(
        session: Session,
        record: LicenseRecord,
        *,
        action: str,
        remote_addr: str | None = None,
        client_version: str | None = None,
        client_version_code: int | None = None,
        channel: str | None = None,
    ) -> None:
        if len(action) > 64:
            action = action[:64]
        if remote_addr:
            remote_addr = remote_addr.strip()[:64] or None
        if client_version:
            client_version = client_version.strip()[:64] or None
        if channel and channel not in {"alpha", "beta", "stable"}:
            channel = None
        if client_version_code is not None and client_version_code <= 0:
            client_version_code = None

        record.last_seen_at = datetime.now(timezone.utc)
        record.last_seen_action = action
        if remote_addr:
            record.last_seen_ip = remote_addr
        if client_version:
            record.last_client_version = client_version
        if client_version_code is not None:
            record.last_client_version_code = client_version_code
        if channel:
            record.last_client_channel = channel
        session.add(record)
        session.commit()

    @staticmethod
    def reissue_activation(session: Session, record: LicenseRecord) -> str:
        activation_code = secrets.token_hex(32)
        record.activation_hash = hashlib.sha256(activation_code.encode("ascii")).hexdigest()
        record.credential_hash = None
        record.activated_at = None
        session.add(record)
        session.commit()
        return activation_code

    @staticmethod
    def set_status(session: Session, record: LicenseRecord, status: str) -> None:
        if status not in {"active", "revoked"}:
            raise ControlPlaneError("Некорректный статус лицензии")
        record.status = status
        if status == "revoked":
            record.credential_hash = None
            record.activation_hash = None
        session.add(record)
        session.commit()

    @staticmethod
    def _assert_entitled(record: LicenseRecord) -> None:
        if record.status != "active":
            raise ControlPlaneError("Доступ к обновлениям отозван", status=403, code="update_access_denied")
        now = datetime.now(timezone.utc)
        if record.updates_until is not None and now >= record.updates_until:
            raise ControlPlaneError("Срок доступа к обновлениям истёк", status=403, code="update_access_denied")
        verify_license_token(record.signed_license, str(record.installation_id))

    @classmethod
    def activate(
        cls,
        session: Session,
        installation_id: str,
        activation_code: str,
        *,
        remote_addr: str | None = None,
        client_version: str | None = None,
        client_version_code: int | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        try:
            installation_uuid = UUID(installation_id)
        except ValueError as exc:
            raise ControlPlaneError("Authentication required", status=401, code="authentication_required") from exc
        if re.fullmatch(r"[0-9a-f]{64}", activation_code) is None:
            raise ControlPlaneError("Authentication required", status=401, code="authentication_required")

        record = (
            session.query(LicenseRecord)
            .filter(LicenseRecord.installation_id == installation_uuid)
            .with_for_update()
            .first()
        )
        expected = hashlib.sha256(activation_code.encode("ascii")).hexdigest()
        if record is None or record.activation_hash is None or not hmac.compare_digest(record.activation_hash, expected):
            session.rollback()
            raise ControlPlaneError("Authentication required", status=401, code="authentication_required")

        cls._assert_entitled(record)
        credential = secrets.token_hex(32)
        record.activation_hash = None
        record.credential_hash = hashlib.sha256(credential.encode("ascii")).hexdigest()
        record.activated_at = datetime.now(timezone.utc)
        record.last_seen_at = record.activated_at
        record.last_seen_action = "activation"
        record.last_seen_ip = remote_addr.strip()[:64] if remote_addr else record.last_seen_ip
        if client_version:
            record.last_client_version = client_version.strip()[:64]
        if client_version_code is not None and client_version_code > 0:
            record.last_client_version_code = client_version_code
        if channel in {"alpha", "beta", "stable"}:
            record.last_client_channel = channel
        session.add(record)
        session.commit()

        return {
            "schema": 1,
            "installation_id": str(record.installation_id),
            "token": credential,
            "base_url": config.NOTES_UPDATE_BASE_URL,
        }

    @classmethod
    def authorize(cls, session: Session, installation_id: str, credential: str) -> LicenseRecord:
        try:
            installation_uuid = UUID(installation_id)
        except ValueError as exc:
            raise ControlPlaneError("Authentication required", status=401, code="authentication_required") from exc
        if re.fullmatch(r"[0-9a-f]{64}", credential) is None:
            raise ControlPlaneError("Authentication required", status=401, code="authentication_required")
        record = (
            session.query(LicenseRecord)
            .filter(LicenseRecord.installation_id == installation_uuid)
            .first()
        )
        expected = hashlib.sha256(credential.encode("ascii")).hexdigest()
        if record is None or record.credential_hash is None or not hmac.compare_digest(record.credential_hash, expected):
            raise ControlPlaneError("Authentication required", status=401, code="authentication_required")
        cls._assert_entitled(record)
        return record

    @staticmethod
    def store_release_upload(upload: Any) -> dict[str, Any]:
        original_name = str(getattr(upload, "filename", "") or "").strip()
        if not original_name or Path(original_name).suffix.lower() != ".zip":
            raise ControlPlaneError("Выберите ZIP-архив релиза")

        filename = secure_filename(Path(original_name).name)
        if not filename.lower().endswith(".zip"):
            filename = f"workspace-organizer-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.zip"

        root = _release_storage_root()
        max_bytes = min(config.NOTES_RELEASE_UPLOAD_MAX_BYTES, _MAX_PACKAGE_BYTES)
        suffix = secrets.token_hex(4)
        candidate = root / filename
        if candidate.exists():
            source = Path(filename)
            candidate = root / f"{source.stem}-{suffix}{source.suffix.lower()}"

        temporary = root / f".upload-{secrets.token_hex(12)}.part"
        digest = hashlib.sha256()
        size = 0

        try:
            stream = upload.stream
            with temporary.open("xb") as target:
                magic = stream.read(4)
                if magic not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
                    raise ControlPlaneError("Загруженный файл не является ZIP-архивом")
                target.write(magic)
                digest.update(magic)
                size = len(magic)

                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ControlPlaneError(
                            f"ZIP превышает допустимый размер {max_bytes // (1024 * 1024)} MiB",
                            status=413,
                            code="package_too_large",
                        )
                    target.write(chunk)
                    digest.update(chunk)

                target.flush()
                os.fsync(target.fileno())

            os.chmod(temporary, 0o640)
            temporary.replace(candidate)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return {
            "path": str(candidate),
            "filename": candidate.name,
            "original_filename": original_name,
            "size": size,
            "sha256": digest.hexdigest(),
        }

    @staticmethod
    def prepare_release_manifest(
        *,
        package_path: str,
        version: str,
        version_code: int,
        channel: str,
        source_commit: str,
        min_source_version_code: int,
        requires_php: str,
    ) -> tuple[str, str]:
        manifest_bytes, resolved = _build_release_manifest(
            package_path=package_path,
            version=version,
            version_code=version_code,
            channel=channel,
            source_commit=source_commit,
            min_source_version_code=min_source_version_code,
            requires_php=requires_php,
        )
        return manifest_bytes, str(resolved)

    @staticmethod
    def publish_release(
        session: Session,
        *,
        manifest_bytes: str,
        signature: str,
        package_path: str,
    ) -> ReleaseRecord:
        manifest = verify_update_manifest(manifest_bytes, signature)
        package = manifest["package"]
        resolved = _resolve_package(package_path)
        size, sha256 = _hash_file(resolved)
        if resolved.name != package["filename"] or size != package["size"] or not hmac.compare_digest(sha256, package["sha256"]):
            raise ControlPlaneError("ZIP-пакет не соответствует подписанному manifest")

        existing = (
            session.query(ReleaseRecord)
            .filter(
                ReleaseRecord.channel == manifest["channel"],
                ReleaseRecord.version_code == manifest["version_code"],
            )
            .first()
        )
        if existing is not None:
            raise ControlPlaneError("Релиз с таким channel/version_code уже зарегистрирован")

        name = f"release-{manifest['version_code']}"
        record = ReleaseRecord(
            channel=manifest["channel"],
            version=manifest["version"],
            version_code=manifest["version_code"],
            manifest_name=f"{name}.json",
            signature_name=f"{name}.sig",
            manifest_bytes=manifest_bytes,
            signature=signature.strip(),
            package_name=package["filename"],
            package_path=str(resolved),
            package_size=size,
            package_sha256=sha256,
            source_commit=manifest["source_commit"],
            is_active=True,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @classmethod
    def release_for_artifact(
        cls,
        session: Session,
        license_record: LicenseRecord,
        channel: str,
        name: str,
    ) -> ReleaseRecord:
        if channel not in {"alpha", "beta", "stable"} or _ARTIFACT_RE.fullmatch(name) is None:
            raise ControlPlaneError("Artifact not found", status=404, code="not_found")

        query = session.query(ReleaseRecord).filter(
            ReleaseRecord.channel == channel,
            ReleaseRecord.is_active.is_(True),
        )
        if license_record.max_version is not None:
            query = query.filter(ReleaseRecord.version_code <= license_record.max_version)

        if name == "feed.json":
            record = query.order_by(ReleaseRecord.version_code.desc()).first()
        else:
            record = query.filter(
                (ReleaseRecord.manifest_name == name)
                | (ReleaseRecord.signature_name == name)
                | (ReleaseRecord.package_name == name)
            ).first()
        if record is None:
            raise ControlPlaneError("Artifact not found", status=404, code="not_found")
        return record

    @staticmethod
    def verified_package_handle(record: ReleaseRecord):
        path = _resolve_package(record.package_path)
        handle = path.open("rb")
        digest = hashlib.sha256()
        size = 0
        try:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            if size != record.package_size or not hmac.compare_digest(digest.hexdigest(), record.package_sha256):
                raise ControlPlaneError("Целостность release package нарушена", status=503, code="service_unavailable")
            handle.seek(0)
            return handle
        except Exception:
            handle.close()
            raise

    @staticmethod
    def health(session: Session) -> dict[str, Any]:
        database_ok = False
        try:
            session.query(LicenseRecord.id).limit(1).all()
            database_ok = True
        except Exception:
            database_ok = False
        storage_ok = False
        try:
            root = _release_storage_root()
            storage_ok = root.is_dir()
        except ControlPlaneError:
            storage_ok = False
        trust_ok = bool(LICENSE_TRUSTED_KEYS) and bool(UPDATE_TRUSTED_KEYS)
        enabled = bool(config.NOTES_CONTROL_PLANE_ENABLED)
        return {
            "status": "ok" if enabled and database_ok and storage_ok and trust_ok else "degraded",
            "enabled": enabled,
            "database": database_ok,
            "release_storage": storage_ok,
            "license_trust": bool(LICENSE_TRUSTED_KEYS),
            "update_trust": bool(UPDATE_TRUSTED_KEYS),
        }
