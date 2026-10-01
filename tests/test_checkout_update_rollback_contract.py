from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CheckoutUpdateRollbackContractTests(unittest.TestCase):
    def test_checkout_updater_bootstraps_target_script(self):
        script = (ROOT / "update.sh").read_text(encoding="utf-8")

        self.assertIn("JSINT_UPDATER_BOOTSTRAPPED", script)
        self.assertIn('git show "${TARGET_COMMIT}:update.sh"', script)
        self.assertIn("Перезапуск updater из target commit", script)
        self.assertIn("flock -u 9", script)
        self.assertIn("JSINT_UPDATER_BOOTSTRAP_FILE", script)

    def test_checkout_rollback_recreates_local_database(self):
        script = (ROOT / "update.sh").read_text(encoding="utf-8")

        self.assertIn(
            'sudo -u postgres dropdb --if-exists "${DB_NAME}"',
            script,
        )
        self.assertIn(
            'sudo -u postgres createdb --owner="${DB_USER}" "${DB_NAME}"',
            script,
        )
        self.assertIn(
            "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;",
            script,
        )

    def test_checkout_rollback_skips_database_before_migrations(self):
        script = (ROOT / "update.sh").read_text(encoding="utf-8")

        self.assertIn("MIGRATIONS_STARTED=0", script)
        self.assertIn(
            'if (( MIGRATIONS_STARTED == 0 )); then',
            script,
        )
        self.assertIn(
            "Миграции БД не запускались — PostgreSQL rollback не требуется.",
            script,
        )
        self.assertIn(
            'MIGRATIONS_STARTED=1',
            script,
        )

    def test_checkout_rollback_verifies_alembic_revision(self):
        script = (ROOT / "update.sh").read_text(encoding="utf-8")

        self.assertIn(
            'EXPECTED_DB_HEAD="$("${APP_DIR}/.venv/bin/alembic" heads',
            script,
        )
        self.assertIn(
            'CURRENT_DB_HEAD="$("${APP_DIR}/.venv/bin/alembic" current',
            script,
        )
        self.assertIn("PostgreSQL snapshot не восстановлен", script)
        self.assertIn("revision БД после restore не совпадает", script)
        self.assertIn("Старый runtime не запускается", script)


if __name__ == "__main__":
    unittest.main()
