from __future__ import annotations

from flask import abort, render_template
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from services.page import PageService
from services.site import SiteService


PROJECTS = {
    "phoenixos": {
        "name": "PhoenixOS",
        "eyebrow": "Experimental OS",
        "tagline": "Экспериментальная операционная система с нуля для современных x86-64 ПК.",
        "description": (
            "Проектируется как полноценная платформа: ядро, драйверы, userspace, "
            "desktop, SDK, документация по портированию и системные приложения."
        ),
        "accent": "blue",
        "facts": [
            "x86-64 + UEFI",
            "QEMU / OVMF",
            "kernel + userspace",
            "drivers + desktop",
        ],
        "sections": [
            {
                "title": "Не только ядро",
                "text": (
                    "PhoenixOS развивается как целостная платформа, а не как "
                    "изолированный kernel-проект."
                ),
            },
            {
                "title": "Контролируемая матрица железа",
                "text": (
                    "На ранних релизах поддержка намеренно ограничивается, "
                    "чтобы сохранять воспроизводимость и стабильность."
                ),
            },
            {
                "title": "Портирование и SDK",
                "text": (
                    "В roadmap входят SDK, документация для добавления драйверов "
                    "и перенос прикладного ПО."
                ),
            },
        ],
    },
    "churchcms": {
        "name": "ChurchCMS",
        "eyebrow": "CMS / self-hosted",
        "tagline": "CMS для приходов, школ, благочиний, епархий и связанных организаций.",
        "description": (
            "Система ориентирована на самостоятельное развёртывание и поддержку "
            "связанных сайтов разных уровней — от отдельного прихода до епархии."
        ),
        "accent": "violet",
        "facts": [
            "PHP 8.3+",
            "self-hosted",
            "связанные сайты",
            "без внешних runtime-зависимостей",
        ],
        "sections": [
            {
                "title": "Разные типы сайтов",
                "text": (
                    "Один продукт должен покрывать приходские, школьные, "
                    "благочиннические и епархиальные сценарии."
                ),
            },
            {
                "title": "Связи между инстансами",
                "text": (
                    "Поддерживается модель самостоятельных сайтов с возможностью "
                    "связи с вышестоящими, нижестоящими и равноправными инстансами."
                ),
            },
            {
                "title": "Минимум инфраструктурного шума",
                "text": (
                    "Проект строится без внешних runtime-зависимостей и с фокусом "
                    "на предсказуемое самостоятельное размещение."
                ),
            },
        ],
    },
}


class ProjectPromoPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session: Session, slug: str):
        project = PROJECTS.get(slug)
        if project is None:
            abort(404)

        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        PageService.apply_public_navigation(
            db_session,
            site_model.id,
            site,
        )

        canonical_url = (
            f"{site['base_url']}/projects/{slug}"
            if site["base_url"]
            else None
        )

        return render_template(
            "public/projects/detail.html",
            site=site,
            project=project,
            project_slug=slug,
            seo_title=f"{project['name']} | JSInteractive",
            seo_description=project["tagline"],
            canonical_url=canonical_url,
        )
