# Дорожная карта административной панели jsint-site

Публичная часть проекта остаётся портфолио/публикационной площадкой. Закрытая CMS развивается как отдельная операторская панель для собственных сервисов.

## 0.1 — production baseline

Стартовая версия должна быть пригодна для постоянной работы на VPS:

- публикации и категории;
- закрытая single-admin CMS;
- dashboard «Обзор»;
- PostgreSQL + Redis health;
- CSRF/rate-limit/security headers;
- production Gunicorn/Nginx/systemd;
- `/healthz`;
- immutable release layout;
- installer;
- updater с PostgreSQL backup и automatic rollback;
- CI/preflight contracts.

## Следующий этап — Workspace Organizer Releases

В CMS появляется отдельный раздел:

```text
Workspace Organizer
└── Релизы
```

Панель должна уметь:

- показывать опубликованные версии;
- принимать ZIP + signed manifest + detached signature;
- проверять metadata/hash/signature через отдельный Notes Update Service;
- показывать channel/version/version code/source commit/package hash;
- публиковать уже подписанный release;
- показывать состояние feed;
- никогда не хранить production private signing key.

Security boundary:

```text
offline signing machine
        |
 ZIP + manifest + signature
        v
jsint-site operator UI
        |
 internal authenticated request
        v
Notes Update Service
```

## Этап — установки и лицензии

После стабилизации release publication:

```text
Workspace Organizer
├── Релизы
├── Установки
└── Лицензии
```

План:

- список installation IDs;
- состояние license/update entitlement;
- дата окончания;
- max version/update window;
- revoked/active status;
- безопасная выдача activation artifact;
- audit административных операций;
- поиск/фильтрация.

Private license/update signing keys остаются вне web server.

## Этап — мониторинг

Dashboard получает агрегированные operational cards:

- health Notes Update Service;
- количество активных installations;
- количество лицензий с истекающим сроком;
- последние опубликованные releases;
- ошибки доставки update artifacts;
- собственный health портфолио;
- PostgreSQL/Redis состояние.

Мониторинг не должен получать содержимое пользовательских Notes/Messenger данных.

## Этап — другие операторские функции

Админка может расширяться для других собственных проектов, если соблюдаются правила:

1. публичный portfolio frontend не зависит от availability operator integrations;
2. integrations изолированы по service/API boundary;
3. secrets каждого сервиса разделены;
4. destructive actions требуют явного подтверждения и CSRF;
5. важные действия журналируются;
6. один внешний сервис не получает прямой доступ к DB другого проекта без отдельного обоснованного contract;
7. private signing material не хранится в jsint-site.
