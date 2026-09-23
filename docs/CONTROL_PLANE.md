# Единая система публикаций, лицензий и релизов

`jsint-site` объединяет публичный сайт, CMS и операторский control plane Workspace Organizer.

## URL

- публичный сайт: `https://jsinteractive.ru/`;
- админка: `https://jsinteractive.ru/<ADMIN_ROUTE_PREFIX>/`;
- machine API: `https://jsinteractive.ru/api/notes/v1/`;
- локальный signer оператора: `http://127.0.0.1:17843/v1`.

## Криптографическая граница

Private license/update keys **не должны находиться на web-сервере**.

Операторская схема устроена так:

```text
браузер на ПК оператора
        │
        ├── HTTPS ───────────────► jsinteractive.ru
        │                         формы, БД, ZIP, manifest, verify
        │
        └── HTTP loopback ───────► 127.0.0.1:17843
                                  чтение флешки/локальной папки,
                                  Ed25519 signing
```

Web-сервер знает только public trust roots из `config/notes_trust.py`.

Браузер по правилам безопасности не может сам открыть произвольный
`D:\...`, `E:\...` или каталог флешки. Поэтому на компьютере оператора
запускается небольшой local signer из `tools/operator-signer/`.

Путь к папке с ключами, pairing token и содержимое private key не отправляются
в серверную форму и не сохраняются в PostgreSQL.

## Local Operator Signer

### Запуск в Windows

Если нужный PHP находится в `PATH`:

```powershell
cd tools\operator-signer
.\start.ps1
```

Если используется конкретный PHP, например из OSPanel:

```powershell
.\start.ps1 -Php "D:\path\to\php.exe"
```

Signer выводит временный код подключения и начинает слушать только:

```text
http://127.0.0.1:17843
```

По умолчанию запросы принимает только от страницы:

```text
https://jsinteractive.ru
```

### Как сайт находит ключ

Во вкладке «Лицензии → Выпустить» оператор вводит:

1. временный код подключения signer;
2. нажимает «Выбрать папку…»;
3. local signer открывает системный диалог ОС и возвращает выбранный путь только в браузер;
4. нажимает «Проверить ключи».

Путь обрабатывается **на `127.0.0.1`**, а не на VPS.

Signer просматривает только выбранную папку, распознаёт два штатных формата:

```text
wo-ed25519-secret-v1:<base64url 64-byte Ed25519 secret>
wo-update-ed25519-secret-v1:<base64url 64-byte Ed25519 secret>
```

и возвращает в браузер только:

- тип ключа;
- имя файла;
- public key;
- короткий fingerprint.

Админка сопоставляет public key с production trust root. Если нужного ключа нет,
кнопка выпуска не приводит к серверной регистрации.

### Защита local signer

Signer:

- принимает соединения только с `127.0.0.1/::1`;
- проверяет точный browser Origin;
- требует случайный pairing token, созданный при каждом запуске;
- не имеет endpoint для чтения private key;
- не имеет endpoint для подписи произвольных bytes;
- умеет только:
  - сканировать выбранную папку;
  - выпускать структурированный Workspace Organizer `wo1...` token;
  - подписывать валидный Workspace Organizer update manifest;
- перед подписью сверяет derived public key с public trust root, указанным
  админкой;
- очищает рабочую переменную secret key через `sodium_memzero`.

После окончания операторской операции signer следует остановить.

## Реестр лицензий

В PostgreSQL хранятся:

- `installation_id`;
- `license_id`;
- уже подписанный `wo1...` token;
- `customer`, `edition`, `max_users`, `features`;
- срок действия лицензии;
- ограничения доступа к обновлениям: `updates_until`, `max_version`;
- SHA-256 одноразового activation code или download credential;
- состояние последней связи клиента.

Private key и локальный путь к нему в БД отсутствуют.

## Выпуск лицензии

Админка → «Лицензии → Выпустить».

Оператор задаёт:

- Installation ID;
- клиента;
- License ID;
- edition;
- лимит пользователей;
- features;
- дату начала;
- срок лицензии;
- срок доступа к обновлениям;
- максимальный разрешённый `version_code`.

Далее:

1. оператор подключает local signer;
2. выбирает папку на своём ПК/флешке;
3. сайт сверяет найденный ключ с public trust root;
4. параметры лицензии передаются напрямую из браузера в local signer;
5. signer строит и подписывает `wo1...`;
6. только готовый `wo1...` отправляется в `jsinteractive.ru`;
7. сервер повторно проверяет Ed25519 signature и записывает лицензию в БД;
8. сервер показывает одноразовый activation code для updater.

То есть результат состоит из двух разных сущностей:

- `wo1...` — лицензия самого Workspace Organizer;
- activation code — одноразовый код для получения online-update credential.

### Импорт готовой лицензии

Вкладка «Импорт готовой» остаётся для полностью офлайн-процесса. Можно
подписать лицензию штатным tooling Workspace Organizer на отдельной машине и
вставить уже готовый `wo1...`.

## Presence / last seen

Control plane не пытается входящим соединением «пинговать» клиентскую
установку: за NAT или в закрытой сети это ненадёжно.

Статус строится по последнему исходящему запросу клиента:

