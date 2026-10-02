from __future__ import annotations

from dataclasses import dataclass

from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.page import PageService
from services.public_seo import author_entity, breadcrumb_schema, share_image_url
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
    seo_title: str
    cta_url: str | None = None


CHURCHCMS_DETAIL = {
    "status": "Активная разработка · Parish MVP",
    "intro": (
        "ChurchCMS создаётся не как ещё один шаблон сайта для прихода, а как "
        "общая платформа для независимых церковных организаций — от небольшого "
        "прихода до епархии, митрополии или духовной школы."
    ),
    "profiles": (
        ("Приход / собор", "Публикации, страницы, расписание, люди, медиа, документы и контакты."),
        ("Монастырь", "Тот же общий runtime с собственной структурой, темой и набором модулей."),
        ("Благочиние", "Дерево приходов и организаций, scoped-доступ и агрегация разрешённых материалов."),
        ("Епархия / митрополия", "Независимые узлы могут связываться parent/child/peer без общего доступа к БД."),
        ("Духовная школа", "Профиль уже предусмотрен архитектурой; образовательный набор развивается отдельной фазой."),
        ("Смешанный профиль", "Церковные и образовательные возможности можно объединять в одной установке."),
    ),
    "evolution": (
        ("01", "Legacy-аудит", "Историческая VPDS CMS используется как источник данных, поведения и миграционных требований, но не как runtime-фундамент."),
        ("02", "Новый фундамент", "Система переписана вокруг PHP 8.3+, PDO, модулей, тем, миграций, API, security и собственного Admin Shell."),
        ("03", "Parish MVP", "Публикации, страницы, навигация, Media, галереи, SEO, редиректы, комментарии и операторские сценарии собраны в единый продукт."),
        ("04", "Федерация", "ChurchCMS-узлы получили организационную иерархию, pairing, scopes, remote projections и безопасную агрегацию данных."),
        ("05", "Интеграции", "Появилась provider-agnostic архитектура внешних каналов, inbox/outbox и встроенные Telegram, VK и MAX адаптеры."),
    ),
    "federation_points": (
        ("Самостоятельность", "Каждый сайт остаётся полноценным автономным ChurchCMS и не теряет данные при разрыве связи."),
        ("Явное доверие", "Связи parent/child/peer создаются через pairing, имеют scopes и могут быть отозваны."),
        ("Без общей БД", "Обмен идёт через versioned HTTP API и stable public ID, прямой доступ к чужой БД запрещён."),
        ("Сохранение источника", "Агрегированные публикации, события, расписание, документы и медиа сохраняют canonical owner и исходный URL."),
    ),
    "roadmap": (
        ("Parish MVP", "Завершить People/clergy, Worship, Events, версии документов и поиск."),
        ("Cathedral profile", "Министерства и отделы, святыни, святые, воскресная школа, библиотека и новые контентные потоки."),
        ("Education profile", "Программы, преподаватели, кафедры, приёмная кампания, расписания, раскрытие информации, Moodle/OJS интеграции."),
        ("Legacy migration", "Маппинг VPDS, перенос контента и медиа, сохранение URL через redirects и диагностический dry-run."),
        ("Pilot deployments", "Экспериментальные внедрения, сбор редакционного UX-фидбэка и усиление update/deploy пути."),
    ),
}


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
        seo_title="Vanga — ML-модель прогнозирования рейтинга фильмов | JSInteractive",
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
        seo_title="The-Game — браузерная JavaScript Canvas игра | JSInteractive",
    ),
    "churchcms": ProjectPromo(
        slug="churchcms",
        title="ChurchCMS",
        eyebrow="CMS / self-hosted / federation",
        summary=(
            "Модульная CMS-платформа для приходов, соборов, монастырей, "
            "благочиний, епархий, митрополий и духовных школ."
        ),
        description=(
            "Независимые ChurchCMS-сайты могут работать полностью автономно "
            "или объединяться в доверенную федерацию: обмениваться разрешёнными "
            "публикациями, событиями, расписанием, документами и медиа без общей БД."
        ),
        accent="purple",
        facts=("PHP 8.3+", "PostgreSQL / MySQL 8", "No Composer runtime", "Modular + federated"),
        capabilities=(
            ("Публикации и страницы", "Workflow публикаций, дерево страниц, навигация, ревизии, категории, теги и отложенная публикация."),
            ("Media, галереи и документы", "Безопасные загрузки, MIME sniffing, SHA-256, derivatives, HTTP Range, галереи и document-to-media связи."),
            ("Организационная структура", "Локальное дерево организаций, scoped RBAC и владельцы контента от прихода до митрополии."),
            ("Федерация ChurchCMS-узлов", "Pairing parent/child/peer, scopes, sync workers, tombstones, remote projections и агрегированные ленты."),
            ("Admin Shell и безопасность", "Единая админка, роли, CSRF/session foundation, audit/security log и понятные операторские сценарии."),
            ("Внешние каналы", "Provider-agnostic inbox/outbox, encrypted credentials и встроенные Telegram, VK и MAX адаптеры."),
            ("Установка, backup и updates", "Четырёхшаговый web-installer, healthcheck, резервные копии, staging, подпись пакетов и rollback."),
            ("SEO, API и синдикация", "Canonical/OG/Schema.org, sitemap/robots, redirects, versioned API, RSS и подключаемые каналы распространения."),
        ),
        cta_label="Обсудить проект",
        seo_title="ChurchCMS — модульная self-hosted CMS и федерация церковных сайтов | JSInteractive",
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

        canonical_url = (
            f"{site['base_url']}/projects/{project.slug}"
            if site["base_url"]
            else None
        )
        base_url = (site["base_url"] or "").rstrip("/")
        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "@id": f"{canonical_url}#software" if canonical_url else None,
                "name": project.title,
                "url": canonical_url,
                "description": project.summary,
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "Web",
                "creator": author_entity(site),
                "featureList": [title for title, _ in project.capabilities],
                "inLanguage": "ru-RU",
            },
            breadcrumb_schema(
                [
                    ("JSInteractive", f"{base_url}/" if base_url else "/"),
                    ("Проекты", f"{base_url}/#systems" if base_url else "/#systems"),
                    (project.title, canonical_url),
                ]
            ),
        ]

        return render_template(
            "public/projects/detail.html",
            site=site,
            project=project,
            seo_title=project.seo_title,
            seo_description=project.summary,
            canonical_url=canonical_url,
            seo_image_url=share_image_url(site),
            seo_image_alt=f"{project.title} — проект JSInteractive",
            structured_data_items=structured_data_items,
            project_detail=(
                CHURCHCMS_DETAIL if project.slug == "churchcms" else None
            ),
        )
