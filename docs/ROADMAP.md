# Дорожная карта административной панели jsint-site

Публичная часть проекта остаётся публикационной площадкой. Закрытая CMS является операторской панелью для собственных сервисов.

## 0.1 — production baseline

Базовая production-линия включает:

- публикации и категории;
- закрытую single-admin CMS;
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

## Следующий этап — аудит операторских действий

Нужно добавить:

- отдельный immutable audit log административных операций control plane;
- кто и когда импортировал/отозвал лицензию;
- кто зарегистрировал release;
- журнал повторной выдачи activation code;
- фильтрацию по installation/license/release;
- retention policy для operator audit.

Audit не должен хранить signed tokens, activation codes, credentials или private key material.

## Следующий этап — мониторинг

Dashboard расширяется operational cards:

- количество активных installations;
- лицензии с близким `updates_until`;
- последние опубликованные releases;
- ошибки выдачи update artifacts;
- попытки доступа с revoked/expired entitlement;
- состояние PostgreSQL/Redis/Celery/control plane storage.

Мониторинг не должен получать содержимое пользовательских Notes/Messenger данных.

## Следующий этап — удобство release ceremony

Можно добавить:

- preflight-страницу перед регистрацией релиза;
- отображение source SHA и package SHA крупным отдельным блоком;
- сравнение нового version_code с текущим channel head;
- предупреждение при публикации prerelease в stable;
- read-only страницу feed state;
- ручное выключение release из выдачи без удаления immutable записи.

Private signing material по-прежнему не переносится в web-приложение.

## Другие операторские функции

Админка может расширяться для других собственных проектов, если соблюдаются правила:

1. публичный frontend не зависит от availability operator integrations;
2. integrations изолированы по service/API boundary;
3. secrets разных trust domains разделены;
4. destructive actions требуют явного подтверждения и CSRF;
5. важные действия журналируются;
6. private signing material не хранится в jsint-site.
