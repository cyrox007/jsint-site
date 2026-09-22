from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.control_plane import LicenseRecord, ReleaseRecord
from services.notes_control_plane import ControlPlaneError, NotesControlPlane


def _parse_optional_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneError("Некорректная дата окончания доступа к обновлениям") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_optional_positive_int(value: str, field: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    if not value.isdigit() or int(value) <= 0:
        raise ControlPlaneError(f"{field} должен быть положительным целым числом")
    return int(value)


def _license_context(db_session: Session, **extra):
    records = db_session.query(LicenseRecord).order_by(LicenseRecord.created_at.desc()).all()
    context = {
        "licenses": records,
        "control_plane": NotesControlPlane.health(db_session),
        "activation_code": None,
        "activation_installation": None,
    }
    context.update(extra)
    return context


class LicenseListView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        return render_template("dashboard/control_plane/licenses.html", **_license_context(db_session))

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        try:
            record, activation_code = NotesControlPlane.register_license(
                db_session,
                request.form.get("signed_license", ""),
                updates_until=_parse_optional_datetime(request.form.get("updates_until", "")),
                max_version=_parse_optional_positive_int(request.form.get("max_version", ""), "max_version"),
            )
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            return render_template("dashboard/control_plane/licenses.html", **_license_context(db_session)), exc.status

        flash("Лицензия зарегистрирована. Скопируйте одноразовый activation code сейчас.", "success")
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(
                db_session,
                activation_code=activation_code,
                activation_installation=str(record.installation_id),
            ),
        )


class LicenseStatusView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, license_row_id: UUID):
        record = db_session.query(LicenseRecord).filter(LicenseRecord.id == license_row_id).first()
        if record is None:
            abort(404)
        try:
            NotesControlPlane.set_status(db_session, record, request.form.get("status", ""))
            flash("Статус лицензии обновлён", "success")
        except ControlPlaneError as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin.licenses.index"))


class LicenseActivationView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, license_row_id: UUID):
        record = db_session.query(LicenseRecord).filter(LicenseRecord.id == license_row_id).first()
        if record is None:
            abort(404)
        if record.status != "active":
            flash("Нельзя выпустить activation code для отозванной лицензии", "error")
            return redirect(url_for("admin.licenses.index"))
        activation_code = NotesControlPlane.reissue_activation(db_session, record)
        flash("Новый одноразовый activation code создан. Предыдущий больше не действует.", "success")
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(
                db_session,
                activation_code=activation_code,
                activation_installation=str(record.installation_id),
            ),
        )


class ReleaseListView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        releases = db_session.query(ReleaseRecord).order_by(ReleaseRecord.version_code.desc()).all()
        return render_template("dashboard/control_plane/releases.html", releases=releases)

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        try:
            record = NotesControlPlane.publish_release(
                db_session,
                manifest_bytes=request.form.get("manifest_bytes", ""),
                signature=request.form.get("signature", ""),
                package_path=request.form.get("package_path", ""),
            )
            flash(
                f"Релиз {record.version} ({record.channel}) зарегистрирован и проверен",
                "success",
            )
            return redirect(url_for("admin.releases.index"))
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            releases = db_session.query(ReleaseRecord).order_by(ReleaseRecord.version_code.desc()).all()
            return render_template("dashboard/control_plane/releases.html", releases=releases), exc.status
