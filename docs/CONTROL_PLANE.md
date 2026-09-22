# Единая система публикаций, лицензий и релизов

`jsint-site` объединяет публичный сайт, CMS и операторский control plane Workspace Organizer.

## URL

- публичный сайт: `https://jsinteractive.ru/`;
- админка: `https://jsinteractive.ru/<ADMIN_ROUTE_PREFIX>/`;
- machine API: `https://jsinteractive.ru/api/notes/v1/`.

## Модель лицензии: что хранится в БД

В реестре лицензий хранится не private key, а уже подписанный `wo1...` token и его извлечённые параметры:

- `installation_id` — конкретная установка Workspace Organizer;
- `license_id` — операторский идентификатор лицензии;
- `customer`, `edition`, `max_users`, `features`;
- сроки локальной лицензии;
- отдельные ограничения доступа к online-обновлениям: `updates_until` и `max_version`;
- хеш одноразового activation code или хеш download credential;
- время последней связи клиента с control plane.

## Операторские вкладки лицензий

### Реестр

Показывает все лицензии, которые уже записаны в PostgreSQL. Для каждой установки отдельно отображаются:

- административный статус `active/revoked`;
- срок самой лицензии;
- право на обновления;
- активирован ли updater;
- `last seen`, последняя операция, IP и сообщённая версия клиента;
- features и лимит пользователей.

Presence — это телеметрия, а не удалённая проверка работоспособности. Сервер не может надёжно «пинговать» установку за NAT или в закрытой сети. Статус строится по последнему исходящему запросу клиента:

- «На связи» — контакт не старше 15 минут;
- «Недавно» — контакт за последние 24 часа;
- «Нет связи» — контакта не было более суток;
- «Нет данных» — клиент ещё ни разу не обращался к control plane.

Контакт обновляется при activation, обращении к feed/manifest/signature/ZIP и через `POST /api/notes/v1/heartbeat`.

### Выпустить

Оператор вводит обычные поля: installation ID, клиента, тариф, лимит пользователей, features и сроки.

По умолчанию local signing выключен. Это сохраняет исходную security boundary: private keys остаются офлайн.

Если оператор осознанно включает:

```env
NOTES_LOCAL_SIGNING_ENABLED=true
NOTES_SIGNING_KEY_ROOT=/var/lib/jsint-site/signing
```

то в форме можно указать путь к private key внутри `NOTES_SIGNING_KEY_ROOT`.

Ограничения local signing:

1. путь не сохраняется в БД и `.env`;
2. разрешены только regular files внутри отдельного signing root;
3. symlink запрещён;
4. файл должен иметь права 0600;
5. формат должен совпадать со штатным Notes tooling;
6. derived public key обязан совпасть с выбранным public trust root.

Поддерживаемый license-key format:

```text
wo-ed25519-secret-v1:<base64url 64-byte Ed25519 secret>
```

После выпуска оператор получает две разные сущности:

1. `wo1...` — лицензия самого Workspace Organizer;
2. одноразовый activation code — выдача credential для online updater.

### Импорт готовой

Если signing keys остаются на отдельной offline-машине, лицензия выпускается штатным Notes tooling, а в админку вставляется готовый `wo1...`.

## Активация online updater

На клиенте:

```bash
php bin/update_activate.php \
  --server=https://jsinteractive.ru/api/notes/v1/ \
  --installation-id=<UUID> \
  --activation-file=/private/activation-code \
  --credentials-out=/private/update-access.json
```

Machine API:

- `POST /api/notes/v1/activate`;
- `POST /api/notes/v1/heartbeat`;
- `GET /api/notes/v1/{alpha|beta|stable}/feed.json`;
- manifest/signature/ZIP в том же канале.

Artifact и heartbeat requests требуют:

```text
Authorization: Bearer <64hex credential>
X-Notes-Installation: <installation UUID>
```

## Операторские вкладки релизов

### Реестр

Показывает опубликованные версии, channel, version_code, source commit, минимальную исходную версию, PHP requirement, signing key, ZIP и SHA-256.

Релиз можно временно снять с feed без удаления записи.

### Опубликовать

Обычный оператор больше не собирает manifest вручную. Он указывает:

- путь к ZIP внутри `NOTES_RELEASE_STORAGE_PATH`;
- человекочитаемую версию;
- монотонно растущий `version_code`;
- канал `alpha/beta/stable`;
- `source_commit` — полный 40-символьный Git SHA;
- `min_source_version_code` — минимальная версия, с которой разрешён прямой переход;
- `requires_php`.

Control plane автоматически:

1. проверяет ZIP;
2. считает размер и SHA-256;
3. строит exact update manifest;
4. подписывает его локально, если local signing включён, либо показывает manifest для offline signing;
5. повторно проверяет signature штатным verifier;
6. регистрирует release и включает его в feed.

Update-key format:

```text
wo-update-ed25519-secret-v1:<base64url 64-byte Ed25519 secret>
```

### Расширенный импорт

Сохраняет старый низкоуровневый workflow: exact manifest JSON + `wou1...` signature + путь к ZIP. Нужен для полностью офлайн-signing ceremony.

## Release storage

ZIP хранится вне application tree:

```text
/var/lib/jsint-site/notes-releases
```

Пример размещения:

```bash
sudo install -o root -g jsint-site -m 0640 \
  ./workspace-organizer-v1.0.2.zip \
  /var/lib/jsint-site/notes-releases/workspace-organizer-v1.0.2.zip
```

## Local signing: подготовка каталога

Local signing — опциональное ослабление исходной offline boundary. Включайте его только на контролируемом vendor-сервере.

Пример:

```bash
sudo install -d -o jsint-site -g jsint-site -m 0700 /var/lib/jsint-site/signing
sudo install -o jsint-site -g jsint-site -m 0600 \
  /secure/source/prod-license-2026-01.license-secret \
  /var/lib/jsint-site/signing/prod-license-2026-01.license-secret
```

Аналогично размещается update signing key. Не храните signing root внутри Git checkout или release storage.

## Healthcheck

- общий: `GET /healthz`;
- control plane: `GET /api/notes/v1/health`.

Health дополнительно сообщает, включён ли local signing и существует ли signing root.

## Production environment

```env
NOTES_CONTROL_PLANE_ENABLED=true
NOTES_UPDATE_API_PREFIX=/api/notes/v1
NOTES_UPDATE_BASE_URL=https://jsinteractive.ru/api/notes/v1/
NOTES_RELEASE_STORAGE_PATH=/var/lib/jsint-site/notes-releases

# Безопасный default:
NOTES_LOCAL_SIGNING_ENABLED=false
NOTES_SIGNING_KEY_ROOT=/var/lib/jsint-site/signing
```
