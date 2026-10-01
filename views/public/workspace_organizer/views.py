from __future__ import annotations

from flask import render_template
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from models.control_plane import ReleaseRecord
from services.page import PageService
from services.site import SiteService


class WorkspaceOrganizerPromoPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session: Session):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        PageService.apply_public_navigation(
            db_session,
            site_model.id,
            site,
        )

        latest_release = (
            db_session.query(ReleaseRecord)
            .filter(
                ReleaseRecord.channel == "stable",
                ReleaseRecord.is_active.is_(True),
            )
            .order_by(ReleaseRecord.version_code.desc())
            .first()
        )

        stable_version = (
            latest_release.version if latest_release is not None else "1.0"
        )
        canonical_url = (
            f"{site['base_url']}/workspace-organizer"
            if site["base_url"]
            else None
        )

        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "name": "Workspace Organizer",
                "applicationCategory": "BusinessApplication",
                "operatingSystem": "Web",
                "softwareVersion": stable_version,
                "description": (
                    "Self-hosted рабочее пространство: заметки, задачи, "
                    "файлы, Messenger и администрирование."
                ),
            }
        ]

        return render_template(
            "public/workspace_organizer/index.html",
            site=site,
            stable_version=stable_version,
            seo_title=(
                "Workspace Organizer — self-hosted рабочее пространство "
                "| JSInteractive"
            ),
            seo_description=(
                "Workspace Organizer объединяет заметки, задачи, файлы, "
                "Messenger и администрирование в одном self-hosted контуре."
            ),
            canonical_url=canonical_url,
            structured_data_items=structured_data_items,
        )
