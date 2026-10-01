from __future__ import annotations

import base64
import io
import json
import tempfile
import time
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from nacl.signing import SigningKey

from services.github_release_automation import _inspect_workspace_zip, _source_floor_for_version
from services.notes_control_plane import (
    ControlPlaneError,
    NotesControlPlane,
    _build_release_manifest,
    verify_license_token,
    verify_update_manifest,
)
from settings import config


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class ControlPlaneCryptoContractTest(unittest.TestCase):
    def test_workspace_license_token_contract(self):
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key
        key_id = "test-license"
        installation_id = str(uuid4())

        payload = {
            "v": 1,
            "license_id": "lic-test-001",
            "installation_id": installation_id,
            "issued_at": int(time.time()) - 5,
            "expires_at": None,
            "edition": "standard",
            "features": ["workspace.notes", "workspace.tasks"],
            "max_users": 20,
        }
        payload_encoded = b64url(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        )
        signed = f"wo1.{key_id}.{payload_encoded}"
        signature = signing_key.sign(signed.encode("ascii")).signature
        token = f"{signed}.{b64url(signature)}"

        verified = verify_license_token(
            token,
            installation_id,
            trusted_keys={key_id: b64url(bytes(verify_key))},
        )
        self.assertEqual(verified["license_id"], "lic-test-001")
        self.assertEqual(verified["installation_id"], installation_id)
        self.assertEqual(verified["_key_id"], key_id)

        with self.assertRaises(ControlPlaneError) as raised:
            verify_license_token(
                token,
                str(uuid4()),
                trusted_keys={key_id: b64url(bytes(verify_key))},
            )
        self.assertEqual(raised.exception.code, "wrong_installation")

    def test_workspace_update_manifest_signature_contract(self):
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key
        key_id = "test-update"

        manifest = {
            "schema": 1,
            "product": "workspace-organizer",
            "version": "1.0.2",
            "version_code": 10002,
            "channel": "stable",
            "issued_at": int(time.time()) - 5,
            "source_commit": "a" * 40,
            "min_source_version_code": 10001,
            "requires_php": "8.1.0",
            "package": {
                "filename": "workspace-organizer-v1.0.2.zip",
                "sha256": "b" * 64,
                "size": 12345,
                "format": "zip",
            },
        }
        manifest_bytes = json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            separators=(",", ": "),
        ) + "\n"
        domain = b"WorkspaceOrganizerUpdateManifest/v1\n"
        signature = signing_key.sign(domain + manifest_bytes.encode("utf-8")).signature
        signature_token = f"wou1.{key_id}.{b64url(signature)}"

        verified = verify_update_manifest(
            manifest_bytes,
            signature_token,
            trusted_keys={key_id: b64url(bytes(verify_key))},
        )
        self.assertEqual(verified["version_code"], 10002)
        self.assertEqual(verified["channel"], "stable")
        self.assertEqual(verified["_key_id"], key_id)

        tampered = manifest_bytes.replace('"version_code": 10002', '"version_code": 10003')
        with self.assertRaises(ControlPlaneError) as raised:
            verify_update_manifest(
                tampered,
                signature_token,
                trusted_keys={key_id: b64url(bytes(verify_key))},
            )
        self.assertEqual(raised.exception.code, "invalid_signature")

    def test_release_manifest_is_built_from_server_zip(self):
        original_release_root = config.NOTES_RELEASE_STORAGE_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            release_root = Path(temp_dir)
            package_path = release_root / "workspace-organizer-v1.2.3.zip"
            with zipfile.ZipFile(package_path, "w") as archive:
                archive.writestr("VERSION", "1.2.3\n")

            try:
                config.NOTES_RELEASE_STORAGE_PATH = str(release_root)
                manifest_bytes, resolved = _build_release_manifest(
                    package_path=str(package_path),
                    version="1.2.3",
                    version_code=10203,
                    channel="stable",
                    source_commit="a" * 40,
                    min_source_version_code=10200,
                    requires_php="8.1.0",
                )
                manifest = json.loads(manifest_bytes)
                self.assertEqual(resolved, package_path.resolve())
                self.assertEqual(manifest["version_code"], 10203)
                self.assertEqual(manifest["package"]["filename"], package_path.name)
                self.assertGreater(manifest["package"]["size"], 0)
                self.assertRegex(manifest["package"]["sha256"], r"^[0-9a-f]{64}$")
            finally:
                config.NOTES_RELEASE_STORAGE_PATH = original_release_root

    def test_github_release_package_version_is_read_from_zip(self):
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr(
                "workspace-organizer-v1.0.1/core/Version.php",
                "<?php\nclass Version {\n"
                "public const VERSION = '1.0.1';\n"
                "public const VERSION_CODE = 10001;\n"
                "public const STATUS = 'stable';\n"
                "}\n",
            )
        package.seek(0)

        meta = _inspect_workspace_zip(package)
        self.assertEqual(meta["version"], "1.0.1")
        self.assertEqual(meta["version_code"], 10001)
        self.assertEqual(meta["status"], "stable")
        self.assertEqual(_source_floor_for_version(meta["version_code"]), 10000)
        self.assertEqual(_source_floor_for_version(10005), 10003)
        self.assertEqual(_source_floor_for_version(10006), 10005)
        self.assertEqual(_source_floor_for_version(10042), 10041)
        self.assertEqual(_source_floor_for_version(10100), 10099)

    def test_presence_is_based_on_last_outbound_contact(self):
        now = datetime.now(timezone.utc)

        unknown = NotesControlPlane.presence(SimpleNamespace(last_seen_at=None), now=now)
        online = NotesControlPlane.presence(
            SimpleNamespace(last_seen_at=now - timedelta(minutes=5)),
            now=now,
        )
        recent = NotesControlPlane.presence(
            SimpleNamespace(last_seen_at=now - timedelta(hours=2)),
            now=now,
        )
        offline = NotesControlPlane.presence(
            SimpleNamespace(last_seen_at=now - timedelta(days=2)),
            now=now,
        )

        self.assertEqual(unknown["code"], "unknown")
        self.assertEqual(online["code"], "online")
        self.assertEqual(recent["code"], "recent")
        self.assertEqual(offline["code"], "offline")


if __name__ == "__main__":
    unittest.main()
