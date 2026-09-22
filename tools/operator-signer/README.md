# Локальный Operator Signer

Этот helper запускается **на компьютере оператора**, а не на web-сервере.

Он нужен, чтобы админка `https://jsinteractive.ru` могла работать с private
signing keys на флешке или в локальной защищённой папке, не загружая ключи на
VPS и не передавая их через HTTP.

## Как это работает

1. оператор запускает signer на своём ПК;
2. signer слушает только `127.0.0.1:17843`;
3. при запуске печатается случайный код подключения;
4. в админке оператор вводит этот код и нажимает «Выбрать папку…»;
5. local signer открывает системный диалог выбора папки на ПК оператора;
6. браузер обращается напрямую к `127.0.0.1`, то есть к ПК оператора;
7. signer читает выбранную папку локально и возвращает только public key/fingerprint;
8. при выпуске лицензии или релиза signer подписывает данные локально;
9. на `jsinteractive.ru` отправляется только готовый `wo1...` или
   `wou1...`.

Private key не покидает локальный компьютер.

## Требования

- PHP 8.1+;
- расширение `sodium`;
- Firefox/Chrome/Edge с доступом страницы к loopback HTTP;
- private key в формате штатного tooling Workspace Organizer.

License key:

```text
wo-ed25519-secret-v1:<base64url 64-byte Ed25519 secret>
```

Update key:

```text
wo-update-ed25519-secret-v1:<base64url 64-byte Ed25519 secret>
```

## Windows / OSPanel

Из PowerShell:

```powershell
cd tools\operator-signer

.\start.ps1 -Php "D:\path\to\php.exe"
```

Либо, если нужный PHP уже находится в `PATH`:

```powershell
.\start.ps1
```

После запуска скопируйте показанный код подключения в админку.

## Linux/macOS

```bash
cd tools/operator-signer
./start.sh
```

## Security boundary

Signer:

- принимает соединения только через loopback;
- разрешает только один Origin, по умолчанию `https://jsinteractive.ru`;
- требует случайный pairing token;
- не предоставляет endpoint для чтения private key;
- не подписывает произвольные bytes;
- умеет подписывать только структурированную лицензию Workspace Organizer и
  валидный Workspace Organizer update manifest;
- при подписи сверяет derived public key с public trust root, который передала
  админка;
- после операции очищает secret key из рабочей переменной через
  `sodium_memzero`.

Путь к папке с ключами и pairing token остаются в браузере/на локальном helper
и не отправляются в форму на web-сервер.
