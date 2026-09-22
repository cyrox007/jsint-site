import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DeploymentContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_version_exists(self):
        version = self.read("VERSION").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

    def test_server_preflight_is_read_only_contract(self):
        preflight = self.read("deploy/server-preflight.sh")
        self.assertIn("nginx -T", preflight)
        self.assertIn("ss -ltnp", preflight)
        self.assertNotIn("apt-get install", preflight)
        self.assertNotIn("systemctl restart", preflight)

    def test_systemd_uses_atomic_current_release(self):
        unit = self.read("deploy/jsint-site.service")
        self.assertIn("WorkingDirectory=/opt/jsint-site/current", unit)
        self.assertIn("/opt/jsint-site/current/.venv/bin/gunicorn", unit)
        self.assertNotIn("WorkingDirectory=/opt/jsint-site\n", unit)

    def test_background_systemd_units_follow_current_release(self):
        worker = self.read("deploy/jsint-site-celery-worker.service")
        beat = self.read("deploy/jsint-site-celery-beat.service")
        self.assertIn("WorkingDirectory=/opt/jsint-site/current", worker)
        self.assertIn("celery_app:celery_app worker", worker)
        self.assertIn("WorkingDirectory=/opt/jsint-site/current", beat)
        self.assertIn("celery_app:celery_app beat", beat)
        self.assertIn("/var/lib/jsint-site/celery/celerybeat-schedule", beat)
        self.assertIn("ReadWritePaths=/var/lib/jsint-site/celery", beat)

    def test_installer_is_clean_install_only(self):
        installer = self.read("deploy/install.sh")
        self.assertIn("Используйте deploy/update.sh", installer)
        self.assertIn("SECRET_KEY=", installer)
        self.assertIn("DB_PASSWORD=", installer)
        self.assertIn("run_migrations", installer)
        self.assertIn("run_release_tests", installer)
        self.assertIn("local_healthcheck", installer)
        self.assertIn("background_healthcheck", installer)
        self.assertIn("CELERY_BROKER_URL=", installer)
        self.assertIn("CELERY_RESULT_BACKEND=", installer)
        self.assertIn("--existing-db", installer)
        self.assertIn("--db-host=", installer)
        self.assertIn("--db-password-file=", installer)
        self.assertIn("PGPASSWORD=", installer)

    def test_updater_requires_backup_migration_and_rollback(self):
        updater = self.read("deploy/update.sh")
        self.assertIn("--yes", updater)
        self.assertIn("database_backup", updater)
        self.assertIn("run_migrations", updater)
        self.assertIn("rollback_update", updater)
        self.assertIn("database_restore", updater)
        self.assertIn("switch_current_release", updater)
        self.assertIn("local_healthcheck", updater)
        self.assertIn("background_healthcheck", updater)
        self.assertIn("install_service_units", updater)

    def test_checkout_updater_refreshes_runtime_on_same_commit(self):
        updater = self.read("update.sh")
        self.assertIn(
            "Выполняю полное обновление runtime и перезапуск сервисов",
            updater,
        )
        self.assertNotIn("Обновление не требуется.", updater)
        self.assertIn("stop_services", updater)
        self.assertIn("start_services", updater)
        self.assertIn("HTTP healthcheck", updater)

    def test_checkout_updater_selects_compatible_postgresql_client(self):
        updater = self.read("update.sh")
        self.assertIn("SHOW server_version_num", updater)
        self.assertIn("postgresql-client-${server_major}", updater)
        self.assertIn('PG_DUMP_BIN="${path_dump}"', updater)
        self.assertIn('PG_RESTORE_BIN="${path_restore}"', updater)
        self.assertIn('"${PG_DUMP_BIN}"', updater)
        self.assertIn('"${PG_RESTORE_BIN}"', updater)

    def test_release_runtime_does_not_unzip_over_live_tree(self):
        runtime = self.read("deploy/release-lib.sh")
        self.assertIn("RELEASES_DIR", runtime)
        self.assertIn("CURRENT_LINK", runtime)
        self.assertIn("repo_git()", runtime)
        self.assertIn('sudo -H -u "${APP_USER}" git -C "${REPO_DIR}"', runtime)
        self.assertIn("repo_git archive --format=tar", runtime)
        self.assertNotIn("git pull", runtime)

    def test_release_runtime_reads_repository_as_service_account(self):
        runtime = self.read("deploy/release-lib.sh")
        self.assertIn("repo_git fetch --prune --tags origin", runtime)
        self.assertIn('repo_git rev-parse --verify "origin/${ref}^{commit}"', runtime)
        self.assertIn('repo_git show "${commit}:VERSION"', runtime)

    def test_release_runtime_supports_remote_postgresql_backup_restore(self):
        runtime = self.read("deploy/release-lib.sh")
        self.assertIn('PGPASSWORD="${DB_PASSWORD}"', runtime)
        self.assertIn('--host="${DB_HOST}"', runtime)
        self.assertIn('--port="${DB_PORT}"', runtime)
        self.assertIn("--clean", runtime)
        self.assertIn("--if-exists", runtime)


if __name__ == "__main__":
    unittest.main()
