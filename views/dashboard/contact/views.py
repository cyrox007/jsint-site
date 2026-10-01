from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.admin.site_context import resolve_admin_site
from components.auth.decorator import login_required, with_db_session
from models.contact import ContactMessage
from models.notification import AdminNotification


class ContactInboxPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        site = resolve_admin_site(db_session)
        status = request.args.get("status", "").strip()

        query = db_session.query(ContactMessage).filter(ContactMessage.site_id == site.id)
        if status in {"new", "read", "archived"}:
            query = query.filter(ContactMessage.status == status)

        messages = (
            query
            .order_by(ContactMessage.created_at.desc())
            .limit(200)
            .all()
        )
        counts = {
            state: db_session.query(ContactMessage)
            .filter(
                ContactMessage.site_id == site.id,
                ContactMessage.status == state,
            )
            .count()
            for state in ("new", "read", "archived")
        }

        return render_template(
            "dashboard/contact/index.html",
            messages=messages,
            counts=counts,
            selected_status=status,
            selected_site=site,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        site = resolve_admin_site(db_session)
        message = self._message(db_session, site.id)
        action = request.form.get("action", "").strip()

        if action == "read":
            message.status = "read"
            message.read_at = datetime.now(timezone.utc)
        elif action == "archive":
            message.status = "archived"
            if message.read_at is None:
                message.read_at = datetime.now(timezone.utc)
        elif action == "reopen":
            message.status = "new"
            message.read_at = None
        else:
            abort(400)

        notification = (
            db_session.query(AdminNotification)
            .filter(
                AdminNotification.source_type == "contact",
                AdminNotification.source_id == str(message.id),
            )
            .first()
        )
        if notification is not None:
            notification.status = message.status
            notification.read_at = message.read_at

        db_session.add(message)
        db_session.commit()
        flash("Статус обращения обновлён", "success")
        return redirect(url_for("admin.contact.index", site_id=site.id))

    @staticmethod
    def _message(db_session: Session, site_id: UUID) -> ContactMessage:
        try:
            message_id = UUID(request.form.get("message_id", "").strip())
        except (TypeError, ValueError):
            abort(400)

        message = (
            db_session.query(ContactMessage)
            .filter(
                ContactMessage.id == message_id,
                ContactMessage.site_id == site_id,
            )
            .first()
        )
        if message is None:
            abort(404)
        return message
