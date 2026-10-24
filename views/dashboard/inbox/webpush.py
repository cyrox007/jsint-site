from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from celery.exceptions import TimeoutError as CeleryTimeoutError
from flask import jsonify, request, session
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from services.admin_notifications import AdminNotificationService
from services.web_push import WebPushService


def _current_user_id() -> UUID:
    try:
        return UUID(str(session.get("user_id") or ""))
    except ValueError as exc:
        raise RuntimeError("Сессия администратора не содержит корректный ID пользователя") from exc


class WebPushStateApi(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        try:
            state = WebPushService.state(db_session, user_id=_current_user_id())
        except (OSError, ValueError, RuntimeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, **state})


class WebPushSubscribeApi(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        payload = request.get_json(silent=True) or {}
        try:
            record = WebPushService.subscribe(
                db_session,
                user_id=_current_user_id(),
                subscription=payload.get("subscription") or {},
                user_agent=request.headers.get("User-Agent"),
                device_label=str(payload.get("device_label") or "")[:120],
            )
            db_session.commit()
        except (ValueError, RuntimeError) as exc:
            db_session.rollback()
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "subscription_id": str(record.id)})


class WebPushUnsubscribeApi(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        payload = request.get_json(silent=True) or {}
        endpoint = str(payload.get("endpoint") or "").strip()
        if not endpoint:
            return jsonify({"ok": False, "error": "Не указан endpoint подписки"}), 400
        removed = WebPushService.unsubscribe(
            db_session,
            user_id=_current_user_id(),
            endpoint=endpoint,
        )
        db_session.commit()
        return jsonify({"ok": True, "removed": removed})


class WebPushTestApi(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        notification = AdminNotificationService.create_test_push(db_session)
        db_session.commit()
        try:
            delivery = AdminNotificationService.enqueue_push(
                notification.id,
                user_id=_current_user_id(),
                wait=True,
            )
            result = delivery["web_push"]
        except CeleryTimeoutError:
            return jsonify({
                "ok": False,
                "error": "Очередь не подтвердила отправку за 10 секунд. Проверьте Celery worker. Задача остаётся в очереди и может выполниться позже.",
            }), 504
        except Exception:
            return jsonify({"ok": False, "error": "Ошибка фоновой отправки. Проверьте журнал Celery worker."}), 502
        finally:
            # Техническая проверка не должна становиться задачей в очереди
            # внимания. Оставляем её только в истории уведомлений.
            db_session.refresh(notification)
            notification.status = "read"
            notification.read_at = datetime.now(timezone.utc)
            db_session.add(notification)
            db_session.commit()

        if result["total"] == 0:
            return jsonify({
                "ok": False,
                "error": "На этом аккаунте нет активных Web Push-подписок.",
                **result,
            }), 409
        if result["delivered"] == 0:
            return jsonify({
                "ok": False,
                "error": "Push не доставлен. Проверьте разрешение браузера и состояние устройства.",
                **result,
            }), 502
        return jsonify({"ok": True, "transport": delivery.get("transport", "celery"), **result})
