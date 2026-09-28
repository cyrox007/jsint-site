from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from uuid import UUID

from flask import abort, flash, jsonify, redirect, render_template, request, session as flask_session, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from config.notes_trust import LICENSE_TRUSTED_KEYS, UPDATE_TRUSTED_KEYS
from models.control_plane import ControlPlaneAuditRecord, LicenseRecord, ReleaseRecord
from services.control_plane_audit import ControlPlaneAuditService
from services.github_release_automation import GitHubReleaseAutomation
from services.notes_control_plane import ControlPlaneError, NotesControlPlane
from settings import config


def _actor_user_id() -> UUID | None:
    raw = flask_session.get("user_id")
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _release_preflight(db_session: Session, prepared: dict) -> dict:
    head = (
        db_session.query(ReleaseRecord)
        .filter(
            ReleaseRecord.channel == prepared["channel"],
            ReleaseRecord.is_active.is_(True),
        )
        .order_by(ReleaseRecord.version_code.desc())
        .first()
    )
    warnings: list[str] = []
    if head is not None and prepared["version_code"] <= head.version_code:
        warnings.append(
            f"version_code {prepared['version_code']} не выше текущей головы канала {head.version_code}."
        )
    if prepared["channel"] == "stable":
        lowered = prepared["version"].lower()
        if any(marker in lowered for marker in ("alpha", "beta", "rc", "pre")):
            warnings.append("Название версии похоже на prerelease, хотя канал указан stable.")

    return {
        "head": head,
        "warnings": warnings,
        "ready": not warnings,
    }

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
        "prepared_release_preflight": None,
        "channel_state": ControlPlaneAuditService.channel_state(db_session),
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

        ControlPlaneAuditService.operator(
            db_session,
            actor_user_id=_actor_user_id(),
            action="license.import",
            target_type="license",
            target_id=record.license_id,
            installation_id=record.installation_id,
            license_id=record.license_id,
            details={"edition": record.edition},
        )
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

        ControlPlaneAuditService.operator(
            db_session,
            actor_user_id=_actor_user_id(),
            action="license.issue",
            target_type="license",
            target_id=record.license_id,
            installation_id=record.installation_id,
            license_id=record.license_id,
            details={"edition": record.edition},
        )
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
            new_status = request.form.get("status", "")
            NotesControlPlane.set_status(db_session, record, new_status)
            ControlPlaneAuditService.operator(
                db_session,
                actor_user_id=_actor_user_id(),
                action="license.status",
                target_type="license",
                target_id=record.license_id,
                installation_id=record.installation_id,
                license_id=record.license_id,
                details={"status": new_status},
            )
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
        ControlPlaneAuditService.operator(
            db_session,
            actor_user_id=_actor_user_id(),
            action="license.activation_reissued",
            target_type="license",
            target_id=record.license_id,
            installation_id=record.installation_id,
            license_id=record.license_id,
        )
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
            ControlPlaneAuditService.operator(
                db_session,
                actor_user_id=_actor_user_id(),
                action="release.publish",
                target_type="release",
                target_id=f"{record.channel}:{record.version_code}",
                release_id=record.id,
                details={
                    "channel": record.channel,
                    "version": record.version,
                    "version_code": record.version_code,
                    "source_commit": record.source_commit,
                    "package_sha256": record.package_sha256,
                },
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

        preflight = _release_preflight(db_session, prepared)
        ControlPlaneAuditService.operator(
            db_session,
            actor_user_id=_actor_user_id(),
            action="release.prepare",
            target_type="release",
            target_id=f"{prepared['channel']}:{prepared['version_code']}",
            details={
                "channel": prepared["channel"],
                "version": prepared["version"],
                "version_code": prepared["version_code"],
                "source_commit": prepared["source_commit"],
                "package_sha256": prepared["package_sha256"],
                "preflight_ready": preflight["ready"],
            },
        )
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
                        "preflight": {
                            "ready": preflight["ready"],
                            "warnings": preflight["warnings"],
                            "channel_head_version": preflight["head"].version if preflight["head"] else None,
                            "channel_head_version_code": preflight["head"].version_code if preflight["head"] else None,
                        },
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
                prepared_release_preflight=preflight,
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
        ControlPlaneAuditService.operator(
            db_session,
            actor_user_id=_actor_user_id(),
            action="release.status",
            target_type="release",
            target_id=f"{record.channel}:{record.version_code}",
            release_id=record.id,
            details={"status": status},
        )
        flash("Статус релиза обновлён", "success")
        return redirect(url_for("admin.releases.index", tab="registry"))


class ControlPlaneAuditView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        action = request.args.get("action", "").strip()[:96] or None
        outcome = request.args.get("outcome", "").strip()[:16] or None
        query = request.args.get("q", "").strip()[:160] or None
        records = ControlPlaneAuditService.list_records(
            db_session,
            action=action,
            outcome=outcome,
            query=query,
        )
        actions = [
            item[0]
            for item in (
                db_session.query(ControlPlaneAuditRecord.action)
                .distinct()
                .order_by(ControlPlaneAuditRecord.action)
                .all()
            )
        ]
        return render_template(
            "dashboard/control_plane/audit.html",
            records=records,
            actions=actions,
            selected_action=action or "",
            selected_outcome=outcome or "",
            query=query or "",
            retention_days=config.OPERATOR_AUDIT_RETENTION_DAYS,
        )
