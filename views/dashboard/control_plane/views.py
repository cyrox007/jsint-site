from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from config.notes_trust import LICENSE_TRUSTED_KEYS, UPDATE_TRUSTED_KEYS
from models.control_plane import LicenseRecord, ReleaseRecord
from services.notes_control_plane import ControlPlaneError, NotesControlPlane
from settings import config


def _parse_optional_datetime(value: str, field: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneError(f"Некорректное значение поля «{field}»") from exc
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


def _parse_required_positive_int(value: str, field: str) -> int:
    parsed = _parse_optional_positive_int(value, field)
    if parsed is None:
        raise ControlPlaneError(f"{field} обязателен")
    return parsed


def _license_id(value: str) -> str:
    value = value.strip()
    if value:
        return value
    return f"lic-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4)}"


def _features() -> list[str]:
    result: list[str] = []
    for item in request.form.getlist("features"):
        item = item.strip().lower()
        if item and item not in result:
            result.append(item)
    extra = request.form.get("features_extra", "").strip()
    if extra:
        for item in extra.split(","):
            item = item.strip().lower()
            if item and item not in result:
                result.append(item)
    return result


def _license_context(db_session: Session, *, tab: str = "registry", **extra):
    records = db_session.query(LicenseRecord).order_by(LicenseRecord.created_at.desc()).all()
    license_rows = [
        {
            "record": record,
            "presence": NotesControlPlane.presence(record),
            "activated": record.credential_hash is not None and record.activated_at is not None,
        }
        for record in records
    ]
    context = {
        "tab": tab,
        "licenses": records,
        "license_rows": license_rows,
        "control_plane": NotesControlPlane.health(db_session),
        "activation_code": None,
        "activation_installation": None,
        "issued_license_token": None,
        "license_key_ids": list(LICENSE_TRUSTED_KEYS.keys()),
        "local_signing_enabled": bool(config.NOTES_LOCAL_SIGNING_ENABLED),
        "signing_key_root": config.NOTES_SIGNING_KEY_ROOT,
        "stats": {
            "total": len(records),
            "active": sum(1 for row in records if row.status == "active"),
            "activated": sum(1 for row in license_rows if row["activated"]),
            "online": sum(1 for row in license_rows if row["presence"]["code"] == "online"),
        },
    }
    context.update(extra)
    return context


def _release_context(db_session: Session, *, tab: str = "registry", **extra):
    releases = db_session.query(ReleaseRecord).order_by(
        ReleaseRecord.version_code.desc(),
        ReleaseRecord.published_at.desc(),
    ).all()
    rows = []
    for record in releases:
        manifest = {}
        try:
            manifest = json.loads(record.manifest_bytes)
        except (TypeError, json.JSONDecodeError):
            pass
        signature_parts = record.signature.split(".")
        rows.append(
            {
                "record": record,
                "manifest": manifest,
                "key_id": signature_parts[1] if len(signature_parts) == 3 else "—",
            }
        )
    context = {
        "tab": tab,
        "releases": releases,
        "release_rows": rows,
        "update_key_ids": list(UPDATE_TRUSTED_KEYS.keys()),
        "local_signing_enabled": bool(config.NOTES_LOCAL_SIGNING_ENABLED),
        "signing_key_root": config.NOTES_SIGNING_KEY_ROOT,
        "release_storage_path": config.NOTES_RELEASE_STORAGE_PATH,
        "prepared_manifest": None,
        "prepared_package_path": None,
    }
    context.update(extra)
    return context


class LicenseListView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        tab = request.args.get("tab", "registry").strip()
        if tab not in {"registry", "issue", "import"}:
            tab = "registry"
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(db_session, tab=tab),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        """Совместимый импорт готового wo1 token."""
        try:
            record, activation_code = NotesControlPlane.register_license(
                db_session,
                request.form.get("signed_license", ""),
                updates_until=_parse_optional_datetime(
                    request.form.get("updates_until", ""),
                    "Доступ к обновлениям до",
                ),
                max_version=_parse_optional_positive_int(
                    request.form.get("max_version", ""),
                    "max_version",
                ),
            )
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/licenses.html",
                **_license_context(db_session, tab="import"),
            ), exc.status

        flash("Лицензия импортирована в реестр.", "success")
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(
                db_session,
                tab="registry",
                activation_code=activation_code,
                activation_installation=str(record.installation_id),
            ),
        )


