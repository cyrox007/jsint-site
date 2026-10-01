from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pathlib
import unittest

from services.notes_control_plane import NotesControlPlane


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FakeQuery:
    def __init__(self, deleted: int = 0):
        self.deleted = deleted
        self.filters = ()

    def filter(self, *filters):
        self.filters = filters
        return self

    def delete(self, *, synchronize_session: bool):
        if synchronize_session is not False:
            raise AssertionError("Очистка не должна синхронизировать загруженные ORM-объекты")
        return self.deleted


class FakeSession:
    def __init__(self, deleted: int = 0):
        self.query_object = FakeQuery(deleted)
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def query(self, _model):
        return self.query_object


class LicenseCleanupContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_revocation_sets_timestamp_once_and_activation_clears_it(self):
        session = FakeSession()
        record = SimpleNamespace(
            status="active",
            revoked_at=None,
            credential_hash="credential",
            activation_hash="activation",
        )

        NotesControlPlane.set_status(session, record, "revoked")

        self.assertEqual(record.status, "revoked")
        self.assertIsNotNone(record.revoked_at)
        first_revoked_at = record.revoked_at
        self.assertIsNone(record.credential_hash)
        self.assertIsNone(record.activation_hash)

        NotesControlPlane.set_status(session, record, "revoked")
        self.assertEqual(record.revoked_at, first_revoked_at)

        NotesControlPlane.set_status(session, record, "active")
        self.assertEqual(record.status, "active")
        self.assertIsNone(record.revoked_at)

    def test_purge_deletes_matching_rows_and_commits(self):
        session = FakeSession(deleted=2)
        now = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)

        deleted = NotesControlPlane.purge_revoked_licenses(session, now=now)

        self.assertEqual(deleted, 2)
        self.assertEqual(session.commits, 1)
        self.assertEqual(session.rollbacks, 0)
        self.assertEqual(len(session.query_object.filters), 3)

    def test_retention_and_scheduler_are_wired(self):
        settings = self.read("settings.py")
        celery = self.read("celery_app.py")
        tasks = self.read("tasks/system.py")
        migration = self.read("alembic/versions/b7d4e2f190ab_license_revoked_retention.py")

        self.assertIn('LICENSE_REVOKED_RETENTION_DAYS", "30"', settings)
        self.assertIn("max(\n        30,", settings)
        self.assertIn('"purge-revoked-license-keys-daily"', celery)
        self.assertIn('"tasks.system.purge_revoked_license_keys"', celery)
        self.assertIn("crontab(hour=3, minute=17)", celery)
        self.assertIn("def purge_revoked_license_keys()", tasks)
        self.assertIn("revoked_at = updated_at", migration)
        self.assertIn("ix_license_registry_revoked_at", migration)


if __name__ == "__main__":
    unittest.main()
