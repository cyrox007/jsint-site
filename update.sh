#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${JSINT_APP_DIR:-/home/projects/js}"
ENV_FILE="${JSINT_ENV_FILE:-${APP_DIR}/.env}"
BACKUP_ROOT="${JSINT_BACKUP_ROOT:-/var/backups/jsint-site}"
LOCK_FILE="${JSINT_LOCK_FILE:-/run/lock/jsint-site-checkout-update.lock}"
SERVICE_NAME="${JSINT_SERVICE_NAME:-jsint-site.service}"
WORKER_SERVICE_NAME="${JSINT_WORKER_SERVICE_NAME:-jsint-site-celery-worker.service}"
BEAT_SERVICE_NAME="${JSINT_BEAT_SERVICE_NAME:-jsint-site-celery-beat.service}"

TARGET_REF=""
CONFIRMED=0
SKIP_TESTS=0

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
    log "ОШИБКА: $*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Безопасное обновление checkout-развёртывания jsint-site.

Использование:
  sudo ./update.sh --yes [--ref=<branch|tag|sha>] [--skip-tests]

Если --ref не указан, используется текущая локальная ветка и её origin/<branch>.

Алгоритм:
  lock
  -> проверка чистого Git tree
  -> fetch
  -> PostgreSQL backup
  -> stop web/worker/beat
  -> reset exact target commit
  -> обновление .venv dependencies
  -> compileall
  -> Alembic migrations
  -> unit/HTTP smoke tests (database E2E отключены)
  -> CLI healthcheck
  -> start web/worker/beat
  -> HTTP healthcheck
  -> Celery heartbeat

При ошибке после остановки:
  stop
  -> reset previous commit
  -> восстановление PostgreSQL backup
  -> восстановление requirements
  -> start previous code
EOF
}

for arg in "$@"; do
    case "$arg" in
        --yes) CONFIRMED=1 ;;
        --ref=*) TARGET_REF="${arg#*=}" ;;
        --skip-tests) SKIP_TESTS=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Неизвестный аргумент: $arg" ;;
    esac
done

[[ "${EUID}" -eq 0 ]] || die "Запустите updater от root."
(( CONFIRMED == 1 )) || die "Повторите команду с --yes."
[[ -d "${APP_DIR}/.git" ]] || die "Не найден Git repository: ${APP_DIR}"
[[ -f "${ENV_FILE}" ]] || die "Не найден .env: ${ENV_FILE}"

for cmd in git flock python3 psql systemctl curl; do
    command -v "$cmd" >/dev/null 2>&1 || die "Не найдена обязательная команда: $cmd"
done

install -d -m 0755 "$(dirname "${LOCK_FILE}")"
exec 9>"${LOCK_FILE}"
flock -n 9 || die "Другой update process уже выполняется."

cd "${APP_DIR}"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    die "Есть незакоммиченные изменения tracked-файлов. .env игнорируется и этой проверке не мешает."
fi

CURRENT_BRANCH="$(git symbolic-ref --short -q HEAD || true)"
if [[ -z "${TARGET_REF}" ]]; then
    [[ -n "${CURRENT_BRANCH}" ]] || die "Detached HEAD: явно укажите --ref."
    TARGET_REF="${CURRENT_BRANCH}"
fi

log "Получение refs из origin."
git fetch --prune --tags origin

if git rev-parse --verify "origin/${TARGET_REF}^{commit}" >/dev/null 2>&1; then
    TARGET_COMMIT="$(git rev-parse "origin/${TARGET_REF}^{commit}")"
elif git rev-parse --verify "${TARGET_REF}^{commit}" >/dev/null 2>&1; then
    TARGET_COMMIT="$(git rev-parse "${TARGET_REF}^{commit}")"
else
    die "Не удалось разрешить ref: ${TARGET_REF}"
fi

OLD_COMMIT="$(git rev-parse HEAD)"
log "Текущее состояние checkout: branch=${CURRENT_BRANCH:-detached}, HEAD=${OLD_COMMIT}, target=${TARGET_REF}@${TARGET_COMMIT}."
if [[ "${TARGET_COMMIT}" == "${OLD_COMMIT}" ]]; then
    log "Commit ${TARGET_COMMIT} уже находится на диске. Выполняю полное обновление runtime и перезапуск сервисов."
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

