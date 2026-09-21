# Production-развёртывание jsint-site

Для стартовой production-линии используется release-layout с атомарным symlink `current`. Не копируйте новую версию поверх работающего application tree.

Подробный контракт installer/updater: [INSTALL_UPDATE.md](INSTALL_UPDATE.md).

## Архитектура

```text
Internet
  |
 HTTPS
  v
Nginx
  |
  +-- /static/* -> /opt/jsint-site/current/static/
  |
  +-- остальные запросы -> 127.0.0.1:8080
                              |
                              v
                           Gunicorn
                              |
                  /opt/jsint-site/current
                              |
                           Flask
                          /     \
                    PostgreSQL  Redis
```

Файловая layout:

```text
/opt/jsint-site/
├── repository/
├── releases/
│   ├── 0.1.0-<sha>-<timestamp>/
│   └── ...
├── current -> releases/<active-release>/
└── .ssh/

/etc/jsint-site.env
/var/backups/jsint-site/
```

PostgreSQL, Redis и Gunicorn не публикуются напрямую в Internet.

## Рекомендуемая первая установка

Подготовьте read-only GitHub deploy key для private repository и добавьте его public half в Repository → Settings → Deploy keys.

Затем из доверенного checkout:

```bash
sudo bash deploy/install.sh \
  --domain=jsinteractive.ru \
  --admin-email=you@example.com \
  --deploy-key=/root/jsint-site-deploy-key \
  --source-repo="$PWD" \
  --ref=v0.1.0 \
  --certbot-email=you@example.com
```

Installer сам:

- устанавливает системные dependencies;
- создаёт Unix account `jsint-site`;
- создаёт PostgreSQL role/database;
- генерирует production secrets;
- создаёт `/etc/jsint-site.env`;
- собирает immutable release и venv;
- применяет Alembic migrations;
- запускает tests/healthcheck;
- устанавливает systemd/Nginx;
- создаёт первого administrator;
- при необходимости выпускает TLS через Certbot.

Installer предназначен только для чистой установки и не перезаписывает уже установленную систему.

## Production environment

Основная конфигурация живёт вне repository:

```text
/etc/jsint-site.env
```

Файл принадлежит `root:jsint-site` и имеет mode `0640`.

Ключевые параметры:

```env
APP_ENV=production
SECRET_KEY=<случайное значение>
ADMIN_ROUTE_PREFIX=/x321/dashboard
ADMIN_EMAILS=you@example.com

ALLOWED_HOSTS=jsinteractive.ru
BEHIND_PROXY=true
SESSION_COOKIE_SECURE=true

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=jsint
DB_USER=jsint
DB_PASSWORD=<случайный пароль>

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_REQUIRED=true
```

Production startup fail-closed, если обязательные secrets/hosts/admin allowlist отсутствуют.

## Проверка состояния

HTTP:

```bash
curl -fsS https://jsinteractive.ru/healthz
```

Пример:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "checks": {
    "database": true,
    "redis": true
  }
}
```

CLI:

```bash
sudo -H -u jsint-site /bin/bash -c '
  set -a
  source /etc/jsint-site.env
  set +a
  cd /opt/jsint-site/current
  .venv/bin/python manage.py health
'
```

Текущий exact release:

```bash
readlink -f /opt/jsint-site/current
cat /opt/jsint-site/current/.release-version
cat /opt/jsint-site/current/.release-commit
```

## Обновление production

Каждый production release обязан увеличивать `VERSION` и желательно публиковаться immutable Git tag.

Например:

```bash
sudo bash /opt/jsint-site/current/deploy/update.sh \
  --yes \
  --ref=v0.1.1
```

Updater:

```text
fetch exact commit
  -> VERSION guard
  -> candidate release + venv
  -> PostgreSQL backup
  -> stop application
  -> migrations
  -> candidate tests
  -> candidate health
  -> atomic current switch
  -> start
  -> HTTP healthcheck
```

Если после начала migrations возникает ошибка, updater возвращает previous release и восстанавливает PostgreSQL из pre-update dump.

Подробности: [INSTALL_UPDATE.md](INSTALL_UPDATE.md).

## Systemd

Unit устанавливается в:

```text
/etc/systemd/system/jsint-site.service
```

Он всегда запускает:

```text
/opt/jsint-site/current/.venv/bin/gunicorn
```

Проверка:

```bash
systemctl status jsint-site
journalctl -u jsint-site -f
```

## Nginx и TLS

Installer сначала создаёт HTTP reverse proxy. Если задан `--certbot-email`, Certbot выпускает certificate и переводит host на HTTPS.

Проверка конфигурации:

```bash
nginx -t
systemctl status nginx
```

HSTS приложение отдаёт только для реально HTTPS requests.

## Backup

Updater автоматически создаёт PostgreSQL rollback dump перед каждым обновлением:

```text
/var/backups/jsint-site/
```

Для отдельного планового backup:

```bash
sudo -u postgres pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --file=/secure/backups/jsint-$(date +%Y%m%d-%H%M%S).dump \
  jsint
```

Периодически выполняйте restore drill. Наличие dump без проверенного восстановления не считается достаточной гарантией.

Redis содержит cache/rate-limit state и не является источником пользовательских данных.

## Smoke после deployment

Проверить:

1. главная открывается по HTTPS;
2. мобильный header/hero не создаёт horizontal overflow;
3. article открывается только по своей category;
4. `/register` возвращает 404;
5. CMS доступна только пользователю из `ADMIN_EMAILS`;
6. login rate limit работает;
7. создание/редактирование публикации работает;
8. destructive actions требуют POST+CSRF;
9. logout завершает session;
10. `/healthz` возвращает `status=ok`;
11. dashboard «Обзор» показывает версию/PostgreSQL/Redis;
12. в Nginx/Gunicorn logs нет traceback.

## Notes Update Service

Портфолио и Notes Update Service остаются разными приложениями даже на одном VPS:

```text
jsinteractive.ru          -> jsint-site
updates.jsinteractive.ru -> Notes Update Service
```

Админка портфолио будет расширяться как операторская панель:

- публикации;
- релизы Workspace Organizer;
- лицензии;
- установки;
- мониторинг.

Но private signing key обновлений Workspace Organizer никогда не переносится в web-приложение.
