from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
from sqlalchemy.orm import Session

from database import Database
from models.notification import AdminNotification, AdminNotificationPreferences
from models.web_push import AdminWebPushSubscription
from settings import config


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WebPushService:
    """Нативный Web Push для установленной PWA панели управления."""

    @staticmethod
    def _private_key_path() -> Path:
        configured = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY_PATH", "").strip()
        if configured:
            return Path(configured)
        if config.IS_PRODUCTION:
            return Path("/var/lib/jsint-site/webpush/vapid-private.pem")
        return Path(config.BASE_DIR) / "storage" / "webpush-vapid.pem"

    @classmethod
    def _ensure_vapid_key(cls) -> Path:
        path = cls._private_key_path()
        if path.exists():
            return path

        path.parent.mkdir(parents=True, exist_ok=True)
        private_key = ec.generate_private_key(ec.SECP256R1())
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(pem)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            if path.exists():
                temporary.unlink(missing_ok=True)
                return path
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        logger.info("Создан локальный VAPID-ключ Web Push: %s", path)
        return path

    @classmethod
    def public_key(cls) -> str:
        path = cls._ensure_vapid_key()
        private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        public_key = private_key.public_key()
        raw = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @staticmethod
    def _vapid_subject() -> str:
        configured = os.getenv("WEB_PUSH_VAPID_SUBJECT", "").strip()
        host = config.SITE_BASE_URL.split("://", 1)[-1].split("/", 1)[0]
        return configured or f"mailto:admin@{host}"

    @staticmethod
    def _validate_subscription(payload: dict) -> tuple[str, str, str]:
        if not isinstance(payload, dict):
            raise ValueError("Некорректная Web Push-подписка")
        endpoint = str(payload.get("endpoint") or "").strip()
        keys = payload.get("keys") if isinstance(payload.get("keys"), dict) else {}
        p256dh = str(keys.get("p256dh") or "").strip()
        auth = str(keys.get("auth") or "").strip()
        if not endpoint.startswith("https://") or not p256dh or not auth:
            raise ValueError("Браузер вернул неполную Web Push-подписку")
        if len(endpoint) > 4096 or len(p256dh) > 1024 or len(auth) > 512:
            raise ValueError("Web Push-подписка превышает допустимый размер")
        return endpoint, p256dh, auth

    @classmethod
    def subscribe(
        cls,
        db: Session,
        *,
        user_id: UUID,
        subscription: dict,
        user_agent: str | None,
        device_label: str | None,
    ) -> AdminWebPushSubscription:
        endpoint, p256dh, auth = cls._validate_subscription(subscription)
        record = (
            db.query(AdminWebPushSubscription)
            .filter(AdminWebPushSubscription.endpoint == endpoint)
            .first()
        )
        if record is None:
            record = AdminWebPushSubscription(
                user_id=user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
            )
        else:
            record.user_id = user_id
            record.p256dh = p256dh
            record.auth = auth
        record.user_agent = (user_agent or "")[:500] or None
        record.device_label = (device_label or "")[:120] or None
        record.enabled = True
        record.last_error = None
        record.last_error_at = None
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def unsubscribe(db: Session, *, user_id: UUID, endpoint: str) -> bool:
        record = (
            db.query(AdminWebPushSubscription)
            .filter(
                AdminWebPushSubscription.user_id == user_id,
                AdminWebPushSubscription.endpoint == endpoint,
            )
            .first()
        )
        if record is None:
            return False
        db.delete(record)
        db.flush()
        return True

    @classmethod
    def state(cls, db: Session, *, user_id: UUID) -> dict:
        subscriptions = (
            db.query(AdminWebPushSubscription)
            .filter(
                AdminWebPushSubscription.user_id == user_id,
                AdminWebPushSubscription.enabled.is_(True),
            )
            .order_by(AdminWebPushSubscription.updated_at.desc())
            .all()
        )
        return {
            "configured": True,
            "public_key": cls.public_key(),
            "subscriptions": [
                {
                    "id": str(item.id),
                    "device_label": item.device_label or "Устройство",
                    "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None,
                    "last_error": item.last_error,
                }
                for item in subscriptions
            ],
        }

    @staticmethod
    def _allowed_by_preferences(db: Session, notification: AdminNotification) -> bool:
        if bool((notification.details or {}).get("force_push")):
            return True
        preferences = (
            db.query(AdminNotificationPreferences)
            .filter(AdminNotificationPreferences.id == 1)
            .first()
        )
        if preferences is None:
            return True
        if notification.severity == "urgent" and preferences.notify_urgent:
            return True
        if notification.kind == "contact":
            return bool(preferences.notify_contact)
        if notification.kind == "diagnostic":
            return bool(preferences.notify_diagnostic)
        return False

    @classmethod
    def _send(cls, record: AdminWebPushSubscription, payload: dict) -> None:
        webpush(
            subscription_info={
                "endpoint": record.endpoint,
                "keys": {"p256dh": record.p256dh, "auth": record.auth},
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=str(cls._ensure_vapid_key()),
            vapid_claims={"sub": cls._vapid_subject()},
            ttl=300,
        )

    @classmethod
    def deliver_notification(
        cls,
        db: Session,
        notification: AdminNotification,
        *,
        user_id: UUID | None = None,
    ) -> dict:
        if not cls._allowed_by_preferences(db, notification):
            result = {"delivered": 0, "failed": 0, "expired": 0, "total": 0, "skipped": True}
            cls._record_delivery(db, notification, result)
            return result

        query = db.query(AdminWebPushSubscription).filter(
            AdminWebPushSubscription.enabled.is_(True)
        )
        if user_id is not None:
            query = query.filter(AdminWebPushSubscription.user_id == user_id)
        subscriptions = query.all()
        payload = {
            "title": notification.title,
            "body": notification.summary,
            "url": f"{config.ADMIN_ROUTE_PREFIX}/inbox/{notification.id}",
            "tag": f"admin-notification-{notification.id}",
            "severity": notification.severity,
        }

        delivered = 0
        failed = 0
        expired = 0
        for record in subscriptions:
            try:
                cls._send(record, payload)
            except WebPushException as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in {404, 410}:
                    db.delete(record)
                    expired += 1
                    continue
                record.last_error_at = _utcnow()
                record.last_error = str(exc)[:500]
                failed += 1
                logger.warning("Web Push не доставлен на %s: %s", record.id, exc)
                db.add(record)
            except Exception as exc:
                record.last_error_at = _utcnow()
                record.last_error = str(exc)[:500]
                failed += 1
                logger.exception("Ошибка Web Push для подписки %s", record.id)
                db.add(record)
            else:
                record.last_success_at = _utcnow()
                record.last_error_at = None
                record.last_error = None
                delivered += 1
                db.add(record)

        result = {
            "delivered": delivered,
            "failed": failed,
            "expired": expired,
            "total": len(subscriptions),
            "skipped": False,
        }
        cls._record_delivery(db, notification, result)
        return result

    @staticmethod
    def _record_delivery(db: Session, notification: AdminNotification, result: dict) -> None:
        if result["skipped"]:
            status, message = "skipped", "Отключено фильтром событий"
        elif result["delivered"]:
            status = "partial" if result["failed"] or result["expired"] else "sent"
            message = "Принято push-службой"
        elif result["failed"]:
            status, message = "failed", "Ошибка отправки; проверьте состояние устройств и журнал worker"
        else:
            status = "skipped"
            message = "Подписки устройств истекли" if result["expired"] else "Нет активных подписок устройств"
        # Keep Web Push independent of the legacy ntfy push_status fields.
        notification.details = {
            **(notification.details or {}),
            "web_push": {**result, "status": status, "message": message, "updated_at": _utcnow().isoformat()},
        }
        db.add(notification)
        db.commit()

    @classmethod
    def deliver_notification_by_id(cls, notification_id: UUID | str, *, user_id: UUID | None = None) -> dict:
        db = Database.connect_database()
        try:
            notification = (
                db.query(AdminNotification)
                .filter(AdminNotification.id == UUID(str(notification_id)))
                .first()
            )
            if notification is None:
                return {"delivered": 0, "failed": 0, "expired": 0, "total": 0, "skipped": False}
            try:
                return cls.deliver_notification(db, notification, user_id=user_id)
            except Exception:
                db.rollback()
                db.refresh(notification)
                notification.details = {
                    **(notification.details or {}),
                    "web_push": {"status": "failed", "message": "Ошибка обработки отправки; проверьте журнал worker", "updated_at": _utcnow().isoformat()},
                }
                db.commit()
                raise
        finally:
            db.close()
