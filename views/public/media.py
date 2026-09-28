from __future__ import annotations

from uuid import UUID

from flask import Flask, abort, send_file

from components.auth.decorator import with_db_session
from services.media import MediaService


@with_db_session
def media_file(db_session, asset_id: UUID, filename: str):
    asset = MediaService.get_public(db_session, asset_id)
    if asset is None or filename != MediaService.public_filename(asset):
        abort(404)

    path = MediaService.absolute_path(asset)
    if not path.is_file():
        abort(404)

    response = send_file(
        path,
        mimetype=asset.mime_type,
        conditional=True,
        max_age=31536000,
        download_name=filename,
    )
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def install(app: Flask) -> None:
    app.add_url_rule(
        "/media/<uuid:asset_id>/<string:filename>",
        endpoint="public.media.file",
        view_func=media_file,
        methods=["GET"],
    )
