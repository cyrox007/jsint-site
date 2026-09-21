# Production-аудит jsint-site

Дата: 2026-09-21.

## Состояние до аудита

Репозиторий был рабочим development-прототипом портфолио, но имел несколько блокеров прямой публикации в Internet: development Flask server, небезопасные fallback credentials, отсутствие CSRF, destructive GET routes, сломанная публичная регистрация, raw rich-text output, неработающие Vue-компоненты без Vue runtime, отсутствие deployment contract и CI.

## Что исправлено

### Authentication и CMS

- публичная регистрация удалена из маршрутов;
- legacy `run_admin.py` удалён;
- production CMS ограничена `ADMIN_EMAILS`;
- защищённые запросы повторно проверяют существование администратора;
- login использует Redis-backed rate limiting;
- session пересоздаётся после успешного входа;
- logout переведён на POST;
- все изменяющие формы защищены CSRF;
- удаление публикаций и категорий больше не работает через GET.

### Production config

- удалён fallback `SECRET_KEY`;
- production startup fail-closed при слабом/отсутствующем secret;
- обязательны `ALLOWED_HOSTS`, `ADMIN_EMAILS`, DB password и secure cookie;
- reverse-proxy mode включается явно;
- secrets вынесены во внешний environment file.

### Browser/security

- добавлены CSP, HSTS, frame denial, nosniff, Referrer-Policy и Permissions-Policy;
- административные ответы получают `Cache-Control: no-store`;
- rich text проходит allowlist sanitizer;
- raw `|safe` для публикаций убран;
- public article URL проверяет соответствие article/category;
- legacy public upload assets удалены.

### Data/CMS correctness

- server-side slug validation;
- опубликованный материал обязан иметь существующую категорию;
- запрещены циклические parent category;
- исправлена инвалидация category cache;
- обычный Redis cache деградирует без падения публичного сайта;
- production login rate limiter может fail-closed при `REDIS_REQUIRED=true`;
- согласованы relationships Publication/User/Category;
- Alembic использует общую metadata;
- DB password корректно URL-encode/escape для SQLAlchemy/Alembic.

### Публичный интерфейс

- Vue `router-link` без Vue заменён обычными Flask URL;
- несуществующие `TechBadge` заменены реальным HTML;
- исправлен mobile hero/header;
- удалён запрос отсутствующего `noise.png`;
- псевдо-live метрики заменены на описательные характеристики;
- Yandex Metrika стала optional config;
- favicon paths соответствуют существующим файлам;
- добавлены 404/413/500 pages.

### Runtime/deployment

- production entrypoint: Gunicorn + `wsgi.py`;
- добавлен `/healthz`;
- requirements сокращены до прямых используемых зависимостей;
- добавлены systemd/Nginx examples;
- deployment/backup/rollback описаны в `docs/DEPLOYMENT.md`.

### CI

GitHub Actions проверяет:

- Python 3.11 и 3.12;
- PostgreSQL 16;
- Redis 7;
- `compileall`;
- полный `alembic upgrade head`;
- production healthcheck;
- sanitizer/slug/CSRF unit tests;
- HTTP/security smoke.

## Что намеренно не копировалось из vrn-history

`vrn-history` использован как reference production-паттернов, но не как источник моделей:

- его multi-user/role модель не переносилась;
- Flask-WTF и его form layer не переносились;
- article revision/autosave/live-state не относятся к этому портфолио;
- media upload pipeline не переносился;
- models и migrations остаются собственными для `jsint-site`.

## Что остаётся сделать на самом VPS

Код не может самостоятельно:

1. создать DNS;
2. выпустить TLS certificate;
3. создать PostgreSQL role/database и production password;
4. заполнить `/etc/jsint-site.env`;
5. выбрать фактический `ADMIN_EMAILS`;
6. создать первого администратора;
7. настроить место хранения backup;
8. провести первый production browser smoke.

Порядок описан в `docs/DEPLOYMENT.md`.

## Отдельная следующая функция

Управление release artifacts Workspace Organizer из CMS портфолио не смешивается с этим hardening PR. После стабилизации сайта можно добавить раздел «Workspace Organizer → Релизы» как frontend к отдельному Notes Update Service. Private update signing key остаётся вне сайта.
