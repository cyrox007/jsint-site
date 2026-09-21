# Production-развёртывание jsint-site

Эта инструкция описывает рекомендуемый запуск портфолио на Ubuntu/Debian через Nginx + Gunicorn + PostgreSQL + Redis.

## Архитектура

```text
Internet
  |
 HTTPS
  v
Nginx
  |
  +-- /static/* -> /opt/jsint-site/static/
  |
  +-- остальные запросы -> 127.0.0.1:8080
                              |
                              v
                           Gunicorn
                              |
                           Flask
                          /     \
                    PostgreSQL  Redis
```

Gunicorn, PostgreSQL и Redis не должны быть доступны напрямую из Internet.

## 1. Системные пакеты

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql redis-server nginx git
```

Для TLS используйте Certbot или другой ACME-клиент.

## 2. Отдельный системный пользователь

```bash
sudo useradd --system --home /opt/jsint-site --shell /usr/sbin/nologin jsint-site
sudo install -d -o jsint-site -g jsint-site -m 0755 /opt/jsint-site
```

## 3. Код и virtualenv

```bash
sudo -u jsint-site git clone https://github.com/cyrox007/jsint-site.git /opt/jsint-site
cd /opt/jsint-site
sudo -u jsint-site python3 -m venv .venv
sudo -u jsint-site .venv/bin/pip install --upgrade pip
sudo -u jsint-site .venv/bin/pip install -r requirements.txt
```

Если production-серверу нужен доступ к private repository, используйте read-only deploy key. Не сохраняйте personal access token в URL remote.

## 4. PostgreSQL

Создайте отдельного пользователя и БД приложения:

```sql
CREATE ROLE jsint LOGIN PASSWORD 'replace-with-a-strong-random-password';
CREATE DATABASE jsint OWNER jsint;
```

Приложение не должно использовать PostgreSQL superuser.

## 5. Production environment

Создайте environment-файл вне репозитория:

```bash
sudo install -o root -g jsint-site -m 0640 /dev/null /etc/jsint-site.env
sudoedit /etc/jsint-site.env
```

Перечень переменных есть в `default.env`.

Минимальный пример:

```env
APP_ENV=production
SECRET_KEY=<случайная строка не короче 32 символов>
ADMIN_ROUTE_PREFIX=/x321/dashboard
ADMIN_EMAILS=you@example.com

ALLOWED_HOSTS=portfolio.example.com,www.portfolio.example.com
BEHIND_PROXY=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_NAME=jsint_session
SESSION_LIFETIME_HOURS=12
MAX_CONTENT_LENGTH=2097152
LOG_LEVEL=INFO

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=jsint
DB_USER=jsint
DB_PASSWORD=<пароль PostgreSQL>
DB_SSLMODE=prefer

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_REQUIRED=true
AUTH_RATE_LIMIT_ATTEMPTS=5
AUTH_RATE_LIMIT_WINDOW_SECONDS=300

YANDEX_METRIKA_ID=
```

SECRET_KEY можно получить так:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

`ADMIN_EMAILS` — явный allowlist пользователей CMS. Само наличие строки в таблице `users` административного доступа не даёт.

## 6. Миграции

```bash
sudo -u jsint-site /bin/bash -c 'set -a; source /etc/jsint-site.env; set +a; cd /opt/jsint-site && .venv/bin/alembic upgrade head'
```

Проверка revision:

```bash
sudo -u jsint-site /bin/bash -c 'set -a; source /etc/jsint-site.env; set +a; cd /opt/jsint-site && .venv/bin/alembic current'
```

Не выводите содержимое `/etc/jsint-site.env` в логи или CI.

## 7. Создание администратора

Email должен присутствовать в `ADMIN_EMAILS`:

```bash
sudo -u jsint-site /bin/bash -c 'set -a; source /etc/jsint-site.env; set +a; cd /opt/jsint-site && .venv/bin/python manage.py create-admin --email=you@example.com'
```

Пароль вводится интерактивно и не попадает в shell history.

Смена пароля:

```bash
sudo -u jsint-site /bin/bash -c 'set -a; source /etc/jsint-site.env; set +a; cd /opt/jsint-site && .venv/bin/python manage.py set-password --email=you@example.com'
```

## 8. Проверка зависимостей

```bash
sudo -u jsint-site /bin/bash -c 'set -a; source /etc/jsint-site.env; set +a; cd /opt/jsint-site && .venv/bin/python manage.py health'
```

При исправной production-среде ожидается:

```json
{"status":"ok","checks":{"config":true,"database":true,"redis":true}}
```

## 9. systemd

```bash
sudo cp /opt/jsint-site/deploy/jsint-site.service /etc/systemd/system/jsint-site.service
sudo systemctl daemon-reload
sudo systemctl enable --now jsint-site
sudo systemctl status jsint-site
```

Логи:

```bash
journalctl -u jsint-site -f
```

Проверка Gunicorn напрямую:

```bash
curl -fsS -H 'Host: portfolio.example.com' http://127.0.0.1:8080/healthz
```

## 10. Nginx и TLS

```bash
sudo cp /opt/jsint-site/deploy/nginx.conf.example /etc/nginx/sites-available/jsint-site.conf
sudoedit /etc/nginx/sites-available/jsint-site.conf
```

Замените домен и пути сертификатов. Затем:

```bash
sudo ln -s /etc/nginx/sites-available/jsint-site.conf /etc/nginx/sites-enabled/jsint-site.conf
sudo nginx -t
sudo systemctl reload nginx
```

После выпуска сертификата:

```bash
curl -fsS https://portfolio.example.com/healthz
```

## 11. Проверка после deployment

Проверить вручную:

1. главная открывается по HTTPS;
2. header links ведут на реальные секции;
3. опубликованный материал открывается только по своей категории;
4. `/register` возвращает 404;
5. admin login доступен по HTTPS;
6. несколько неверных паролей включают rate limit;
7. создание/редактирование публикации работает;
8. delete требует POST+CSRF;
9. logout завершает сессию;
10. `/healthz` возвращает 200;
11. в browser console нет ошибок Vue/неизвестных компонентов;
12. в Nginx/Gunicorn logs нет traceback.

## 12. Backup

Перед deployment с миграциями:

```bash
pg_dump --format=custom --file=/secure/backups/jsint-$(date +%Y%m%d-%H%M%S).dump jsint
```

Периодически делайте restore drill в отдельную тестовую БД. Наличие dump без проверенного восстановления не считается достаточной гарантией.

Redis содержит кеш и rate-limit state и не является источником пользовательских данных.

## 13. Обновление production

Рекомендуемый порядок:

1. backup PostgreSQL;
2. получить exact release commit;
3. обновить virtualenv/requirements;
4. `alembic upgrade head`;
5. `python manage.py health`;
6. `systemctl restart jsint-site`;
7. проверить `/healthz` и browser smoke.

Не запускайте Flask development server в production.

## 14. Rollback

Если новая версия не меняла schema, верните предыдущий release commit и перезапустите service.

Если deployment включал миграции, сначала оцените совместимость предыдущего кода с новой schema. Не выполняйте `alembic downgrade` вслепую. При несовместимости восстанавливайте PostgreSQL backup вместе с предыдущей версией приложения.

## 15. Notes Update Service

Портфолио и Notes Update Service остаются отдельными приложениями:

```text
portfolio.example.com -> jsint-site / Flask
updates.example.com   -> Notes Update Service
```

На одном VPS это могут быть разные systemd services и Unix users. CMS портфолио позже можно превратить в операторский frontend публикации релизов Notes, но production private signing key Notes на этот сервер не переносится.
