from __future__ import annotations

import importlib.util
import pathlib
import unittest
from unittest.mock import Mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "alembic/versions/a91c7e4b2d10_admin_web_push_subscriptions.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("admin_web_push_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AdminWebPushLegacyMigrationTests(unittest.TestCase):
    def test_migration_detects_whether_users_id_can_be_referenced(self):
        migration = MIGRATION_PATH.read_text(encoding="utf-8")

        self.assertIn("get_pk_constraint", migration)
        self.assertIn("get_unique_constraints", migration)
        self.assertIn("users.id", migration)
        self.assertIn("legacy", migration.lower())

    def test_legacy_users_without_unique_id_do_not_get_invalid_foreign_key(self):
        module = load_migration()
        inspector = Mock()
        inspector.get_pk_constraint.return_value = {"constrained_columns": []}
        inspector.get_unique_constraints.return_value = [
            {"name": "ix_users_email", "column_names": ["email"]}
        ]

        self.assertFalse(module._users_id_is_referenceable(inspector))

    def test_normal_users_primary_key_keeps_foreign_key(self):
        module = load_migration()
        inspector = Mock()
        inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
        inspector.get_unique_constraints.return_value = []

        self.assertTrue(module._users_id_is_referenceable(inspector))


if __name__ == "__main__":
    unittest.main()
