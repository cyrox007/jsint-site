#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=release-lib.sh
source "${SCRIPT_DIR}/release-lib.sh"

DOMAIN=""
WWW_DOMAIN=""
ADMIN_EMAIL=""
REPO_URL="git@github.com:cyrox007/jsint-site.git"
SOURCE_REPO=""
TARGET_REF="master"
CERTBOT_EMAIL=""
DEPLOY_KEY=""
DB_NAME_ARG="jsint"
DB_USER_ARG="jsint"
SKIP_PACKAGES=0
SKIP_ADMIN=0

usage() {
    cat <<'EOF'
Первичная production-установка jsint-site.

Использование:
  sudo bash deploy/install.sh \
    --domain=portfolio.example.com \
    --admin-email=you@example.com \
    [--www-domain=www.portfolio.example.com] \
    [--repo-url=git@github.com:cyrox007/jsint-site.git] \
    [--source-repo=/path/to/already-cloned-repository] \
    [--ref=master] \
    [--certbot-email=you@example.com] \
    [--deploy-key=/root/jsint-site-deploy-key] \
    [--db-name=jsint] \
    [--db-user=jsint] \
    [--skip-packages] \
    [--skip-admin]

Установщик предназначен только для ЧИСТОЙ установки.
Если /opt/jsint-site/current или /etc/jsint-site.env уже существуют,
используйте deploy/update.sh.
EOF
}

for arg in "$@"; do
    case "${arg}" in
        --domain=*) DOMAIN="${arg#*=}" ;;
        --www-domain=*) WWW_DOMAIN="${arg#*=}" ;;
        --admin-email=*) ADMIN_EMAIL="${arg#*=}" ;;
        --repo-url=*) REPO_URL="${arg#*=}" ;;
        --source-repo=*) SOURCE_REPO="${arg#*=}" ;;
        --ref=*) TARGET_REF="${arg#*=}" ;;
        --certbot-email=*) CERTBOT_EMAIL="${arg#*=}" ;;
        --deploy-key=*) DEPLOY_KEY="${arg#*=}" ;;
        --db-name=*) DB_NAME_ARG="${arg#*=}" ;;
        --db-user=*) DB_USER_ARG="${arg#*=}" ;;
        --skip-packages) SKIP_PACKAGES=1 ;;
        --skip-admin) SKIP_ADMIN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Неизвестный аргумент: ${arg}" ;;
    esac
done

