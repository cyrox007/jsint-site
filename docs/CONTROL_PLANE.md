# Единая система публикаций, лицензий и релизов

`jsint-site` является единым web-приложением для двух контуров:

1. публичный сайт и CMS публикаций;
2. операторский control plane Workspace Organizer: лицензии, установки и релизы.

Отдельный Notes Update Service для базовой production-схемы больше не требуется. Machine API работает в том же Flask runtime и той же PostgreSQL БД.

## URL

Публичная часть:

```text
https://jsinteractive.ru/
```

Админка:

```text
https://jsinteractive.ru/<ADMIN_ROUTE_PREFIX>/
```

Клиентский API Workspace Organizer:

```text
https://jsinteractive.ru/api/notes/v1/
```

При необходимости `updates.jsinteractive.ru` можно позже направить на тот же Flask runtime, но это alias, а не отдельное приложение.

## Криптографическая граница

Web-сервер хранит только публичные Ed25519 trust roots:

- `config/notes_trust.py::LICENSE_TRUSTED_KEYS`;
- `config/notes_trust.py::UPDATE_TRUSTED_KEYS`.

Private license signing key и private update signing key:

- не копируются на VPS;
- не хранятся в PostgreSQL;
- не хранятся в `.env`;
- не загружаются через CMS;
- не попадают в backup сайта или CI artifacts.

Лицензия сначала выпускается офлайн штатным инструментом Workspace Organizer. В CMS импортируется только готовый `wo1...` token.

Release manifest и detached signature также создаются и подписываются офлайн. CMS проверяет подпись, SHA-256, размер и имя ZIP перед регистрацией.

## Реестр лицензий

Админка → «Лицензии».

При импорте подписанной лицензии система:

1. проверяет Ed25519 подпись;
2. проверяет payload и срок действия;
3. извлекает `installation_id`, `license_id`, edition, features и max_users;
4. задаёт entitlement обновлений: `updates_until` и/или `max_version`;
5. генерирует одноразовый 64-hex activation code;
6. хранит только SHA-256 activation code.

После активации клиента одноразовый код уничтожается и создаётся отдельный 64-hex download credential. В БД хранится только его SHA-256.

Статус `revoked` немедленно инвалидирует update credential.

## Активация Workspace Organizer

На клиенте:

```bash
php bin/update_activate.php \
  --server=https://jsinteractive.ru/api/notes/v1/ \
  --installation-id=<UUID из /admin/license> \
  --activation-file=/private/activation-code \
  --credentials-out=/private/update-access.json
```

После успешной активации:

```env
UPDATE_ACCESS_MODE=online
UPDATE_CREDENTIALS_FILE=/private/update-access.json
UPDATE_FEED_URL=https://jsinteractive.ru/api/notes/v1/stable/feed.json
```

API сохраняет текущий Notes contract:

- `POST /api/notes/v1/activate`;
- `GET /api/notes/v1/{alpha|beta|stable}/feed.json`;
- `GET /api/notes/v1/{channel}/release-<version_code>.json`;
- `GET /api/notes/v1/{channel}/release-<version_code>.sig`;
- `GET /api/notes/v1/{channel}/<package>.zip`.

Artifact requests требуют:

```text
Authorization: Bearer <64hex credential>
X-Notes-Installation: <installation UUID>
```

## Реестр релизов

ZIP хранится только во внешнем каталоге:

```text
/var/lib/jsint-site/notes-releases
```

Application tree остаётся immutable.

Перед регистрацией положите уже принятый ZIP в storage:

```bash
sudo install -o root -g jsint-site -m 0640 \
  ./workspace-organizer-v1.0.2.zip \
  /var/lib/jsint-site/notes-releases/workspace-organizer-v1.0.2.zip
```

В админке → «Релизы» вставьте:

- exact manifest JSON;
- detached `wou1...` signature;
- абсолютный путь к ZIP внутри `NOTES_RELEASE_STORAGE_PATH`.

Система отклонит релиз, если:

- public key неизвестен;
- подпись manifest неверна;
- manifest не соответствует Workspace Organizer schema;
- ZIP лежит вне разрешённого storage;
- имя, размер или SHA-256 не совпадают;
- такой channel/version_code уже зарегистрирован.

## Healthcheck

Общий:

```text
GET /healthz
```

Machine control plane:

```text
GET /api/notes/v1/health
```

При включённом `NOTES_CONTROL_PLANE_ENABLED=true` общий healthcheck считается успешным только если доступны PostgreSQL, Redis и control plane storage/trust roots.

## Production environment

```env
NOTES_CONTROL_PLANE_ENABLED=true
NOTES_UPDATE_API_PREFIX=/api/notes/v1
NOTES_UPDATE_BASE_URL=https://jsinteractive.ru/api/notes/v1/
NOTES_RELEASE_STORAGE_PATH=/var/lib/jsint-site/notes-releases
```

`deploy/install.sh` создаёт внешний storage автоматически и добавляет эти значения в `/etc/jsint-site.env`.

## Что остаётся отдельным

Отдельным остаётся только офлайн signing ceremony. Это намеренная security boundary, а не отдельный web-сервис.
