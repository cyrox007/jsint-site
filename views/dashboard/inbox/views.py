from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.contact import ContactMessage
from models.notification import AdminNotification, DiagnosticReport
from services.admin_notifications import DiagnosticService


_ALLOWED_STATUSES = {"new", "read", "archived"}
_ALLOWED_KINDS = {"contact", "diagnostic", "system"}


class InboxPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        status = request.args.get("status", "").strip()
        kind = request.args.get("kind", "").strip()

        query = db_session.query(AdminNotification)
        if status in _ALLOWED_STATUSES:
            query = query.filter(AdminNotification.status == status)
        if kind in _ALLOWED_KINDS:
            query = query.filter(AdminNotification.kind == kind)

        notifications = (
            query.order_by(AdminNotification.created_at.desc())
            .limit(300)
            .all()
        )

        counts = {
            state: db_session.query(AdminNotification)
            .filter(AdminNotification.status == state)
            .count()
            for state in ("new", "read", "archived")
        }
        kind_counts = {
            item: db_session.query(AdminNotification)
            .filter(AdminNotification.kind == item)
            .count()
            for item in ("contact", "diagnostic")
        }

        return render_template(
            "dashboard/inbox/index.html",
            notifications=notifications,
            counts=counts,
            kind_counts=kind_counts,
            selected_status=status,
            selected_kind=kind,
        )


class InboxDetailPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, notification_id: UUID):
        notification = self._notification(db_session, notification_id)
        if notification.status == "new":
            notification.status = "read"
            notification.read_at = datetime.now(timezone.utc)
            db_session.commit()

        source = None
        if notification.source_type == "contact":
            try:
                source_id = UUID(notification.source_id)
            except ValueError:
                source_id = None
            if source_id is not None:
                source = (
                    db_session.query(ContactMessage)
                    .filter(ContactMessage.id == source_id)
                    .first()
                )
        elif notification.source_type == "diagnostic":
            try:
                source_id = UUID(notification.source_id)
            except ValueError:
                source_id = None
            if source_id is not None:
                source = (
                    db_session.query(DiagnosticReport)
                    .filter(DiagnosticReport.id == source_id)
                    .first()
                )

        return render_template(
            "dashboard/inbox/detail.html",
            notification=notification,
            source=source,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, notification_id: UUID):
        notification = self._notification(db_session, notification_id)
        action = request.form.get("action", "").strip()

        if action == "read":
            notification.status = "read"
            notification.read_at = datetime.now(timezone.utc)
        elif action == "archive":
            notification.status = "archived"
            if notification.read_at is None:
                notification.read_at = datetime.now(timezone.utc)
        elif action == "reopen":
            notification.status = "new"
            notification.read_at = None
        else:
            abort(400)

        db_session.commit()
        flash("Статус входящего события обновлён", "success")
        return redirect(url_for("admin.inbox.detail", notification_id=notification.id))

    @staticmethod
    def _notification(db_session: Session, notification_id: UUID) -> AdminNotification:
        notification = (
            db_session.query(AdminNotification)
            .filter(AdminNotification.id == notification_id)
            .first()
        )
        if notification is None:
            abort(404)
        return notification


class DiagnosticDownload(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, notification_id: UUID):
        notification = InboxDetailPage._notification(db_session, notification_id)
        if notification.source_type != "diagnostic":
            abort(404)

        try:
            report_id = UUID(notification.source_id)
        except ValueError:
            abort(404)

        report = (
            db_session.query(DiagnosticReport)
            .filter(DiagnosticReport.id == report_id)
            .first()
        )
        if report is None:
            abort(404)

        try:
            package = DiagnosticService.package_path(report)
        except (OSError, FileNotFoundError):
            abort(404)
        if package is None:
            abort(404)

        return send_file(
            package,
            mimetype="application/zip",
            as_attachment=True,
            download_name=report.package_name or f"diagnostic-{report.id}.zip",
            conditional=True,
            etag=True,
            max_age=0,
        )
