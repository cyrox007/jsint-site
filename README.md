# jsint-site — +УЛЬТРА

Персональный сайт-портфолио и небольшая CMS на Flask.

Проект использует:

- Python 3.11+;
- Flask 3;
- PostgreSQL;
- Redis;
- SQLAlchemy 2;
- Alembic;
- Gunicorn в production;
- Nginx как reverse proxy.

## Быстрый локальный запуск

Создайте виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Создайте локальный `.env` на основе `default.env`. Для development можно использовать:

```env
APP_ENV=development
SECRET_KEY=local-development-secret-key-with-at-least-32-characters
ADMIN_ROUTE_PREFIX=/x321/dashboard
ADMIN_EMAILS=admin@example.com

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=jsint
DB_USER=postgres
DB_PASSWORD=postgres
DB_SSLMODE=prefer

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_REQUIRED=false

ALLOWED_HOSTS=
BEHIND_PROXY=false
SESSION_COOKIE_SECURE=false
```

Примените миграции:

```bash
alembic upgrade head
```

Создайте администратора:

```bash
python manage.py create-admin --email=admin@example.com
```

Запустите development server:

```bash
python run_server.py
```

По умолчанию он слушает только:

```text
http://127.0.0.1:8080
```

## Production

Flask development server для production не используется.

Production entrypoint:

```text
Nginx -> Gunicorn -> Flask -> PostgreSQL / Redis
```

Полная русская инструкция:

- `docs/INSTALL_UPDATE.md` — штатный installer/updater и автоматический rollback;
- `docs/DEPLOYMENT.md` — production layout, systemd, Nginx, TLS и backup;
- `docs/PRODUCTION_AUDIT.md` — что было найдено аудитом и что исправлено.

Первая установка:

```bash
sudo bash deploy/install.sh \
  --domain=portfolio.example.com \
  --admin-email=you@example.com \
  --deploy-key=/root/jsint-site-deploy-key \
  --source-repo="$PWD" \
  --ref=v0.1.0
```

Обновление:

```bash
sudo bash /opt/jsint-site/current/deploy/update.sh --yes --ref=v0.1.1
```

Готовые примеры:

- `deploy/jsint-site.service`;
- `deploy/nginx.conf.example`;
- `default.env`.

Проверка production-зависимостей:

```bash
python manage.py health
```

HTTP healthcheck:

```text
GET /healthz
```

## CMS

Путь CMS задаётся через:

```env
ADMIN_ROUTE_PREFIX=/x321/dashboard
```

Доступ разрешён только пользователям, чей email явно перечислен в:

```env
ADMIN_EMAILS=admin@example.com
```

Публичной регистрации нет. Создание администратора выполняется операторской командой:

```bash
python manage.py create-admin --email=admin@example.com
```

Смена пароля:

```bash
python manage.py set-password --email=admin@example.com
```

## Безопасность

В production включены:

- fail-closed проверка конфигурации;
- secure/HttpOnly/SameSite session cookie;
- CSRF для изменяющих запросов;
- POST-only destructive actions;
- Redis-backed rate limiting входа;
- server-side slug validation;
- sanitization rich-text;
- Content-Security-Policy;
- HSTS;
- `X-Frame-Options: DENY`;
- `X-Content-Type-Options: nosniff`;
- trusted Host validation;
- административный `Cache-Control: no-store`.

## CI

GitHub Actions поднимает PostgreSQL и Redis и проверяет:

- Python 3.11/3.12;
- compileall;
- полный Alembic migration chain;
- production healthcheck;
- unit tests security primitives;
- HTTP/security smoke tests.

## Разработка миграций

После изменения SQLAlchemy models:

```bash
alembic revision --autogenerate -m "описание изменения"
alembic upgrade head
```

Перед commit просмотрите сгенерированную migration вручную.

## Notes Update Service

Этот репозиторий остаётся портфолио. Notes Update Service разворачивается как отдельный сервис, даже если использует тот же VPS:

```text
portfolio.example.com -> jsint-site
updates.example.com   -> Notes Update Service
```

Позже CMS этого сайта может получить раздел управления релизами Notes как операторский frontend, но private signing key Notes на web-сервер не переносится.
