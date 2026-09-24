from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from config.notes_trust import LICENSE_TRUSTED_KEYS, UPDATE_TRUSTED_KEYS
from models.control_plane import LicenseRecord, ReleaseRecord
from services.github_release_automation import GitHubReleaseAutomation
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
        "license_trusted_keys": LICENSE_TRUSTED_KEYS,
        "suggested_license_id": _license_id(""),
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
        "update_trusted_keys": UPDATE_TRUSTED_KEYS,
        "operator_signer_url": config.NOTES_OPERATOR_SIGNER_URL,
        "release_storage_path": config.NOTES_RELEASE_STORAGE_PATH,
        "release_upload_max_bytes": config.NOTES_RELEASE_UPLOAD_MAX_BYTES,
        "release_github_repository": config.NOTES_RELEASE_GITHUB_REPOSITORY,
        "prepared_manifest": None,
        "prepared_package_path": None,
        "prepared_release_source": None,
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
        """Регистрирует лицензию, которую браузер оператора подписал выбранным ключом."""
        signed_license = request.form.get("signed_license", "").strip()
        try:
            record, activation_code = NotesControlPlane.register_license(
                db_session,
                signed_license,
                updates_until=None,
                max_version=None,
                updates_follow_license_expiry=True,
            )
        except ControlPlaneError as exc:
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/licenses.html",
                **_license_context(db_session, tab="issue"),
            ), exc.status

        flash("Лицензия подписана на ПК оператора, проверена сервером и добавлена в реестр.", "success")
        return render_template(
            "dashboard/control_plane/licenses.html",
            **_license_context(
                db_session,
                tab="registry",
                activation_code=activation_code,
                activation_installation=str(record.installation_id),
                issued_license_token=signed_license,
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
        if tab not in {"registry", "publish"}:
            tab = "registry"
        return render_template(
            "dashboard/control_plane/releases.html",
            **_release_context(db_session, tab=tab),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        """Публикует релиз, сохраняя точные байты manifest при JSON-запросе."""
        json_mode = request.is_json
        if json_mode:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify(
                    {
                        "status": "error",
                        "code": "invalid_request",
                        "message": "Ожидался JSON-объект с данными релиза.",
                    }
                ), 400
            manifest_bytes = str(payload.get("manifest_bytes", ""))
            signature = str(payload.get("signature", ""))
            package_path = str(payload.get("package_path", ""))
        else:
            manifest_bytes = request.form.get("manifest_bytes", "")
            signature = request.form.get("signature", "")
            package_path = request.form.get("package_path", "")

        try:
            record = NotesControlPlane.publish_release(
                db_session,
                manifest_bytes=manifest_bytes,
                signature=signature,
                package_path=package_path,
            )
            if json_mode:
                return jsonify(
                    {
                        "status": "ok",
                        "release": {
                            "version": record.version,
                            "channel": record.channel,
                        },
                    }
                )
            flash(
                f"Релиз {record.version} ({record.channel}) импортирован и проверен",
                "success",
            )
            return redirect(url_for("admin.releases.index", tab="registry"))
        except ControlPlaneError as exc:
            if json_mode:
                return jsonify(
                    {
                        "status": "error",
                        "code": exc.code,
                        "message": str(exc),
                    }
                ), exc.status
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/releases.html",
                **_release_context(db_session, tab="publish"),
            ), exc.status


class ReleaseGitHubPrepareView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        """Автоматически готовит manifest из официального GitHub Release."""
        tag = request.form.get("tag", "").strip()
        json_mode = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        try:
            prepared = GitHubReleaseAutomation.prepare(db_session, tag=tag)
        except ControlPlaneError as exc:
            if json_mode:
                return jsonify(
                    {
                        "status": "error",
                        "code": exc.code,
                        "message": str(exc),
                    }
                ), exc.status
            flash(str(exc), "error")
            return render_template(
                "dashboard/control_plane/releases.html",
                **_release_context(db_session, tab="publish"),
            ), exc.status

        if json_mode:
            return jsonify(
                {
                    "status": "ok",
                    "release": {
                        "manifest": prepared["manifest"],
                        "package_path": prepared["package_path"],
                        "tag": prepared["tag"],
                        "version": prepared["version"],
                        "version_code": prepared["version_code"],
                        "channel": prepared["channel"],
                        "source_commit": prepared["source_commit"],
                        "package_sha256": prepared["package_sha256"],
                    },
                }
            )

        flash(
            f"GitHub Release {prepared['tag']} проверен. Выберите update key и опубликуйте релиз.",
            "success",
        )
        return render_template(
            "dashboard/control_plane/releases.html",
            **_release_context(
                db_session,
                tab="publish",
                prepared_manifest=prepared["manifest"],
                prepared_package_path=prepared["package_path"],
                prepared_release_source=prepared,
            ),
        )


class ReleaseUploadView(MethodView):
    @login_required
    def post(self):
        # Flask 3.1 позволяет поднять лимит только для этого конкретного request.
        # Остальные формы приложения по-прежнему ограничены общим MAX_CONTENT_LENGTH.
        request.max_content_length = config.NOTES_RELEASE_UPLOAD_MAX_BYTES + (1024 * 1024)

        upload = request.files.get("package")
        if upload is None:
            return jsonify(
                {
                    "status": "error",
                    "code": "package_required",
                    "message": "Выберите ZIP-архив релиза.",
                }
            ), 400

        try:
            stored = NotesControlPlane.store_release_upload(upload)
        except ControlPlaneError as exc:
            return jsonify(
                {
                    "status": "error",
                    "code": exc.code,
                    "message": str(exc),
                }
            ), exc.status

        return jsonify({"status": "ok", "package": stored})


class ReleasePublishView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session):
        """Проверяет ZIP и готовит exact manifest для подписи на ПК оператора."""
        try:
            package_path = request.form.get("package_path", "").strip()
            manifest, resolved_path = NotesControlPlane.prepare_release_manifest(
                package_path=package_path,
                version=request.form.get("version", "").strip(),
                version_code=_parse_required_positive_int(
                    request.form.get("version_code", ""),
                    "version_code",
                ),
                channel=request.form.get("channel", "stable").strip(),
                source_commit=request.form.get("source_commit", "").strip(),
                min_source_version_code=_parse_required_positive_int(
                    request.form.get("min_source_version_code", ""),
                    "min_source_version_code",
                ),
                requires_php=request.form.get("requires_php", "").strip(),
            )
            flash(
                "ZIP проверен, SHA-256 рассчитан, manifest готов. Теперь подпишите его локальным signer.",
                "success",
            )
            return render_template(
                "dashboard/control_plane/releases.html",
                **_release_context(
                    db_session,
                    tab="publish",
                    prepared_manifest=manifest,
                    prepared_package_path=resolved_path,
                ),
            )
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
