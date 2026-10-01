from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID

from flask import Flask, Response, jsonify, request
from sqlalchemy.orm import Session

from components.security.csrf import csrf_exempt
from database import Database
from services.control_plane_audit import ControlPlaneAuditService
from services.admin_notifications import AdminNotificationService, DiagnosticService
from services.notes_control_plane import ControlPlaneError, NotesControlPlane
from settings import config


_BEARER_RE = re.compile(r"^Bearer ([0-9a-f]{64})$")


def _error(exc: ControlPlaneError):
    return jsonify({"error": exc.code}), exc.status


def _session() -> Session:
    return Database.connect_database()


def _require_enabled() -> None:
    if not config.NOTES_CONTROL_PLANE_ENABLED:
        raise ControlPlaneError(
            "Notes control plane отключён",
            status=503,
            code="service_unavailable",
        )


def _client_release_state() -> tuple[str | None, int | None]:
    version = request.headers.get("X-Notes-Version", "").strip()
    version_code_raw = request.headers.get("X-Notes-Version-Code", "").strip()

    if version and (len(version) > 64 or re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._+-]{0,63}", version) is None):
        raise ControlPlaneError("Invalid client version")
    if not version_code_raw:
        return (version or None, None)
    if re.fullmatch(r"[1-9][0-9]{0,9}", version_code_raw) is None:
        raise ControlPlaneError("Invalid client version code")

    version_code = int(version_code_raw)
    if version_code > 2_147_483_647:
        raise ControlPlaneError("Invalid client version code")
    return (version or None, version_code)




def _audit_machine_failure(
    db: Session,
    *,
    action: str,
    target_id: str | None,
    exc: ControlPlaneError,
) -> None:
    raw_installation = request.headers.get("X-Notes-Installation", "").strip().lower()
    try:
        installation_id = UUID(raw_installation)
    except ValueError:
        installation_id = None

    try:
        db.rollback()
        ControlPlaneAuditService.machine_failure(
            db,
            action=action,
            installation_id=installation_id,
            target_id=target_id,
            error_code=exc.code,
            http_status=exc.status,
        )
    except Exception:
        db.rollback()


@csrf_exempt
def health():
    db = _session()
    try:
        result = NotesControlPlane.health(db)
        return jsonify(result), (200 if result["status"] == "ok" else 503)
    finally:
        db.close()


@csrf_exempt
def activate():
    db = _session()
    try:
        _require_enabled()
        if request.content_length is not None and request.content_length > 24576:
            raise ControlPlaneError("Request too large", status=413)

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ControlPlaneError("Invalid request")

        installation_id = data.get("installation_id")
        activation_code = data.get("activation_code")
        license_token = data.get("license_token")
        version = data.get("version")
        version_code = data.get("version_code")
        channel = data.get("channel")

        if not isinstance(installation_id, str):
            raise ControlPlaneError("Invalid request")
        if version is not None and not isinstance(version, str):
            raise ControlPlaneError("Invalid request")
        if version_code is not None and (not isinstance(version_code, int) or isinstance(version_code, bool)):
            raise ControlPlaneError("Invalid request")
        if channel is not None and not isinstance(channel, str):
            raise ControlPlaneError("Invalid request")

        has_code = isinstance(activation_code, str) and activation_code != ""
        has_license = isinstance(license_token, str) and license_token != ""
        if has_code == has_license:
            raise ControlPlaneError("Invalid request")

        if has_license:
            result = NotesControlPlane.activate_with_license(
                db,
                installation_id.lower(),
                license_token,
                remote_addr=request.remote_addr,
                client_version=version,
                client_version_code=version_code,
                channel=channel,
            )
        else:
            result = NotesControlPlane.activate(
                db,
                installation_id.lower(),
                activation_code.lower(),
                remote_addr=request.remote_addr,
                client_version=version,
                client_version_code=version_code,
                channel=channel,
            )

        return jsonify(result)
    except ControlPlaneError as exc:
        return _error(exc)
    finally:
        db.close()



@csrf_exempt
def heartbeat():
    db = _session()
    try:
        _require_enabled()
        if request.content_length is not None and request.content_length > 4096:
            raise ControlPlaneError("Request too large", status=413)

        match = _BEARER_RE.fullmatch(request.headers.get("Authorization", "").strip())
        if match is None:
            raise ControlPlaneError(
                "Authentication required",
                status=401,
                code="authentication_required",
            )
        installation_id = request.headers.get("X-Notes-Installation", "").strip().lower()
        record = NotesControlPlane.authorize(db, installation_id, match.group(1))

        data = request.get_json(silent=True)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ControlPlaneError("Invalid request")

        version = data.get("version")
        version_code = data.get("version_code")
        channel = data.get("channel")
        if version is not None and not isinstance(version, str):
            raise ControlPlaneError("Invalid version")
        if version_code is not None and (not isinstance(version_code, int) or isinstance(version_code, bool)):
            raise ControlPlaneError("Invalid version_code")
        if channel is not None and not isinstance(channel, str):
            raise ControlPlaneError("Invalid channel")

        NotesControlPlane.touch_seen(
            db,
            record,
            action="heartbeat",
            remote_addr=request.remote_addr,
            client_version=version,
            client_version_code=version_code,
            channel=channel,
        )
        presence = NotesControlPlane.presence(record)
        return jsonify(
            {
                "status": "ok",
                "server_time": int(__import__("time").time()),
                "installation_id": str(record.installation_id),
                "presence": presence["code"],
            }
        )
    except ControlPlaneError as exc:
        return _error(exc)
    finally:
        db.close()