: "${DB_HOST:?DB_HOST is required}"
: "${DB_PORT:?DB_PORT is required}"
: "${DB_NAME:?DB_NAME is required}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"
DB_SSLMODE="${DB_SSLMODE:-prefer}"
APP_BIND="${APP_BIND:-127.0.0.1:18080}"
ALLOWED_HOSTS="${ALLOWED_HOSTS:-jsinteractive.ru}"
NOTES_RELEASE_STORAGE_PATH="${NOTES_RELEASE_STORAGE_PATH:-/var/lib/jsint-site/notes-releases}"
NOTES_DIAGNOSTIC_STORAGE_PATH="${NOTES_DIAGNOSTIC_STORAGE_PATH:-/var/lib/jsint-site/diagnostics}"

install -d -o root -g jsint-site -m 0770 "${NOTES_RELEASE_STORAGE_PATH}"
install -d -o root -g jsint-site -m 0770 "${NOTES_DIAGNOSTIC_STORAGE_PATH}"

select_postgresql_client_tools() {
    local server_version_num server_major
    local path_dump path_restore
    local generic_dump="" generic_restore="" generic_major=""

    server_version_num="$(
        PGPASSWORD="${DB_PASSWORD}" PGSSLMODE="${DB_SSLMODE}" \
        psql \
            --host="${DB_HOST}" \
            --port="${DB_PORT}" \
            --username="${DB_USER}" \
            --dbname="${DB_NAME}" \
            --tuples-only \
            --no-align \
            --command='SHOW server_version_num;' \
        | tr -d '[:space:]'
    )"

    [[ "${server_version_num}" =~ ^[0-9]+$ ]] \
        || die "Не удалось определить server_version_num PostgreSQL."

    server_major="$((server_version_num / 10000))"
    path_dump="/usr/lib/postgresql/${server_major}/bin/pg_dump"
    path_restore="/usr/lib/postgresql/${server_major}/bin/pg_restore"

    if [[ -x "${path_dump}" && -x "${path_restore}" ]]; then
        PG_DUMP_BIN="${path_dump}"
        PG_RESTORE_BIN="${path_restore}"
    else
        generic_dump="$(command -v pg_dump || true)"
        generic_restore="$(command -v pg_restore || true)"

        if [[ -n "${generic_dump}" && -n "${generic_restore}" ]]; then
            generic_major="$(
                "${generic_dump}" --version \
                | sed -E 's/.* ([0-9]+)(\.[0-9]+)?.*/\1/' \
                | tr -d '[:space:]'
            )"
        fi

        if [[ "${generic_major}" =~ ^[0-9]+$ ]] && (( generic_major >= server_major )); then
            PG_DUMP_BIN="${generic_dump}"
            PG_RESTORE_BIN="${generic_restore}"
        else
            die "PostgreSQL server major=${server_major}, а совместимый pg_dump/pg_restore не найден. Установите postgresql-client-${server_major}; ожидаемый путь: ${path_dump}"
        fi
    fi

    log "PostgreSQL server major: ${server_major}."
    log "Backup client: $("${PG_DUMP_BIN}" --version)."
}

select_postgresql_client_tools

install -d -o root -g jsint-site -m 0750 "${BACKUP_ROOT}"
STAMP="$(date -u +'%Y%m%d%H%M%S')"
BACKUP_FILE="${BACKUP_ROOT}/${DB_NAME}-before-${TARGET_COMMIT:0:12}-${STAMP}.dump"

log "Backup PostgreSQL: ${BACKUP_FILE}"
PGPASSWORD="${DB_PASSWORD}" PGSSLMODE="${DB_SSLMODE}" \
"${PG_DUMP_BIN}" \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --dbname="${DB_NAME}" \
    --format=custom \
    --no-owner \
    --no-acl \
    --file="${BACKUP_FILE}"
chmod 0640 "${BACKUP_FILE}"
chown root:jsint-site "${BACKUP_FILE}"
[[ -s "${BACKUP_FILE}" ]] || die "Backup БД пустой."

stop_services() {
    systemctl stop "${BEAT_SERVICE_NAME}" "${WORKER_SERVICE_NAME}" "${SERVICE_NAME}" || true
}

install_units() {
    install -o root -g root -m 0644 "${APP_DIR}/deploy/checkout/jsint-site.service" "/etc/systemd/system/${SERVICE_NAME}"
    install -o root -g root -m 0644 "${APP_DIR}/deploy/checkout/jsint-site-celery-worker.service" "/etc/systemd/system/${WORKER_SERVICE_NAME}"
    install -o root -g root -m 0644 "${APP_DIR}/deploy/checkout/jsint-site-celery-beat.service" "/etc/systemd/system/${BEAT_SERVICE_NAME}"
    systemctl daemon-reload
}

