#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${JSINT_APP_DIR:-/home/projects/js}"
ENV_FILE="${JSINT_ENV_FILE:-${APP_DIR}/.env}"
APP_USER="${JSINT_APP_USER:-jsint-site}"
APP_GROUP="${JSINT_APP_GROUP:-jsint-site}"

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
    log "ОШИБКА: $*" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || die "Запустите setup от root."
[[ -d "${APP_DIR}/.git" ]] || die "Не найден repository: ${APP_DIR}"
[[ -f "${ENV_FILE}" ]] || die "Сначала создайте и заполните ${ENV_FILE}"

if ! getent group "${APP_GROUP}" >/dev/null; then
    groupadd --system "${APP_GROUP}"
fi
if ! id "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --gid "${APP_GROUP}" --home-dir /nonexistent --shell /usr/sbin/nologin "${APP_USER}"
fi

log "Подготовка runtime directories."
install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0750 /var/lib/jsint-site/celery
install -d -o root -g "${APP_GROUP}" -m 0770 /var/lib/jsint-site/notes-releases
install -d -o root -g "${APP_GROUP}" -m 0750 /var/backups/jsint-site

chown root:"${APP_GROUP}" "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

log "Создание Python virtualenv и установка dependencies."
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
    python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/python" -m pip install --disable-pip-version-check -r "${APP_DIR}/requirements.txt"
"${APP_DIR}/.venv/bin/python" -m compileall -q "${APP_DIR}"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

log "Применение Alembic migrations."
"${APP_DIR}/.venv/bin/alembic" upgrade head

log "Запуск unit/HTTP smoke tests."
"${APP_DIR}/.venv/bin/python" -m unittest discover -s tests -v

log "Проверка конфигурации и PostgreSQL/Redis/control plane."
"${APP_DIR}/.venv/bin/python" manage.py health

log "Установка checkout-mode systemd units."
install -o root -g root -m 0644 "${APP_DIR}/deploy/checkout/jsint-site.service" /etc/systemd/system/jsint-site.service
install -o root -g root -m 0644 "${APP_DIR}/deploy/checkout/jsint-site-celery-worker.service" /etc/systemd/system/jsint-site-celery-worker.service
install -o root -g root -m 0644 "${APP_DIR}/deploy/checkout/jsint-site-celery-beat.service" /etc/systemd/system/jsint-site-celery-beat.service
systemctl daemon-reload
systemctl enable jsint-site.service jsint-site-celery-worker.service jsint-site-celery-beat.service
systemctl restart jsint-site.service
systemctl restart jsint-site-celery-worker.service
systemctl restart jsint-site-celery-beat.service

sleep 2

APP_BIND="${APP_BIND:-127.0.0.1:18080}"
ALLOWED_HOSTS="${ALLOWED_HOSTS:-jsinteractive.ru}"
HOST="${ALLOWED_HOSTS%%,*}"
HOST="${HOST//[[:space:]]/}"

log "HTTP healthcheck."
curl --fail --silent --show-error --max-time 15 \
    --header "Host: ${HOST}" \
    "http://${APP_BIND}/healthz"
printf '\n'

log "Проверка Celery heartbeat."
"${APP_DIR}/.venv/bin/python" manage.py background-health \
    --fresh \
    --expect-version="$(tr -d '\r\n' < "${APP_DIR}/VERSION")" \
    --wait=75

log "Checkout-mode установлен."
log "Сервисы: jsint-site, jsint-site-celery-worker, jsint-site-celery-beat"
log "Обновление: cd ${APP_DIR} && sudo ./update.sh --yes"
