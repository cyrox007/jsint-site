# Демонстрационный проект Vanga

Vanga используется как небольшой внешний клиент для проверки control plane jsint-site без привязки к Workspace Organizer UI.

## Что подключено

- `GET /api/demo/v1/vanga/health`
- `POST /api/demo/v1/vanga/activate`
- `POST /api/demo/v1/vanga/heartbeat`
- существующий реестр лицензий и presence-механизм;
- отдельный заголовок клиента `X-JSInt-Installation`.

Демо API намеренно не публикует update artifacts. Текущий release pipeline содержит продукт-специфичные поля Workspace Organizer (`product=workspace-organizer`, PHP requirement и отдельный signature domain). Перед подключением релизов Vanga его нужно перевести на product-aware модель.

## Проверка

В репозитории `cyrox007/vanga`, ветка `feature/jsint-site-demo`:

```bash
python jsint_demo.py --site https://<jsint-site> health
python jsint_demo.py --site https://<jsint-site> activate --code <activation-code>
python jsint_demo.py --site https://<jsint-site> heartbeat
```

После heartbeat запись установки должна отображаться в разделе лицензий как «На связи», а `last_seen_action` — как `vanga-demo-heartbeat`.

## Ограничение текущего этапа

Лицензионная запись пока не содержит отдельного `product_id`. Поэтому Vanga служит интеграционным demo-клиентом существующего реестра, а не полноценным вторым коммерческим продуктом. Следующий архитектурный шаг — добавить реестр продуктов и связать с ним лицензии, релизы и audit.
