#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${JSINT_APP_DIR:-/home/projects/js}"
SOURCE="${APP_DIR}/deploy/checkout/nginx.conf.example"
TARGET="/etc/nginx/sites-available/jsint-site.conf"
ENABLED="/etc/nginx/sites-enabled/jsint-site.conf"
LEGACY_ENABLED="/etc/nginx/sites-enabled/jsinteractive"
BACKUP=""
LEGACY_LINK_TARGET=""

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
    log "ОШИБКА: $*" >&2
    exit 1
}

rollback() {
    log "Выполняю rollback конфигурации Nginx."
    rm -f "${ENABLED}"

    if [[ -n "${BACKUP}" && -f "${BACKUP}" ]]; then
        cp -a "${BACKUP}" "${TARGET}"
        ln -sfn "${TARGET}" "${ENABLED}"
    else
        rm -f "${TARGET}"
    fi

    if [[ -n "${LEGACY_LINK_TARGET}" ]]; then
        ln -sfn "${LEGACY_LINK_TARGET}" "${LEGACY_ENABLED}"
    fi

    nginx -t || true
}

[[ "${EUID}" -eq 0 ]] || die "Запустите скрипт от root."
command -v nginx >/dev/null 2>&1 || die "Nginx не установлен."
[[ -f "${SOURCE}" ]] || die "Не найден конфиг: ${SOURCE}"

for required in \
    /etc/letsencrypt/live/jsinteractive.ru/fullchain.pem \
    /etc/letsencrypt/live/jsinteractive.ru/privkey.pem \
    /etc/letsencrypt/options-ssl-nginx.conf \
    /etc/letsencrypt/ssl-dhparams.pem
do
    [[ -e "${required}" ]] || die "Не найден TLS-файл Certbot: ${required}"
done

if [[ -f "${TARGET}" ]]; then
    BACKUP="${TARGET}.bak.$(date -u +'%Y%m%d%H%M%S')"
    cp -a "${TARGET}" "${BACKUP}"
    log "Существующий jsint-site config сохранён: ${BACKUP}"
fi

# Legacy vhost раньше обслуживал jsinteractive.ru как статический каталог и
# конфликтует с единым Flask/Gunicorn vhost. Сам файл не удаляем: отключаем
# только symlink, чтобы rollback был мгновенным.
if [[ -L "${LEGACY_ENABLED}" ]]; then
    LEGACY_LINK_TARGET="$(readlink "${LEGACY_ENABLED}")"
    rm -f "${LEGACY_ENABLED}"
    log "Legacy vhost отключён: ${LEGACY_ENABLED} -> ${LEGACY_LINK_TARGET}"
elif [[ -e "${LEGACY_ENABLED}" ]]; then
    die "Legacy path ${LEGACY_ENABLED} существует, но не является symlink. Отключите его вручную."
fi

install -o root -g root -m 0644 "${SOURCE}" "${TARGET}"
ln -sfn "${TARGET}" "${ENABLED}"

NGINX_TEST_OUTPUT=""
NGINX_TEST_STATUS=0
set +e
NGINX_TEST_OUTPUT="$(nginx -t 2>&1)"
NGINX_TEST_STATUS=$?
set -e
printf '%s\n' "${NGINX_TEST_OUTPUT}"

if [[ "${NGINX_TEST_STATUS}" -ne 0 ]] \
    || grep -Eq 'conflicting server name "(jsinteractive\\.ru|www\\.jsinteractive\\.ru)"' <<<"${NGINX_TEST_OUTPUT}"; then
    if grep -Eq 'conflicting server name "(jsinteractive\\.ru|www\\.jsinteractive\\.ru)"' <<<"${NGINX_TEST_OUTPUT}"; then
        log "ОШИБКА: после отключения legacy vhost остался другой конфликтующий server_name для jsinteractive.ru."
    fi
    rollback
    exit 1
fi

systemctl enable --now nginx
systemctl reload nginx

log "Nginx config установлен и успешно проверен."
log "HTTP перенаправляется на HTTPS."
log "Сайт: https://jsinteractive.ru/"
log "Health: https://jsinteractive.ru/healthz"
log "Notes API health: https://jsinteractive.ru/api/notes/v1/health"
