#!/usr/bin/env bash
set -euo pipefail

PHP_BIN="${PHP_BIN:-php}"
ORIGIN="${OPERATOR_SIGNER_ORIGIN:-https://jsinteractive.ru}"
PORT="${OPERATOR_SIGNER_PORT:-17843}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

TOKEN="$("${PHP_BIN}" -r 'echo bin2hex(random_bytes(24));')"
if [[ ! "${TOKEN}" =~ ^[0-9a-f]{48}$ ]]; then
    echo "Не удалось создать pairing token через PHP." >&2
    exit 1
fi

export OPERATOR_SIGNER_TOKEN="${TOKEN}"
export OPERATOR_SIGNER_ORIGIN="${ORIGIN}"

cat <<EOF

Workspace Organizer Operator Signer
-----------------------------------
Слушает только: http://127.0.0.1:${PORT}
Разрешённая страница: ${ORIGIN}

КОД ПОДКЛЮЧЕНИЯ:
${TOKEN}

Вставьте этот код во вкладке «Лицензии» или «Релизы».
Остановите signer после завершения выпуска/подписи (Ctrl+C).

EOF

cd "${SCRIPT_DIR}"
exec "${PHP_BIN}" -d display_errors=0 -S "127.0.0.1:${PORT}" router.php
