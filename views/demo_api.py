from __future__ import annotations

import re

from flask import Flask, jsonify, request
from sqlalchemy.orm import Session

from components.security.csrf import csrf_exempt
from database import Database
from services.notes_control_plane import ControlPlaneError, NotesControlPlane
from settings import config


_BEARER_RE = re.compile(r"^Bearer ([0-9a-f]{64})$")


def _session() -> Session:
    return Database.connect_database()


def _error(exc: ControlPlaneError):
    return jsonify({"error": exc.code, "message": str(exc)}), exc.status


def _require_enabled() -> None:
    if not config.NOTES_CONTROL_PLANE_ENABLED:
        raise ControlPlaneError(
            "Control plane отключён",
            status=503,
            code="service_unavailable",
        )


@csrf_exempt
def health():
    db = _session()
    try:
        result = NotesControlPlane.health(db)
        result = {
            **result,
            "api": "jsint-demo-v1",
            "project": "vanga",
        }
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
        channel = data.get("channel", "stable")

        if not isinstance(installation_id, str):
            raise ControlPlaneError("Invalid request")
        if version is not None and not isinstance(version, str):
            raise ControlPlaneError("Invalid request")
        if version_code is not None and (not isinstance(version_code, int) or isinstance(version_code, bool)):
            raise ControlPlaneError("Invalid request")
        if not isinstance(channel, str):
            raise ControlPlaneError("Invalid request")

        has_code = isinstance(activation_code, str) and activation_code != ""
        has_license = isinstance(license_token, str) and license_token != ""
        if has_code == has_license:
            raise ControlPlaneError("Передайте activation_code или license_token")

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

        return jsonify({
            **result,
            "api": "jsint-demo-v1",
            "project": "vanga",
        })
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

        installation_id = request.headers.get("X-JSInt-Installation", "").strip().lower()
        record = NotesControlPlane.authorize(db, installation_id, match.group(1))

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            raise ControlPlaneError("Invalid request")

        version = data.get("version")
        version_code = data.get("version_code")
        channel = data.get("channel", "stable")

        NotesControlPlane.touch_seen(
            db,
            record,
            action="vanga-demo-heartbeat",
            remote_addr=request.remote_addr,
            client_version=version if isinstance(version, str) else None,
            client_version_code=version_code if isinstance(version_code, int) and not isinstance(version_code, bool) else None,
            channel=channel if isinstance(channel, str) else None,
        )
        presence = NotesControlPlane.presence(record)
        return jsonify({
            "status": "ok",
            "api": "jsint-demo-v1",
            "project": "vanga",
            "installation_id": str(record.installation_id),
            "presence": presence["code"],
        })
    except ControlPlaneError as exc:
        return _error(exc)
    finally:
        db.close()


def install(app: Flask) -> None:
    prefix = "/api/demo/v1/vanga"
    app.add_url_rule(
        f"{prefix}/health",
        endpoint="demo_api.health",
        view_func=health,
        methods=["GET"],
    )
    app.add_url_rule(
        f"{prefix}/activate",
        endpoint="demo_api.activate",
        view_func=activate,
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/heartbeat",
        endpoint="demo_api.heartbeat",
        view_func=heartbeat,
        methods=["POST"],
    )