start_services() {
    systemctl start "${SERVICE_NAME}"
    systemctl start "${WORKER_SERVICE_NAME}"
    systemctl start "${BEAT_SERVICE_NAME}"
}

install_dependencies() {
    if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
        log "Создание .venv."
        python3 -m venv "${APP_DIR}/.venv"
    fi
    "${APP_DIR}/.venv/bin/python" -m pip install --disable-pip-version-check -r "${APP_DIR}/requirements.txt"
}

http_health() {
    local host="${ALLOWED_HOSTS%%,*}"
    host="${host//[[:space:]]/}"
    curl --fail --silent --show-error --max-time 15 \
        --header "Host: ${host}" \
        "http://${APP_BIND}/healthz"
    printf '\n'
}

rollback() {
    local reason="$1"
    log "ROLLBACK: ${reason}"
    set +e
    stop_services
    git reset --hard "${OLD_COMMIT}"
    RESTORED_COMMIT="$(git rev-parse HEAD)"
    log "Rollback checkout: branch=${CURRENT_BRANCH:-detached}, HEAD=${RESTORED_COMMIT}, ожидаемый target=${TARGET_COMMIT}."
    if [[ -n "${CURRENT_BRANCH}" && "${RESTORED_COMMIT}" != "${TARGET_COMMIT}" ]]; then
        log "ВНИМАНИЕ: имя ветки ${CURRENT_BRANCH} сохранено, но checkout откатан на старый commit. Сверяйте HEAD, а не только название ветки."
    fi
    install_dependencies
    install_units
    PGPASSWORD="${DB_PASSWORD}" PGSSLMODE="${DB_SSLMODE}" \
    "${PG_RESTORE_BIN}" \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --username="${DB_USER}" \
        --dbname="${DB_NAME}" \
        --exit-on-error \
        --clean \
        --if-exists \
        --no-owner \
        --no-acl \
        "${BACKUP_FILE}"
    systemctl daemon-reload
    start_services
    sleep 2
    if http_health; then
        log "Rollback подтверждён: ${OLD_COMMIT}"
    else
        log "КРИТИЧЕСКАЯ ОШИБКА: rollback выполнен, но healthcheck не прошёл."
    fi
    set -e
}

log "Обновление ${OLD_COMMIT:0:12} -> ${TARGET_COMMIT:0:12}."
stop_services

trap 'rollback "необработанная ошибка updater"; exit 1' ERR

git reset --hard "${TARGET_COMMIT}"
CHECKED_OUT_COMMIT="$(git rev-parse HEAD)"
[[ "${CHECKED_OUT_COMMIT}" == "${TARGET_COMMIT}" ]] \
    || die "После reset HEAD=${CHECKED_OUT_COMMIT}, ожидался ${TARGET_COMMIT}."
log "Candidate checkout подтверждён: ${CHECKED_OUT_COMMIT}."
install_dependencies

log "Проверка Python syntax."
"${APP_DIR}/.venv/bin/python" -m compileall -q "${APP_DIR}"

log "Применение Alembic migrations."
"${APP_DIR}/.venv/bin/alembic" upgrade head

if (( SKIP_TESTS == 0 )); then
    log "Запуск unit/HTTP smoke tests. Database E2E принудительно отключены для рабочей БД."
    ALLOW_DATABASE_E2E_TESTS=false \
        "${APP_DIR}/.venv/bin/python" -m unittest discover -s tests -v
else
    log "Тесты пропущены оператором (--skip-tests)."
fi

log "Проверка production dependencies."
"${APP_DIR}/.venv/bin/python" manage.py health

install_units
start_services
sleep 2

log "HTTP healthcheck."
http_health

log "Проверка свежего Celery heartbeat."
"${APP_DIR}/.venv/bin/python" manage.py background-health \
    --fresh \
    --expect-version="$(tr -d '\r\n' < VERSION)" \
    --wait=75

trap - ERR

INSTALLED_COMMIT="$(git rev-parse HEAD)"
[[ "${INSTALLED_COMMIT}" == "${TARGET_COMMIT}" ]] \
    || die "После запуска runtime HEAD=${INSTALLED_COMMIT}, ожидался ${TARGET_COMMIT}."

log "Обновление завершено успешно."
log "Установлен commit: ${INSTALLED_COMMIT}"
log "Checkout: branch=${CURRENT_BRANCH:-detached}, HEAD=${INSTALLED_COMMIT}."
log "Backup перед обновлением: ${BACKUP_FILE}"
