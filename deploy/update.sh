#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=release-lib.sh
source "${SCRIPT_DIR}/release-lib.sh"

TARGET_REF="master"
KEEP_RELEASES=5
CONFIRMED=0

usage() {
    cat <<'EOF'
Безопасное production-обновление jsint-site.

Использование:
  sudo bash deploy/update.sh --yes [--ref=master] [--keep-releases=5]

Алгоритм:
  fetch exact Git commit
  -> подготовка нового immutable release + venv
  -> PostgreSQL backup
  -> stop service
  -> Alembic migrations
  -> unit/HTTP smoke tests
  -> production healthcheck
  -> atomic current symlink switch
  -> start service + HTTP healthcheck
  -> cleanup старых releases

При ошибке после начала migrations:
  stop
  -> previous current symlink
  -> restore PostgreSQL backup
  -> start previous release
  -> healthcheck
EOF
}

for arg in "$@"; do
    case "${arg}" in
        --ref=*) TARGET_REF="${arg#*=}" ;;
        --keep-releases=*) KEEP_RELEASES="${arg#*=}" ;;
        --yes) CONFIRMED=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Неизвестный аргумент: ${arg}" ;;
    esac
done

require_root
(( CONFIRMED == 1 )) || die "Обновление изменяет код и БД. Повторите с --yes."
[[ "${KEEP_RELEASES}" =~ ^[1-9][0-9]*$ ]] || die "Некорректный --keep-releases."

require_commands     curl flock git pg_dump pg_restore psql python3 sort sudo systemctl tar

acquire_update_lock

[[ -d "${REPO_DIR}/.git" ]] || die "Не найден deployment repository: ${REPO_DIR}"
[[ -L "${CURRENT_LINK}" ]] || die "Не найден current release symlink: ${CURRENT_LINK}"
[[ -f "${ENV_FILE}" ]] || die "Не найден environment-файл: ${ENV_FILE}"
services_are_active || die "Web/Celery runtime не полностью активен. Сначала восстановите штатное состояние."

OLD_RELEASE="$(current_release_path)"
[[ -n "${OLD_RELEASE}" && -d "${OLD_RELEASE}" ]] || die "Текущий release повреждён."
[[ -f "${OLD_RELEASE}/.release-commit" ]] || die "У текущего release отсутствует .release-commit."
[[ -f "${OLD_RELEASE}/.release-version" ]] || die "У текущего release отсутствует .release-version."

OLD_COMMIT="$(tr -d '\r\n' < "${OLD_RELEASE}/.release-commit")"
OLD_VERSION="$(tr -d '\r\n' < "${OLD_RELEASE}/.release-version")"

TARGET_COMMIT="$(resolve_ref "${TARGET_REF}")"
if [[ "${TARGET_COMMIT}" == "${OLD_COMMIT}" ]]; then
    log "Уже установлен commit ${TARGET_COMMIT}. Обновление не требуется."
    exit 0
fi

TARGET_VERSION="$(release_version_for_commit "${TARGET_COMMIT}")"
version_is_newer "${OLD_VERSION}" "${TARGET_VERSION}"     || die "Candidate VERSION ${TARGET_VERSION} не выше установленной ${OLD_VERSION}. Выпуск обновления требует увеличения VERSION."

log "Обновление ${OLD_VERSION} (${OLD_COMMIT:0:12}) -> ${TARGET_VERSION} (${TARGET_COMMIT:0:12})."

CANDIDATE_RELEASE="$(prepare_release "${TARGET_COMMIT}")"
BACKUP_FILE="$(database_backup)"

rollback_update() {
    local reason="$1"
    log "ROLLBACK: ${reason}"

    set +e
    if ! service_stop; then
        log "КРИТИЧЕСКАЯ ОШИБКА: не удалось гарантированно остановить ${SERVICE_NAME}; restore БД не выполняется."
        log "Backup сохранён: ${BACKUP_FILE}"
        set -e
        return 2
    fi
    switch_current_release "${OLD_RELEASE}"
    database_restore "${BACKUP_FILE}"
    install_service_units "${OLD_RELEASE}"
    if ! service_start; then
        log "КРИТИЧЕСКАЯ ОШИБКА: предыдущий Web/Celery runtime не запустился после restore."
        log "Backup сохранён: ${BACKUP_FILE}"
        set -e
        return 2
    fi

    if local_healthcheck && background_healthcheck "${OLD_RELEASE}" 75; then
        log "Rollback подтверждён: восстановлен ${OLD_VERSION} (${OLD_COMMIT:0:12})."
        set -e
        return 0
    fi

    log "КРИТИЧЕСКАЯ ОШИБКА: rollback выполнен, но healthcheck предыдущей версии не прошёл."
    log "Не удаляйте backup: ${BACKUP_FILE}"
    set -e
    return 2
}

log "Остановка приложения на окно миграции/проверки."
service_stop

if ! run_migrations "${CANDIDATE_RELEASE}"; then
    rollback_update "Alembic migration failed" || exit 2
    exit 1
fi

if ! run_release_tests "${CANDIDATE_RELEASE}"; then
    rollback_update "candidate test suite failed" || exit 2
    exit 1
fi

if ! run_health_command "${CANDIDATE_RELEASE}"; then
    rollback_update "candidate production health command failed" || exit 2
    exit 1
fi

if ! switch_current_release "${CANDIDATE_RELEASE}"; then
    rollback_update "atomic release switch failed" || exit 2
    exit 1
fi

if ! install_service_units "${CANDIDATE_RELEASE}"; then
    rollback_update "systemd unit installation failed" || exit 2
    exit 1
fi

if ! service_start; then
    rollback_update "systemd start failed" || exit 2
    exit 1
fi

if ! local_healthcheck; then
    rollback_update "post-switch HTTP healthcheck failed" || exit 2
    exit 1
fi

if ! background_healthcheck "${CANDIDATE_RELEASE}" 75; then
    rollback_update "post-switch Celery heartbeat failed" || exit 2
    exit 1
fi

cleanup_old_releases "${KEEP_RELEASES}"

log "Обновление завершено успешно."
log "Installed: ${TARGET_VERSION} (${TARGET_COMMIT})"
log "Rollback backup сохранён: ${BACKUP_FILE}"
log "Previous release сохранён в release history, пока не вытеснен retention policy."
