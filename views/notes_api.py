from __future__ import annotations

import re

from flask import Flask, Response, jsonify, request
from sqlalchemy.orm import Session

from components.security.csrf import csrf_exempt
from database import Database
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
        if request.content_length is not None and request.content_length > 1024:
            raise ControlPlaneError("Request too large", status=413)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ControlPlaneError("Invalid request")
        installation_id = data.get("installation_id")
        activation_code = data.get("activation_code")
        if not isinstance(installation_id, str) or not isinstance(activation_code, str):
            raise ControlPlaneError("Invalid request")
        return jsonify(NotesControlPlane.activate(db, installation_id.lower(), activation_code.lower()))
    except ControlPlaneError as exc:
        return _error(exc)
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
        release = NotesControlPlane.release_for_artifact(db, license_record, channel, name)

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
        f"{prefix}/<string:channel>/<string:name>",
        endpoint="notes_api.artifact",
        view_func=artifact,
        methods=["GET"],
    )
