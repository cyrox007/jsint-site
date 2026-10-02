from __future__ import annotations

from dataclasses import dataclass

from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.page import PageService
from services.site import SiteService


@dataclass(frozen=True)
class ProjectPromo:
    slug: str
    title: str
    eyebrow: str
    summary: str
    description: str
    accent: str
    facts: tuple[str, ...]
    capabilities: tuple[tuple[str, str], ...]
    cta_label: str
    cta_url: str | None = None


PROJECTS: dict[str, ProjectPromo] = {
    "vanga": ProjectPromo(
        slug="vanga",
        title="Vanga",
        eyebrow="ML / экспериментальный проект",
        summary="Экспериментальная модель прогнозирования рейтинга фильма до релиза.",
        description=(
            "Проект объединяет подготовку IMDb-данных, исторические признаки, "
            "CatBoost-модель и публичную демонстрацию на JSInteractive."
        ),
        accent="violet",
        facts=("Python", "CatBoost", "DuckDB", "Flask API"),
        capabilities=(
            ("Подготовка данных", "Обновление IMDb-наборов и построение локальной базы."),
            ("Temporal validation", "Проверка качества на более новых годах без случайного split."),
            ("Публичное демо", "Форма на JSInteractive работает через локальный API модели."),
            ("Безопасный retrain", "Новый артефакт публикуется отдельно от текущей рабочей модели."),
        ),
        cta_label="Открыть демо",
        cta_url="/demo/vanga",
    ),
    "the-game": ProjectPromo(
        slug="the-game",
        title="The-Game",
        eyebrow="Браузерная игра",
        summary="Браузерная игра на чистом JavaScript с Canvas-рендерингом.",
        description=(
            "Один из публичных проектов: объектно-ориентированная архитектура, "
            "Canvas-рендеринг игрового поля, сессионный счёт и адаптивный геймплей."
        ),
        accent="green",
        facts=("JavaScript", "Canvas", "OOP", "Responsive"),
        capabilities=(
            ("Canvas", "Игровое поле и визуальная часть рендерятся средствами Canvas API."),
            ("Архитектура", "Логика проекта разделена на объекты и игровые сущности."),
            ("Сессии", "Поддерживается подсчёт очков в рамках игровой сессии."),
            ("Адаптивность", "Интерфейс и геймплей рассчитаны на разные размеры экрана."),
        ),
        cta_label="Обсудить проект",
    ),
    "churchcms": ProjectPromo(
        slug="churchcms",
        title="ChurchCMS",
        eyebrow="CMS / self-hosted",
        summary="CMS для приходов, школ, благочиний, епархий и связанных организаций.",
        description=(
            "Self-hosted CMS с упором на независимое развёртывание, связанную "
            "структуру организаций и понятное управление содержимым."
        ),
        accent="purple",
        facts=("PHP 8.3+", "Self-hosted", "CMS", "No runtime deps"),
        capabilities=(
            ("Несколько типов сайтов", "Приходы, школы, благочиния, епархии и митрополии."),
            ("Связи между инстансами", "Поддерживаются вышестоящие, нижестоящие и равноправные сайты."),
            ("Самостоятельный runtime", "Минимум внешних зависимостей при эксплуатации."),
            ("Развитие по roadmap", "Функции добавляются небольшими совместимыми итерациями."),
        ),
        cta_label="Обсудить проект",
    ),
}


class ProjectPromoPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session, project_slug: str):
        project = PROJECTS.get(project_slug)
        if project is None:
            abort(404)

        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        PageService.apply_public_navigation(
            db_session,
            site_model.id,
            site,
        )

        return render_template(
            "public/projects/detail.html",
            site=site,
            project=project,
            seo_title=f"{project.title} — проект | JSInteractive",
            seo_description=project.summary,
            canonical_url=(
                f"{site['base_url']}/projects/{project.slug}"
                if site["base_url"]
                else None
            ),
        )
