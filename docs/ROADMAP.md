# Дорожная карта административной панели jsint-site

Публичная часть проекта остаётся публикационной площадкой. Закрытая CMS является операторской панелью для собственных сервисов.

## 0.1 — production baseline

Базовая production-линия включает:

- публикации и категории;
- закрытую CMS с allowlist администраторов и управлением пользователями;
- dashboard «Обзор»;
- PostgreSQL + Redis health;
- CSRF/rate-limit/security headers;
- production Gunicorn/Nginx/systemd;
- `/healthz`;
- immutable release layout;
- installer;
- updater с PostgreSQL backup и automatic rollback;
- CI/preflight contracts;
- Celery Worker + Beat.

## Workspace Organizer — реализованный control plane

В одной CMS работают:

```text
Workspace Organizer
├── Релизы
└── Лицензии
```

Реализованный контракт:

- импорт уже подписанного `wo1` license token;
- привязка к installation ID;
- active/revoked status;
- update entitlement по сроку и max version;
- одноразовый activation code;
- отдельный credential для authenticated artifact download;
- импорт уже подписанного update manifest + detached signature;
- проверка Ed25519 public trust root;
- проверка package filename/size/SHA-256;
- registry каналов alpha/beta/stable;
- feed/manifest/signature/package API, совместимый с Workspace Organizer;
- release ZIP хранится вне immutable application tree;
- private license/update signing keys остаются офлайн.

Machine API:

```text
/api/notes/v1/
```

Подробнее: `docs/CONTROL_PLANE.md`.

## Реализовано — аудит операторских действий

Добавлен append-only журнал control plane:

- фиксируются выпуск и импорт лицензии;
- фиксируется изменение статуса лицензии;
- фиксируется повторная выдача activation code без сохранения самого кода;
- фиксируются подготовка, публикация и включение/отключение релиза;
- сохраняется снимок email оператора и его UUID;
- доступны фильтры по действию, результату, installation/license/release;
- machine API пишет только ошибки выдачи artifacts и код причины;
- PostgreSQL trigger запрещает UPDATE и DELETE записей журнала;
- политика хранения задаётся `OPERATOR_AUDIT_RETENTION_DAYS`, автоматического удаления из приложения нет.

Журнал не хранит signed tokens, activation codes, credentials, private key material или их содержимое.

## Реализовано — мониторинг

Dashboard показывает:

- количество installations, связывавшихся не более 15 минут назад;
- лицензии, у которых `updates_until` истекает в ближайшие 30 дней;
- последние опубликованные releases;
- ошибки выдачи update artifacts за 24 часа;
- отдельный счётчик отказов revoked/expired entitlement;
- PostgreSQL, Redis и Celery heartbeat;
- состояние control plane через его существующий healthcheck.

Мониторинг использует только технические метаданные update-контуров и не получает содержимое пользовательских Notes/Messenger данных.

## Реализовано — release ceremony

Обычный выпуск теперь включает:

- server-side preflight перед подписью manifest;
- сравнение нового `version_code` с активной головой канала;
- остановку выпуска при несовместимом preflight;
- предупреждение, если имя stable-версии похоже на prerelease;
- отображение текущих голов stable/beta/alpha и фактических manifest/signature;
- source SHA и package SHA-256 в карточках релизов;
- ручное выключение release из feed без удаления immutable записи;
- журналирование подготовки, публикации и изменения статуса релиза.

Private signing material по-прежнему не переносится в web-приложение.

## Другие операторские функции

Админка может расширяться для других собственных проектов, если соблюдаются правила:

1. публичный frontend не зависит от availability operator integrations;
2. integrations изолированы по service/API boundary;
3. secrets разных trust domains разделены;
4. destructive actions требуют явного подтверждения и CSRF;
5. важные действия журналируются;
6. private signing material не хранится в jsint-site.
