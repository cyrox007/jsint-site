from __future__ import annotations

import importlib.util
import pathlib
import unittest
from unittest.mock import MagicMock, patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "alembic"
    / "versions"
    / "d2f7a91c4e60_admin_notification_preferences.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location(
        "admin_notification_preferences_migration",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить migration module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdminNotificationPreferencesMigrationTests(unittest.TestCase):
    def test_existing_complete_table_is_accepted(self):
        migration = load_migration()
        inspector = MagicMock()
        inspector.get_table_names.return_value = [
            "admin_notification_preferences"
        ]
        inspector.get_columns.return_value = [
            {"name": name}
            for name in sorted(migration._REQUIRED_COLUMNS)
        ]

        with (
            patch.object(migration.op, "get_bind", return_value=object()),
            patch.object(migration.sa, "inspect", return_value=inspector),
            patch.object(migration.op, "create_table") as create_table,
        ):
            migration.upgrade()

        create_table.assert_not_called()

    def test_existing_partial_table_fails_with_clear_error(self):
        migration = load_migration()
        inspector = MagicMock()
        inspector.get_table_names.return_value = [
            "admin_notification_preferences"
        ]
        inspector.get_columns.return_value = [{"name": "id"}]

        with (
            patch.object(migration.op, "get_bind", return_value=object()),
            patch.object(migration.sa, "inspect", return_value=inspector),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "структура неполная",
            ):
                migration.upgrade()

    def test_missing_table_is_created(self):
        migration = load_migration()
        inspector = MagicMock()
        inspector.get_table_names.return_value = []

        with (
            patch.object(migration.op, "get_bind", return_value=object()),
            patch.object(migration.sa, "inspect", return_value=inspector),
            patch.object(migration.op, "create_table") as create_table,
        ):
            migration.upgrade()

        create_table.assert_called_once()


if __name__ == "__main__":
    unittest.main()