class LicenseIssueView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        try:
            record, activation_code, token = NotesControlPlane.issue_license_local(
                db_session,
                private_key_path=request.form.get("private_key_path", "").strip(),
                key_id=request.form.get("key_id", "").strip(),
                installation_id=request.form.get("installation_id", "").strip(),
                license_id=_license_id(request.form.get("license_id", "")),
                edition=request.form.get("edition", "team").strip(),
                expires_at=_parse_optional_datetime(
                    request.form.get("expires_at", ""),
                    "Срок лицензии",
                ),
                not_before=_parse_optional_datetime(
                    request.form.get("not_before", ""),
                    "Начало действия",
                ),
                customer=request.form.get("customer", "").strip() or None,
                features=_features(),
                max_users=_parse_optional_positive_int(
                    request.form.get("max_users", ""),
                    "max_users",
                ),
                updates_until=_parse_optional_datetime(
                    request.form.get("updates_until", ""),
                    "Доступ к обновлениям до",
                ),
                max_version=_parse_optional_positive_int(
                    request.form.get("max_version", ""),
                    "max_version",
                ),
            )
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/licenses.html",
                **_license_context(db_session, tab="issue"),
            ), exc.status

        flash("Лицензия подписана, проверена и добавлена в реестр.", "success")
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(
                db_session,
                tab="registry",
                activation_code=activation_code,
                activation_installation=str(record.installation_id),
                issued_license_token=token,
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
        return redirect(url_for("admin.licenses.index", tab="registry"))


class LicenseActivationView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, license_row_id: UUID):
        record = db_session.query(LicenseRecord).filter(LicenseRecord.id == license_row_id).first()
        if record is None:
            abort(404)
        if record.status != "active":
            flash("Нельзя выпустить activation code для отозванной лицензии", "error")
            return redirect(url_for("admin.licenses.index", tab="registry"))
        activation_code = NotesControlPlane.reissue_activation(db_session, record)
        flash("Новый activation code создан. Предыдущий больше не действует.", "success")
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(
                db_session,
                tab="registry",
                activation_code=activation_code,
                activation_installation=str(record.installation_id),
            ),
        )


class ReleaseListView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        tab = request.args.get("tab", "registry").strip()
        if tab not in {"registry", "publish", "import"}:
            tab = "registry"
        return render_template(
            "dashboard/control_plane/releases.html",
            **_release_context(db_session, tab=tab),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        """Совместимый расширенный импорт manifest/signature."""
        try:
            record = NotesControlPlane.publish_release(
                db_session,
                manifest_bytes=request.form.get("manifest_bytes", ""),
                signature=request.form.get("signature", ""),
                package_path=request.form.get("package_path", ""),
            )
            flash(
                f"Релиз {record.version} ({record.channel}) импортирован и проверен",
                "success",
            )
            return redirect(url_for("admin.releases.index", tab="registry"))
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/releases.html",
                **_release_context(db_session, tab="import"),
            ), exc.status


class ReleasePublishView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        try:
            package_path = request.form.get("package_path", "").strip()
            version = request.form.get("version", "").strip()
            version_code = _parse_required_positive_int(
                request.form.get("version_code", ""),
                "version_code",
            )
            channel = request.form.get("channel", "stable").strip()
            source_commit = request.form.get("source_commit", "").strip()
            min_source_version_code = _parse_required_positive_int(
                request.form.get("min_source_version_code", ""),
                "min_source_version_code",
            )
            requires_php = request.form.get("requires_php", "").strip()
            mode = request.form.get("mode", "local").strip()

            if mode == "prepare_offline":
                manifest, resolved_path = NotesControlPlane.prepare_release_manifest(
                    package_path=package_path,
                    version=version,
                    version_code=version_code,
                    channel=channel,
                    source_commit=source_commit,
                    min_source_version_code=min_source_version_code,
                    requires_php=requires_php,
                )
                flash("Manifest собран и ZIP проверен. Подпишите exact bytes офлайн.", "success")
                return render_template(
                    "dashboard/control_plane/releases.html",
                    **_release_context(
                        db_session,
                        tab="publish",
                        prepared_manifest=manifest,
                        prepared_package_path=resolved_path,
                    ),
                )

            if mode != "local":
                raise ControlPlaneError("Некорректный режим публикации")

            record = NotesControlPlane.publish_release_local(
                db_session,
                package_path=package_path,
                version=version,
                version_code=version_code,
                channel=channel,
                source_commit=source_commit,
                min_source_version_code=min_source_version_code,
                requires_php=requires_php,
                private_key_path=request.form.get("private_key_path", "").strip(),
                key_id=request.form.get("key_id", "").strip(),
            )
            flash(
                f"Релиз {record.version} ({record.channel}) собран, подписан и опубликован",
                "success",
            )
            return redirect(url_for("admin.releases.index", tab="registry"))
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/releases.html",
                **_release_context(db_session, tab="publish"),
            ), exc.status


class ReleaseStatusView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, release_row_id: UUID):
        record = db_session.query(ReleaseRecord).filter(ReleaseRecord.id == release_row_id).first()
        if record is None:
            abort(404)
        status = request.form.get("status", "").strip()
        if status not in {"active", "inactive"}:
            flash("Некорректный статус релиза", "error")
            return redirect(url_for("admin.releases.index", tab="registry"))
        record.is_active = status == "active"
        db_session.add(record)
        db_session.commit()
        flash("Статус релиза обновлён", "success")
        return redirect(url_for("admin.releases.index", tab="registry"))