require_root
[[ -n "${DOMAIN}" ]] || die "Укажите --domain."
[[ -n "${ADMIN_EMAIL}" ]] || die "Укажите --admin-email."
validate_domain "${DOMAIN}"
[[ -z "${WWW_DOMAIN}" ]] || validate_domain "${WWW_DOMAIN}"
validate_identifier "${DB_NAME_ARG}" "DB name"
validate_identifier "${DB_USER_ARG}" "DB user"
[[ "${ADMIN_EMAIL}" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] || die "Некорректный --admin-email."

if [[ -L "${CURRENT_LINK}" || -e "${CURRENT_LINK}" || -f "${ENV_FILE}" ]]; then
    die "Обнаружена существующая установка. Используйте deploy/update.sh."
fi

if (( SKIP_PACKAGES == 0 )); then
    require_commands apt-get
    log "Установка системных пакетов."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y         ca-certificates         curl         git         nginx         postgresql         postgresql-client         python3         python3-pip         python3-venv         redis-server         openssh-client         sudo         tar         util-linux
fi

require_commands     curl flock getent git groupadd nginx pg_dump pg_restore psql python3 sudo systemctl tar useradd

acquire_update_lock

if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
    log "Создание системной группы ${APP_GROUP}."
    groupadd --system "${APP_GROUP}"
fi

if ! id "${APP_USER}" >/dev/null 2>&1; then
    log "Создание системного пользователя ${APP_USER}."
    useradd \
        --system \
        --gid "${APP_GROUP}" \
        --home "${APP_ROOT}" \
        --shell /usr/sbin/nologin \
        --no-create-home \
        "${APP_USER}"
fi

ensure_layout
install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0700 "${APP_ROOT}/.ssh"

if [[ -n "${DEPLOY_KEY}" ]]; then
    [[ -f "${DEPLOY_KEY}" ]] || die "Не найден --deploy-key: ${DEPLOY_KEY}"
    log "Установка read-only Git deploy key для service account."
    install -o "${APP_USER}" -g "${APP_GROUP}" -m 0600 "${DEPLOY_KEY}" "${APP_ROOT}/.ssh/id_ed25519"
    cat > "${APP_ROOT}/.ssh/config" <<'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
EOF
    chown "${APP_USER}:${APP_GROUP}" "${APP_ROOT}/.ssh/config"
    chmod 0600 "${APP_ROOT}/.ssh/config"
fi

systemctl enable --now postgresql
systemctl enable --now redis-server

if [[ ! -d "${REPO_DIR}/.git" ]]; then
    log "Подготовка deployment repository."
    if [[ -n "${SOURCE_REPO}" ]]; then
        [[ -d "${SOURCE_REPO}/.git" ]] || die "--source-repo не является Git repository: ${SOURCE_REPO}"
        SOURCE_REMOTE="$(git -C "${SOURCE_REPO}" remote get-url origin 2>/dev/null || true)"
        [[ -n "${SOURCE_REMOTE}" ]] || die "У --source-repo отсутствует remote origin."
        git clone --no-hardlinks "${SOURCE_REPO}" "${REPO_DIR}"
        chown -R "${APP_USER}:${APP_GROUP}" "${REPO_DIR}"
        sudo -H -u "${APP_USER}" git -C "${REPO_DIR}" remote set-url origin "${SOURCE_REMOTE}"
    else
        [[ "${REPO_URL}" != http*://*@* ]] || die "Не помещайте credentials/token в --repo-url. Используйте deploy key."
        if [[ "${REPO_URL}" == git@github.com:* && ! -f "${APP_ROOT}/.ssh/id_ed25519" ]]; then
            die "Private GitHub repository требует --deploy-key или --source-repo."
        fi
        sudo -H -u "${APP_USER}" git clone "${REPO_URL}" "${REPO_DIR}"
    fi
fi

chown -R "${APP_USER}:${APP_GROUP}" "${REPO_DIR}"

ROLE_EXISTS="$(sudo -u postgres psql --dbname=postgres --tuples-only --no-align     --command="SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER_ARG}'" || true)"
DB_EXISTS="$(sudo -u postgres psql --dbname=postgres --tuples-only --no-align     --command="SELECT 1 FROM pg_database WHERE datname = '${DB_NAME_ARG}'" || true)"

[[ -z "${ROLE_EXISTS}" ]] || die "PostgreSQL role ${DB_USER_ARG} уже существует. Установщик не изменяет существующие credentials."
[[ -z "${DB_EXISTS}" ]] || die "PostgreSQL database ${DB_NAME_ARG} уже существует. Установщик предназначен для чистой установки."

DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(48))')"

log "Создание PostgreSQL role/database."
sudo -u postgres psql --dbname=postgres --set=ON_ERROR_STOP=1     --set=db_user="${DB_USER_ARG}"     --set=db_password="${DB_PASSWORD}"     --set=db_name="${DB_NAME_ARG}" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user') \gexec
SQL

ALLOWED_HOSTS_VALUE="${DOMAIN}"
SERVER_NAMES="${DOMAIN}"
if [[ -n "${WWW_DOMAIN}" ]]; then
    ALLOWED_HOSTS_VALUE="${DOMAIN},${WWW_DOMAIN}"
    SERVER_NAMES="${DOMAIN} ${WWW_DOMAIN}"
fi

log "Создание ${ENV_FILE}."
install -o root -g "${APP_GROUP}" -m 0640 /dev/null "${ENV_FILE}"
cat > "${ENV_FILE}" <<EOF
APP_ENV=production
SECRET_KEY=${SECRET_KEY}
ADMIN_ROUTE_PREFIX=/x321/dashboard
ADMIN_EMAILS=${ADMIN_EMAIL}

ALLOWED_HOSTS=${ALLOWED_HOSTS_VALUE}
BEHIND_PROXY=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_NAME=jsint_session
SESSION_LIFETIME_HOURS=12
MAX_CONTENT_LENGTH=2097152
LOG_LEVEL=INFO

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=${DB_NAME_ARG}
DB_USER=${DB_USER_ARG}
DB_PASSWORD=${DB_PASSWORD}
DB_SSLMODE=prefer

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_REQUIRED=true
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
AUTH_RATE_LIMIT_ATTEMPTS=5
AUTH_RATE_LIMIT_WINDOW_SECONDS=300

YANDEX_METRIKA_ID=
EOF
chmod 0640 "${ENV_FILE}"
chown root:"${APP_GROUP}" "${ENV_FILE}"

COMMIT="$(resolve_ref "${TARGET_REF}")"
RELEASE_DIR="$(prepare_release "${COMMIT}")"

run_migrations "${RELEASE_DIR}"
run_release_tests "${RELEASE_DIR}"
run_health_command "${RELEASE_DIR}"
switch_current_release "${RELEASE_DIR}"

log "Установка systemd units: web + Celery Worker + Celery Beat."
install_service_units "${RELEASE_DIR}"
service_enable_all
service_start
local_healthcheck
background_healthcheck "${RELEASE_DIR}" 75

log "Создание HTTP-конфигурации Nginx."
cat > /etc/nginx/sites-available/jsint-site.conf <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${SERVER_NAMES};

    server_tokens off;
    client_max_body_size 2m;

    location /static/ {
        alias ${CURRENT_LINK}/static/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public, max-age=604800";
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        proxy_redirect off;
    }
}
EOF

ln -sfn /etc/nginx/sites-available/jsint-site.conf /etc/nginx/sites-enabled/jsint-site.conf
if [[ -e /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if (( SKIP_ADMIN == 0 )); then
    log "Создание первого администратора. Пароль будет запрошен интерактивно."
    run_release "${RELEASE_DIR}"         "${RELEASE_DIR}/.venv/bin/python"         manage.py create-admin         --email="${ADMIN_EMAIL}"
fi

if [[ -n "${CERTBOT_EMAIL}" ]]; then
    log "Установка Certbot и выпуск TLS certificate."
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y certbot python3-certbot-nginx

    CERTBOT_ARGS=(
        certbot --nginx
        --non-interactive
        --agree-tos
        --redirect
        --email "${CERTBOT_EMAIL}"
        -d "${DOMAIN}"
    )
    if [[ -n "${WWW_DOMAIN}" ]]; then
        CERTBOT_ARGS+=( -d "${WWW_DOMAIN}" )
    fi
    "${CERTBOT_ARGS[@]}"
    nginx -t
    systemctl reload nginx
    curl --fail --silent --show-error --max-time 20 "https://${DOMAIN}/healthz"
    printf '\n'
else
    log "TLS автоматически не выпускался."
    log "До входа в CMS настройте HTTPS. Можно повторно запустить Certbot вручную:"
    log "  certbot --nginx -d ${DOMAIN}"
fi

log "Установка завершена."
log "Release: ${RELEASE_DIR}"
log "Environment: ${ENV_FILE}"
log "CMS: https://${DOMAIN}/x321/dashboard/login"
