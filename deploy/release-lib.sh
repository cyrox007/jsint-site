#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="jsint-site"
APP_USER="${JSINT_APP_USER:-jsint-site}"
APP_GROUP="${JSINT_APP_GROUP:-jsint-site}"
APP_ROOT="${JSINT_APP_ROOT:-/opt/jsint-site}"
REPO_DIR="${JSINT_REPO_DIR:-${APP_ROOT}/repository}"
RELEASES_DIR="${JSINT_RELEASES_DIR:-${APP_ROOT}/releases}"
CURRENT_LINK="${JSINT_CURRENT_LINK:-${APP_ROOT}/current}"
ENV_FILE="${JSINT_ENV_FILE:-/etc/jsint-site.env}"
SERVICE_NAME="${JSINT_SERVICE_NAME:-jsint-site.service}"
BACKUP_ROOT="${JSINT_BACKUP_ROOT:-/var/backups/jsint-site}"
LOCK_FILE="${JSINT_LOCK_FILE:-/run/lock/jsint-site-update.lock}"

log() {
    printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >&2
}

die() {
    log "ОШИБКА: $*"
    exit 1
}

require_root() {
    [[ "${EUID}" -eq 0 ]] || die "Команда должна выполняться от root."
}

require_commands() {
    local cmd
    for cmd in "$@"; do
        command -v "${cmd}" >/dev/null 2>&1 || die "Не найдена обязательная команда: ${cmd}"
    done
}

