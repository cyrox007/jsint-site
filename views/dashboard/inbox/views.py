from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.contact import ContactMessage
from models.notification import AdminNotification, DiagnosticReport
from services.admin_notifications import AdminNotificationService, DiagnosticService


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


class InboxSettingsPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        return render_template(
            "dashboard/inbox/settings.html",
            push=AdminNotificationService.push_state(db_session),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        action = request.form.get("action", "save").strip()

        if action == "test":
            push = AdminNotificationService.push_state(db_session)
            if not push["enabled"]:
                flash("Сначала включите push и сохраните URL канала.", "error")
                return redirect(url_for("admin.inbox.settings"))

            notification = AdminNotificationService.create_test_push(db_session)
            db_session.commit()
            AdminNotificationService.enqueue_push(notification.id)
            flash("Тестовое push-уведомление поставлено в очередь.", "success")
            return redirect(url_for("admin.inbox.settings"))

        try:
            AdminNotificationService.update_preferences(
                db_session,
                push_enabled=request.form.get("push_enabled") == "1",
                push_url=request.form.get("push_url", ""),
                push_token=request.form.get("push_token"),
                clear_token=request.form.get("clear_token") == "1",
                notify_contact=request.form.get("notify_contact") == "1",
                notify_diagnostic=request.form.get("notify_diagnostic") == "1",
                notify_urgent=request.form.get("notify_urgent") == "1",
            )
            db_session.commit()
        except ValueError as exc:
            db_session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("admin.inbox.settings"))

        flash("Настройки уведомлений сохранены.", "success")
        return redirect(url_for("admin.inbox.settings"))


class InboxDetailPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, notification_id: UUID):
        notification = self._notification(db_session, notification_id)
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

        if notification.status == "new":
            now = datetime.now(timezone.utc)
            notification.status = "read"
            notification.read_at = now
            if isinstance(source, ContactMessage) and source.status == "new":
                source.status = "read"
                source.read_at = now
            db_session.commit()

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

        contact = None
        if notification.source_type == "contact":
            try:
                contact_id = UUID(notification.source_id)
            except ValueError:
                contact_id = None
            if contact_id is not None:
                contact = (
                    db_session.query(ContactMessage)
                    .filter(ContactMessage.id == contact_id)
                    .first()
                )

        if action == "read":
            now = datetime.now(timezone.utc)
            notification.status = "read"
            notification.read_at = now
            if contact is not None:
                contact.status = "read"
                contact.read_at = now
        elif action == "archive":
            now = notification.read_at or datetime.now(timezone.utc)
            notification.status = "archived"
            notification.read_at = now
            if contact is not None:
                contact.status = "archived"
                contact.read_at = contact.read_at or now
        elif action == "reopen":
            notification.status = "new"
            notification.read_at = None
            if contact is not None:
                contact.status = "new"
                contact.read_at = None
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
