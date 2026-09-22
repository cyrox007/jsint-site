#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="jsinteractive.ru"

for arg in "$@"; do
    case "$arg" in
        --domain=*) DOMAIN="${arg#*=}" ;;
        -h|--help)
            echo "Использование: bash deploy/server-preflight.sh [--domain=jsinteractive.ru]"
            exit 0
            ;;
        *)
            echo "Неизвестный аргумент: $arg" >&2
            exit 2
            ;;
    esac
done

section() {
    printf '\n=== %s ===\n' "$1"
}

run() {
    printf '$ %s\n' "$*"
    "$@" || true
}

section "OS"
run uname -a
if [[ -f /etc/os-release ]]; then
    cat /etc/os-release
fi

section "Domain"
run getent ahosts "$DOMAIN"

section "Listening ports"
if command -v ss >/dev/null 2>&1; then
    run ss -ltnp
else
    echo "ss не найден"
fi

section "Nginx"
if command -v nginx >/dev/null 2>&1; then
    run nginx -v
    run nginx -t
    echo
    echo "Упоминания server_name $DOMAIN:"
    nginx -T 2>&1 | grep -nE "server_name[^;]*\b${DOMAIN//./\.}\b" || true
else
    echo "nginx не установлен"
fi

section "PostgreSQL"
if command -v psql >/dev/null 2>&1; then
    run psql --version
fi
if command -v systemctl >/dev/null 2>&1; then
    run systemctl is-active postgresql
fi

section "Redis"
if command -v redis-cli >/dev/null 2>&1; then
    run redis-cli --version
    run redis-cli ping
fi
if command -v systemctl >/dev/null 2>&1; then
    run systemctl is-active redis-server
fi

section "Existing jsint services"
if command -v systemctl >/dev/null 2>&1; then
    run systemctl status jsint-site --no-pager
    run systemctl status jsint-site-celery-worker --no-pager
    run systemctl status jsint-site-celery-beat --no-pager
fi

section "Existing paths"
for path in     /opt/jsint-site     /etc/jsint-site.env     /etc/nginx/sites-available/jsint-site.conf     /etc/nginx/sites-enabled/jsint-site.conf     /var/lib/jsint-site/celery     /var/backups/jsint-site
do
    if [[ -e "$path" || -L "$path" ]]; then
        ls -ld "$path"
    else
        echo "нет: $path"
    fi
done

section "System resources"
run df -h /
run free -h

section "Summary"
echo "Preflight только читает состояние сервера и ничего не изменяет."
echo "Перед install.sh проверьте конфликты server_name, занятый порт 8080 и существующие jsint-site paths/services."
