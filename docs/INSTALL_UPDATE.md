# Установщик и обновлятор jsint-site

Стартовая production-линия сайта использует release-layout вместо изменения файлов «на месте».

## Layout

После установки:

```text
/opt/jsint-site/
├── repository/                 # deployment Git repository
├── releases/
│   └── 0.1.0-<sha>-<timestamp>/
│       ├── .venv/
│       ├── .release-commit
│       ├── .release-version
│       └── application files
├── current -> releases/...
└── .ssh/                       # read-only Git deploy key, если используется

/etc/jsint-site.env             # production secrets/config
/var/backups/jsint-site/        # PostgreSQL rollback dumps
```

Gunicorn и Nginx всегда используют `/opt/jsint-site/current`. Новый release готовится рядом и становится активным только атомарной заменой symlink.

## Первая установка

Установщик рассчитан на Ubuntu/Debian и запускается только для чистой установки.

### Private GitHub repository

Рекомендуется отдельный **read-only deploy key**.

Создайте ключ на операторской машине/сервере:

```bash
ssh-keygen -t ed25519 -f /root/jsint-site-deploy-key -N ''
cat /root/jsint-site-deploy-key.pub
```

Добавьте public half в GitHub:

```text
Repository → Settings → Deploy keys → Add deploy key
```

Write access для deployment key не нужен.

Private key не коммитится в репозиторий.

### Запуск

Из доверенного checkout нужной версии:

```bash
sudo bash deploy/install.sh \
  --domain=jsinteractive.ru \
  --admin-email=you@example.com \
  --deploy-key=/root/jsint-site-deploy-key \
  --source-repo="$PWD" \
  --ref=v0.1.0 \
  --certbot-email=you@example.com
```

Если `--source-repo` не передан, installer клонирует `git@github.com:cyrox007/jsint-site.git` от service account.

Installer:

1. ставит системные packages;
2. создаёт отдельные Unix group/user `jsint-site`;
3. создаёт PostgreSQL role/database;
4. генерирует случайные DB password и `SECRET_KEY`;
5. сохраняет secrets только в `/etc/jsint-site.env`;
6. создаёт deployment repository;
7. собирает immutable release и отдельный venv;
8. выполняет Alembic migrations;
9. запускает unit/HTTP smoke tests;
10. запускает production healthcheck;
11. атомарно создаёт `current`;
12. устанавливает systemd service;
13. создаёт Nginx config;
14. интерактивно создаёт первого administrator;
15. при `--certbot-email` выпускает TLS certificate.

Installer не перезаписывает существующую installation. Если уже существуют `current` или `/etc/jsint-site.env`, он прекращает работу и предлагает updater.

## Проверка

После установки:

```bash
curl -fsS https://jsinteractive.ru/healthz
```

Ответ содержит текущую версию:

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

## Выпуск следующей версии

Перед production update:

1. увеличьте `VERSION`, например `0.1.0 -> 0.1.1`;
2. прогоните CI;
3. создайте immutable Git tag, например `v0.1.1`;
4. обновляйте production именно на tag.

Updater по умолчанию не разрешает same-version release или downgrade.

## Обновление

```bash
sudo bash /opt/jsint-site/current/deploy/update.sh \
  --yes \
  --ref=v0.1.1
```

Можно хранить последние пять release-каталогов:

```bash
sudo bash /opt/jsint-site/current/deploy/update.sh \
  --yes \
  --ref=v0.1.1 \
  --keep-releases=5
```

### Что делает updater

До destructive boundary:

```text
Git fetch
  -> resolve exact commit
  -> проверить VERSION > installed VERSION
  -> подготовить candidate release
  -> создать candidate venv
  -> compileall
  -> PostgreSQL backup
```

После backup:

```text
stop Gunicorn
  -> Alembic migrations
  -> candidate unit/HTTP tests
  -> candidate production healthcheck
  -> atomic current switch
  -> start Gunicorn
  -> HTTP /healthz
```

PostgreSQL dump сохраняется в:

```text
/var/backups/jsint-site/
```

Он не удаляется автоматически после успешного update.

## Автоматический rollback

Если после начала migrations происходит ошибка:

```text
stop
  -> вернуть previous current symlink
  -> пересоздать PostgreSQL database
  -> восстановить pre-update dump
  -> запустить previous release
  -> проверить /healthz
```

Restore БД **не начинается**, пока updater не подтвердил, что application service остановлен.

Если rollback healthcheck не проходит, updater завершает работу с critical status и сохраняет backup для ручного recovery.

## Блокировка параллельных операций

Install/update сериализуются через:

```text
/run/lock/jsint-site-update.lock
```

Два updater process одновременно не выполняются.

## Обновление private repository

`git fetch` выполняется от Unix account `jsint-site`, а не от root. Поэтому read-only deploy key должен оставаться доступным:

```text
/opt/jsint-site/.ssh/id_ed25519
```

Private deployment key даёт только read-доступ к source repository. Это **не** ключ подписи обновлений Workspace Organizer и не должен с ним пересекаться.

## Что updater намеренно не делает

- не меняет production secrets;
- не создаёт нового admin;
- не удаляет PostgreSQL backups;
- не выполняет blind `alembic downgrade`;
- не хранит GitHub personal access token;
- не копирует файлы поверх live release;
- не обновляет Notes Update Service — это отдельное приложение.

## Ручная диагностика

Текущий release:

```bash
readlink -f /opt/jsint-site/current
cat /opt/jsint-site/current/.release-version
cat /opt/jsint-site/current/.release-commit
```

Service:

```bash
systemctl status jsint-site
journalctl -u jsint-site -n 200 --no-pager
```

Nginx:

```bash
nginx -t
journalctl -u nginx -n 100 --no-pager
```

PostgreSQL backups:

```bash
ls -lh /var/backups/jsint-site/
```