- «На связи» — контакт не старше 15 минут;
- «Недавно» — контакт за последние 24 часа;
- «Нет связи» — контакта не было более суток;
- «Нет данных» — клиент ещё не связывался с control plane.

Last seen обновляется при:

- activation;
- heartbeat;
- запросе feed;
- manifest;
- signature;
- ZIP.

Machine endpoint:

```text
POST /api/notes/v1/heartbeat
```

Он использует те же update credentials:

```text
Authorization: Bearer <64hex credential>
X-Notes-Installation: <installation UUID>
```

«Нет связи» не означает, что offline/закрытая установка неисправна.

## Релизы

### Реестр

Показывает:

- version;
- version_code;
- channel;
- source commit;
- минимальный source version_code;
- PHP requirement;
- signing key;
- ZIP;
- SHA-256;
- время публикации;
- active/inactive.

Релиз можно снять с feed без удаления записи.

### Быстрый выпуск из GitHub

Основной операторский сценарий не требует ручной загрузки ZIP и заполнения
технических полей. Во вкладке «Релизы → Опубликовать» нажмите
«Подтянуть, проверить и подготовить к подписи». Поле Git tag можно оставить
пустым — тогда берётся последний опубликованный GitHub Release.

Сервер автоматически:

1. получает Release только из настроенного `NOTES_RELEASE_GITHUB_REPOSITORY`;
2. требует три штатных artifact: ZIP, `.sha256` и `.source-sha`;
3. сверяет SHA-256 из checksum artifact и GitHub asset digest;
4. сверяет source SHA с commit, на который указывает Git tag;
5. читает `VERSION`, `VERSION_CODE` и `STATUS` непосредственно из
   `core/Version.php` внутри ZIP;
6. для стандартного последовательного обновления задаёт
   `min_source_version_code = version_code - 1`;
7. строит exact manifest и переводит интерфейс сразу к локальной подписи.

После этих проверок единственное критическое действие оператора — подтвердить
подпись production update key через local signer. Приватный ключ по-прежнему
не попадает на VPS.

Для нестандартного перехода или стороннего ZIP ниже остаётся ручной режим.

### Ручная подготовка и публикация

Оператор выбирает ZIP стандартным файловым диалогом браузера. Панель загружает
его в `NOTES_RELEASE_STORAGE_PATH`, показывает прогресс и после загрузки
автоматически проверяет ZIP magic, размер и SHA-256.

Далее оператор вводит:

- version;
- version_code;
- channel;
- source commit;
- min_source_version_code;
- requires_php.

Сервер:

1. проверяет ZIP;
2. считает размер и SHA-256;
3. строит exact update manifest;
4. возвращает manifest в браузер.

Далее браузер передаёт exact manifest в local signer на компьютере оператора.
Local signer подписывает его update private key и возвращает только
`wou1...` signature.

После этого браузер отправляет на сервер:

- exact manifest;
- готовую `wou1...` signature;
- путь к уже проверенному ZIP на сервере.

Control plane повторно проверяет signature, имя ZIP, размер и SHA-256 и только
после этого публикует release в feed.

### Расширенный импорт

Если local signer не используется, exact manifest можно подписать на отдельной
offline-машине и импортировать через вкладку «Расширенный импорт».

## Release storage

ZIP хранится вне application tree:

```text
/var/lib/jsint-site/notes-releases
```

Пример:

```bash
sudo install -o root -g jsint-site -m 0640 \
  ./workspace-organizer-v1.0.2.zip \
  /var/lib/jsint-site/notes-releases/workspace-organizer-v1.0.2.zip
```

## Активация online updater

На клиенте:

```bash
php bin/update_activate.php \
  --server=https://jsinteractive.ru/api/notes/v1/ \
  --installation-id=<UUID> \
  --activation-file=/private/activation-code \
  --credentials-out=/private/update-access.json
```

После активации:

```env
UPDATE_ACCESS_MODE=online
UPDATE_CREDENTIALS_FILE=/private/update-access.json
UPDATE_FEED_URL=https://jsinteractive.ru/api/notes/v1/stable/feed.json
```

## Production environment

```env
NOTES_CONTROL_PLANE_ENABLED=true
NOTES_UPDATE_API_PREFIX=/api/notes/v1
NOTES_UPDATE_BASE_URL=https://jsinteractive.ru/api/notes/v1/
NOTES_RELEASE_STORAGE_PATH=/var/lib/jsint-site/notes-releases
NOTES_RELEASE_GITHUB_REPOSITORY=cyrox007/Notes
NOTES_RELEASE_GITHUB_TOKEN=
NOTES_RELEASE_DEFAULT_REQUIRES_PHP=8.1.0

# Для public repository token не нужен. Для private repository используется
# отдельный read-only token; его нельзя помещать в Git, release ZIP или логи.

# Этот URL открывает браузер оператора, поэтому он обязан указывать только
# на loopback текущего компьютера.
NOTES_OPERATOR_SIGNER_URL=http://127.0.0.1:17843/v1
```

Private signing paths в production env отсутствуют.

## Healthcheck

- общий: `GET /healthz`;
- control plane: `GET /api/notes/v1/health`.

Healthcheck web-сервера намеренно не проверяет local signer: helper находится
на компьютере конкретного оператора и может быть выключен большую часть
времени.
