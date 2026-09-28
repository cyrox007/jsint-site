import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/d4e9a61b7c20_control_plane_audit.py"


class _Inspector:
    def __init__(self, *, missing: set[str] | None = None):
        required = {
            "id",
            "actor_kind",
            "actor_user_id",
            "actor_label",
            "action",
            "outcome",
            "target_type",
            "target_id",
            "installation_id",
            "license_id",
            "release_id",
            "details",
            "created_at",
        }
        self.columns = required - (missing or set())

    def has_table(self, name):
        return name == "control_plane_audit"

    def get_columns(self, _name):
        return [{"name": name} for name in sorted(self.columns)]

    def get_pk_constraint(self, _name):
        return {"constrained_columns": ["id"]}

    def get_indexes(self, _name):
        return []


class _FakeOp:
    def __init__(self):
        self.created_table = False
        self.created_indexes = []
        self.executed = []

    def get_bind(self):
        return object()

    def create_table(self, *_args, **_kwargs):
        self.created_table = True

    def create_index(self, name, table, columns):
        self.created_indexes.append((name, table, tuple(columns)))

    def execute(self, sql):
        self.executed.append(str(sql))


def _load_migration():
    spec = importlib.util.spec_from_file_location("audit_migration_test", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ControlPlaneAuditMigrationTests(unittest.TestCase):
    def test_existing_compatible_table_is_reused(self):
        module = _load_migration()
        fake_op = _FakeOp()
        inspector = _Inspector()

        module.op = fake_op
        module.sa.inspect = lambda _bind: inspector

        module.upgrade()

        self.assertFalse(fake_op.created_table)
        self.assertEqual(len(fake_op.created_indexes), 10)
        sql = "\n".join(fake_op.executed)
        self.assertIn("CREATE OR REPLACE FUNCTION", sql)
        self.assertIn("DROP TRIGGER IF EXISTS", sql)
        self.assertIn("CREATE TRIGGER", sql)

    def test_existing_incompatible_table_stops_without_recreation(self):
        module = _load_migration()
        fake_op = _FakeOp()
        inspector = _Inspector(missing={"actor_label"})

        module.op = fake_op
        module.sa.inspect = lambda _bind: inspector

        with self.assertRaisesRegex(RuntimeError, "actor_label"):
            module.upgrade()

        self.assertFalse(fake_op.created_table)
        self.assertEqual(fake_op.created_indexes, [])
        self.assertEqual(fake_op.executed, [])


if __name__ == "__main__":
    unittest.main()