@csrf_exempt
def diagnostics():
    db = _session()
    report = None
    try:
        _require_enabled()
        max_bytes = config.NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES + 128 * 1024
        if request.content_length is not None and request.content_length > max_bytes:
            raise ControlPlaneError("Diagnostic package too large", status=413, code="package_too_large")

        match = _BEARER_RE.fullmatch(request.headers.get("Authorization", "").strip())
        if match is None:
            raise ControlPlaneError(
                "Authentication required",
                status=401,
                code="authentication_required",
            )

        installation_id = request.headers.get("X-Notes-Installation", "").strip().lower()
        license_record = NotesControlPlane.authorize(db, installation_id, match.group(1))
        client_version, client_version_code = _client_release_state()

        if request.mimetype == "application/json":
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                raise ControlPlaneError("Invalid diagnostic request")
            reason = data.get("reason", "manual")
            summary = data.get("summary", "")
            metadata = data.get("metadata", {})
            upload = None
        else:
            reason = request.form.get("reason", "manual")
            summary = request.form.get("summary", "")
            raw_metadata = request.form.get("metadata", "{}")
            try:
                metadata = json.loads(raw_metadata)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ControlPlaneError("Invalid diagnostic metadata") from exc
            upload = request.files.get("diagnostic")

        if not isinstance(reason, str) or not isinstance(summary, str) or not isinstance(metadata, dict):
            raise ControlPlaneError("Invalid diagnostic request")

        NotesControlPlane.touch_seen(
            db,
            license_record,
            action="diagnostic-upload",
            remote_addr=request.remote_addr,
            client_version=client_version,
            client_version_code=client_version_code,
            channel=request.headers.get("X-Notes-Channel", "").strip() or None,
        )

        try:
            report, notification = DiagnosticService.create_report(
                db,
                license_record=license_record,
                client_version=client_version,
                client_version_code=client_version_code,
                reason=reason,
                summary=summary,
                metadata=metadata,
                upload=upload,
            )
        except ValueError as exc:
            raise ControlPlaneError(str(exc), status=400, code="invalid_diagnostic") from exc

        db.commit()
        AdminNotificationService.enqueue_push(notification.id)

        return (
            jsonify(
                {
                    "status": "accepted",
                    "diagnostic_id": str(report.id),
                }
            ),
            202,
        )
    except ControlPlaneError as exc:
        db.rollback()
        if report is not None and report.package_path:
            try:
                Path(report.package_path).unlink(missing_ok=True)
            except OSError:
                pass
        _audit_machine_failure(
            db,
            action="machine.diagnostic_rejected",
            target_id=str(report.id) if report is not None else None,
            exc=exc,
        )
        return _error(exc)
    except Exception:
        db.rollback()
        if report is not None and report.package_path:
            try:
                Path(report.package_path).unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        db.close()


@csrf_exempt
def artifact(channel: str, name: str):
    db = _session()
    handle = None
    try:
        _require_enabled()
        match = _BEARER_RE.fullmatch(request.headers.get("Authorization", "").strip())
        if match is None:
            raise ControlPlaneError(
                "Authentication required",
                status=401,
                code="authentication_required",
            )
        installation_id = request.headers.get("X-Notes-Installation", "").strip().lower()
        license_record = NotesControlPlane.authorize(db, installation_id, match.group(1))
        client_version, client_version_code = _client_release_state()
        if name == "feed.json":
            seen_action = "update-feed"
        elif name.endswith(".json"):
            seen_action = "update-manifest"
        elif name.endswith(".sig"):
            seen_action = "update-signature"
        else:
            seen_action = "update-package"
        NotesControlPlane.touch_seen(
            db,
            license_record,
            action=seen_action,
            remote_addr=request.remote_addr,
            client_version=client_version,
            client_version_code=client_version_code,
            channel=channel,
        )
        release = NotesControlPlane.release_for_artifact(
            db,
            license_record,
            channel,
            name,
            client_version_code=client_version_code,
        )

        headers = {
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        }

        if name == "feed.json":
            return jsonify(
                {
                    "schema": 1,
                    "product": "workspace-organizer",
                    "channel": channel,
                    "manifest": release.manifest_name,
                    "signature": release.signature_name,
                }
            ), 200, headers

        if name == release.manifest_name:
            return Response(
                release.manifest_bytes,
                status=200,
                content_type="application/json",
                headers=headers,
            )

        if name == release.signature_name:
            return Response(
                release.signature,
                status=200,
                content_type="text/plain; charset=utf-8",
                headers=headers,
            )

        handle = NotesControlPlane.verified_package_handle(release)

        def stream():
            nonlocal handle
            try:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                if handle is not None:
                    handle.close()
                    handle = None

        response = Response(
            stream(),
            status=200,
            content_type="application/zip",
            direct_passthrough=True,
            headers=headers,
        )
        response.headers["Content-Length"] = str(release.package_size)
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{release.package_name}"'
        )
        return response
    except ControlPlaneError as exc:
        _audit_machine_failure(
            db,
            action="machine.artifact_denied",
            target_id=name,
            exc=exc,
        )
        if handle is not None:
            handle.close()
        return _error(exc)
    finally:
        db.close()


def install(app: Flask) -> None:
    prefix = config.NOTES_UPDATE_API_PREFIX
    app.add_url_rule(
        f"{prefix}/health",
        endpoint="notes_api.health",
        view_func=health,
        methods=["GET"],
    )
    app.add_url_rule(
        f"{prefix}/activate",
        endpoint="notes_api.activate",
        view_func=activate,
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/heartbeat",
        endpoint="notes_api.heartbeat",
        view_func=heartbeat,
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/diagnostics",
        endpoint="notes_api.diagnostics",
        view_func=diagnostics,
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/<string:channel>/<string:name>",
        endpoint="notes_api.artifact",
        view_func=artifact,
        methods=["GET"],
    )
