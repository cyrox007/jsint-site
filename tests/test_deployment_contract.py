import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DeploymentContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_version_exists(self):
        version = self.read("VERSION").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

    def test_systemd_uses_atomic_current_release(self):
        unit = self.read("deploy/jsint-site.service")
        self.assertIn("WorkingDirectory=/opt/jsint-site/current", unit)
        self.assertIn("/opt/jsint-site/current/.venv/bin/gunicorn", unit)
        self.assertNotIn("WorkingDirectory=/opt/jsint-site\n", unit)

    def test_installer_is_clean_install_only(self):
        installer = self.read("deploy/install.sh")
        self.assertIn("Используйте deploy/update.sh", installer)
        self.assertIn("SECRET_KEY=", installer)
        self.assertIn("DB_PASSWORD=", installer)
        self.assertIn("run_migrations", installer)
        self.assertIn("run_release_tests", installer)
        self.assertIn("local_healthcheck", installer)

    def test_updater_requires_backup_migration_and_rollback(self):
        updater = self.read("deploy/update.sh")
        self.assertIn("--yes", updater)
        self.assertIn("database_backup", updater)
        self.assertIn("run_migrations", updater)
        self.assertIn("rollback_update", updater)
        self.assertIn("database_restore", updater)
        self.assertIn("switch_current_release", updater)
        self.assertIn("local_healthcheck", updater)

    def test_release_runtime_does_not_unzip_over_live_tree(self):
        runtime = self.read("deploy/release-lib.sh")
        self.assertIn("RELEASES_DIR", runtime)
        self.assertIn("CURRENT_LINK", runtime)
        self.assertIn("git -C", runtime)
        self.assertIn("archive --format=tar", runtime)
        self.assertNotIn("git pull", runtime)


if __name__ == "__main__":
    unittest.main()
