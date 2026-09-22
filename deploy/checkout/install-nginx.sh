#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${JSINT_APP_DIR:-/home/projects/js}"
SOURCE="${APP_DIR}/deploy/checkout/nginx.conf.example"
TARGET="/etc/nginx/sites-available/jsint-site.conf"
ENABLED="/etc/nginx/sites-enabled/jsint-site.conf"
BACKUP=""

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
    log "ОШИБКА: $*" >&2
    exit 1
}

[[ "${EUID}" -eq 0 ]] || die "Запустите скрипт от root."
command -v nginx >/dev/null 2>&1 || die "Nginx не установлен."
[[ -f "${SOURCE}" ]] || die "Не найден конфиг: ${SOURCE}"

if [[ -f "${TARGET}" ]]; then
    BACKUP="${TARGET}.bak.$(date -u +'%Y%m%d%H%M%S')"
    cp -a "${TARGET}" "${BACKUP}"
    log "Существующий конфиг сохранён: ${BACKUP}"
fi

install -o root -g root -m 0644 "${SOURCE}" "${TARGET}"
ln -sfn "${TARGET}" "${ENABLED}"

if ! nginx -t; then
    log "Новый Nginx config не прошёл проверку. Выполняю rollback."
    rm -f "${ENABLED}"
    if [[ -n "${BACKUP}" && -f "${BACKUP}" ]]; then
        cp -a "${BACKUP}" "${TARGET}"
        ln -sfn "${TARGET}" "${ENABLED}"
    else
        rm -f "${TARGET}"
    fi
    nginx -t || true
    exit 1
fi

systemctl enable --now nginx
systemctl reload nginx

log "Nginx config установлен и успешно проверен."
log "HTTP: http://jsinteractive.ru/"
log "Health: http://jsinteractive.ru/healthz"
log "Notes API health: http://jsinteractive.ru/api/notes/v1/health"
log "Для production TLS после проверки HTTP используйте Certbot/Nginx."