validate_identifier() {
    local value="$1"
    local label="$2"
    [[ "${value}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "Некорректный ${label}: ${value}"
}

validate_domain() {
    local value="$1"
    [[ "${value}" =~ ^[A-Za-z0-9.-]+$ ]] || die "Некорректный домен: ${value}"
    [[ "${value}" != .* && "${value}" != *. && "${value}" != *..* ]] || die "Некорректный домен: ${value}"
}

ensure_layout() {
    install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0755 "${APP_ROOT}" "${RELEASES_DIR}"
    install -d -o root -g "${APP_GROUP}" -m 0750 "${BACKUP_ROOT}"
}

load_environment() {
    [[ -f "${ENV_FILE}" ]] || die "Не найден environment-файл: ${ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a

    : "${DB_HOST:?DB_HOST is required}"
    : "${DB_NAME:?DB_NAME is required}"
    : "${DB_USER:?DB_USER is required}"
    : "${ALLOWED_HOSTS:?ALLOWED_HOSTS is required}"

    validate_identifier "${DB_NAME}" "DB_NAME"
    validate_identifier "${DB_USER}" "DB_USER"
}

run_release() {
    local release_dir="$1"
    shift

    [[ -d "${release_dir}" ]] || die "Release directory отсутствует: ${release_dir}"
    sudo -u "${APP_USER}" env         JSINT_RUNTIME_ENV_FILE="${ENV_FILE}"         JSINT_RUNTIME_RELEASE_DIR="${release_dir}"         /bin/bash -c '
            set -a
            source "$JSINT_RUNTIME_ENV_FILE"
            set +a
            cd "$JSINT_RUNTIME_RELEASE_DIR"
            exec "$@"
        ' bash "$@"
}

resolve_ref() {
    local ref="$1"
    local commit=""

    sudo -u "${APP_USER}" git -C "${REPO_DIR}" fetch --prune --tags origin >&2

    if commit="$(git -C "${REPO_DIR}" rev-parse --verify "origin/${ref}^{commit}" 2>/dev/null)"; then
        printf '%s\n' "${commit}"
        return 0
    fi

    if commit="$(git -C "${REPO_DIR}" rev-parse --verify "${ref}^{commit}" 2>/dev/null)"; then
        printf '%s\n' "${commit}"
        return 0
    fi

    die "Не удалось разрешить Git ref: ${ref}"
}

version_is_newer() {
    local installed="$1"
    local candidate="$2"

    [[ "${installed}" != "${candidate}" ]] || return 1
    local highest
    highest="$(printf '%s\n%s\n' "${installed}" "${candidate}" | sort -V | tail -n 1)"
    [[ "${highest}" == "${candidate}" ]]
}

release_version_for_commit() {
    local commit="$1"
    local version=""

    version="$(git -C "${REPO_DIR}" show "${commit}:VERSION" 2>/dev/null | tr -d '\r\n' || true)"
    [[ -n "${version}" ]] || die "В commit ${commit} отсутствует VERSION."
    [[ "${version}" =~ ^[0-9A-Za-z][0-9A-Za-z.+-]*$ ]] || die "Некорректная VERSION: ${version}"
    printf '%s\n' "${version}"
}

prepare_release() {
    local commit="$1"
    local version release_name final_dir temp_dir

    version="$(release_version_for_commit "${commit}")"
    release_name="${version}-${commit:0:12}-$(date -u +'%Y%m%d%H%M%S')"
    final_dir="${RELEASES_DIR}/${release_name}"
    temp_dir="${RELEASES_DIR}/.new-${release_name}-$$"

    [[ ! -e "${final_dir}" ]] || die "Release уже существует: ${final_dir}"
    [[ ! -e "${temp_dir}" ]] || die "Временный release уже существует: ${temp_dir}"

    log "Подготовка release ${release_name} из commit ${commit}."
    install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0755 "${temp_dir}"

    git -C "${REPO_DIR}" archive --format=tar "${commit}" | tar -xf - -C "${temp_dir}"
    chown -R "${APP_USER}:${APP_GROUP}" "${temp_dir}"

    sudo -u "${APP_USER}" python3 -m venv "${temp_dir}/.venv"
    sudo -u "${APP_USER}" "${temp_dir}/.venv/bin/python" -m pip install         --disable-pip-version-check         --requirement "${temp_dir}/requirements.txt"

    sudo -u "${APP_USER}" "${temp_dir}/.venv/bin/python" -m compileall -q "${temp_dir}"

    printf '%s\n' "${commit}" > "${temp_dir}/.release-commit"
    printf '%s\n' "${version}" > "${temp_dir}/.release-version"
    chown "${APP_USER}:${APP_GROUP}" "${temp_dir}/.release-commit" "${temp_dir}/.release-version"

    mv "${temp_dir}" "${final_dir}"
    printf '%s\n' "${final_dir}"
}

run_release_tests() {
    local release_dir="$1"
    log "Запуск unit/HTTP smoke tests в ${release_dir}."
    run_release "${release_dir}" "${release_dir}/.venv/bin/python" -m unittest discover -s tests -v
}

run_migrations() {
    local release_dir="$1"
    log "Применение Alembic migrations из ${release_dir}."
    run_release "${release_dir}" "${release_dir}/.venv/bin/alembic" upgrade head
}

run_health_command() {
    local release_dir="$1"
    log "Проверка production dependencies в ${release_dir}."
    run_release "${release_dir}" "${release_dir}/.venv/bin/python" manage.py health
}

current_release_path() {
    if [[ -L "${CURRENT_LINK}" ]]; then
        readlink -f "${CURRENT_LINK}"
    fi
}

switch_current_release() {
    local release_dir="$1"
    local temporary_link="${APP_ROOT}/.current.new.$$"

    [[ -d "${release_dir}" ]] || die "Нельзя переключиться на отсутствующий release: ${release_dir}"
    rm -f "${temporary_link}"
    ln -s "${release_dir}" "${temporary_link}"
    mv -Tf "${temporary_link}" "${CURRENT_LINK}"
    chown -h "${APP_USER}:${APP_GROUP}" "${CURRENT_LINK}"
}

database_backup() {
    load_environment

    [[ "${DB_HOST}" == "127.0.0.1" || "${DB_HOST}" == "localhost" ]]         || die "Автоматический backup сейчас поддерживает только локальный PostgreSQL."

    local stamp backup_file
    stamp="$(date -u +'%Y%m%d%H%M%S')"
    backup_file="${BACKUP_ROOT}/${DB_NAME}-${stamp}.dump"

    log "Создание PostgreSQL backup: ${backup_file}"
    sudo -u postgres pg_dump         --format=custom         --no-owner         --no-acl         --file="${backup_file}"         "${DB_NAME}"

    chmod 0640 "${backup_file}"
    chown root:"${APP_GROUP}" "${backup_file}"
    [[ -s "${backup_file}" ]] || die "Создан пустой PostgreSQL backup."

    printf '%s\n' "${backup_file}"
}

database_restore() {
    local backup_file="$1"
    load_environment

    [[ -f "${backup_file}" && -s "${backup_file}" ]] || die "Некорректный backup: ${backup_file}"
    [[ "${DB_HOST}" == "127.0.0.1" || "${DB_HOST}" == "localhost" ]]         || die "Автоматический restore сейчас поддерживает только локальный PostgreSQL."

    log "Восстановление PostgreSQL из ${backup_file}."
    sudo -u postgres psql --dbname=postgres --set=ON_ERROR_STOP=1         --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" >/dev/null
    sudo -u postgres dropdb --if-exists "${DB_NAME}"
    sudo -u postgres createdb --owner="${DB_USER}" "${DB_NAME}"
    sudo -u postgres pg_restore         --exit-on-error         --no-owner         --no-acl         --role="${DB_USER}"         --dbname="${DB_NAME}"         "${backup_file}"
}

service_restart() {
    systemctl restart "${SERVICE_NAME}"
}

service_stop() {
    systemctl stop "${SERVICE_NAME}" || true
}

service_start() {
    systemctl start "${SERVICE_NAME}"
}

local_healthcheck() {
    load_environment
    local host="${ALLOWED_HOSTS%%,*}"
    host="${host//[[:space:]]/}"
    validate_domain "${host}"

    log "HTTP healthcheck через локальный Gunicorn, Host=${host}."
    curl --fail --silent --show-error --max-time 15         --header "Host: ${host}"         "http://127.0.0.1:8080/healthz"
    printf '\n'
}

acquire_update_lock() {
    install -d -m 0755 "$(dirname "${LOCK_FILE}")"
    exec 9>"${LOCK_FILE}"
    flock -n 9 || die "Другой install/update process уже выполняется."
}

cleanup_old_releases() {
    local keep="${1:-5}"
    [[ "${keep}" =~ ^[1-9][0-9]*$ ]] || die "Некорректный keep releases: ${keep}"

    local current
    current="$(current_release_path || true)"

    mapfile -t releases < <(find "${RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d ! -name '.new-*' -printf '%T@ %p\n' | sort -nr | awk '{print $2}')

    local index=0 path
    for path in "${releases[@]}"; do
        index=$((index + 1))
        if (( index <= keep )); then
            continue
        fi
        if [[ -n "${current}" && "$(readlink -f "${path}")" == "${current}" ]]; then
            continue
        fi
        log "Удаление старого release: ${path}"
        rm -rf --one-file-system "${path}"
    done
}
