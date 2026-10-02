from __future__ import annotations

from flask import render_template
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from models.control_plane import ReleaseRecord
from services.page import PageService
from services.public_seo import author_entity, breadcrumb_schema, share_image_url
from services.publication_channel import PublicationChannelService
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

        related_articles = PublicationChannelService.list_public(
            db_session,
            site_id=site_model.id,
            limit=3,
        )

        base_url = (site["base_url"] or "").rstrip("/")
        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "@id": f"{canonical_url}#software" if canonical_url else None,
                "name": "Workspace Organizer",
                "url": canonical_url,
                "applicationCategory": "BusinessApplication",
                "applicationSubCategory": "Self-hosted workspace",
                "operatingSystem": "Web",
                "softwareVersion": stable_version,
                "description": (
                    "Self-hosted рабочее пространство для заметок, задач, "
                    "файлов, Messenger и администрирования."
                ),
                "creator": author_entity(site),
                "featureList": [
                    "Заметки и документация",
                    "Задачи и проекты",
                    "Приватное файловое хранилище",
                    "Командная работа",
                    "Роли и права доступа",
                    "Подписанные обновления",
                ],
                "inLanguage": "ru-RU",
            },
            breadcrumb_schema(
                [
                    ("JSInteractive", f"{base_url}/" if base_url else "/"),
                    ("Проекты", f"{base_url}/#systems" if base_url else "/#systems"),
                    ("Workspace Organizer", canonical_url),
                ]
            ),
        ]

        return render_template(
            "public/workspace_organizer/index.html",
            site=site,
            stable_version=stable_version,
            seo_title=(
                "Workspace Organizer — self-hosted заметки, задачи и файлы "
                "| JSInteractive"
            ),
            seo_description=(
                "Workspace Organizer — self-hosted рабочее пространство для "
                "заметок, задач, файлов, Messenger, ролей и командной работы."
            ),
            canonical_url=canonical_url,
            seo_image_url=share_image_url(site),
            seo_image_alt="Workspace Organizer — self-hosted рабочее пространство",
            structured_data_items=structured_data_items,
            related_articles=related_articles,
        )
