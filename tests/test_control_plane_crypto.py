from __future__ import annotations

import base64
import json
import os
import tempfile
import time
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from nacl.signing import SigningKey

from config.notes_trust import LICENSE_TRUSTED_KEYS, UPDATE_TRUSTED_KEYS
from services.notes_control_plane import (
    ControlPlaneError,
    NotesControlPlane,
    _build_license_token,
    _build_release_manifest,
    _sign_update_manifest,
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


    def test_local_license_signing_matches_workspace_secret_format(self):
        signing_key = SigningKey.generate()
        key_id = "test-local-license"
        original_enabled = config.NOTES_LOCAL_SIGNING_ENABLED
        original_root = config.NOTES_SIGNING_KEY_ROOT
        previous_public = LICENSE_TRUSTED_KEYS.get(key_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "license.license-secret"
            secret = bytes(signing_key) + bytes(signing_key.verify_key)
            key_path.write_text(
                "wo-ed25519-secret-v1:" + b64url(secret) + "\n",
                encoding="utf-8",
            )
            os.chmod(key_path, 0o600)

            try:
                config.NOTES_LOCAL_SIGNING_ENABLED = True
                config.NOTES_SIGNING_KEY_ROOT = temp_dir
                LICENSE_TRUSTED_KEYS[key_id] = b64url(bytes(signing_key.verify_key))

                installation_id = str(uuid4())
                token = _build_license_token(
                    private_key_path=str(key_path),
                    key_id=key_id,
                    installation_id=installation_id,
                    license_id="lic-local-001",
                    edition="team",
                    expires_at=None,
                    not_before=None,
                    customer="Тестовый клиент",
                    features=["workspace.notes"],
                    max_users=20,
                )
                verified = verify_license_token(token, installation_id)
                self.assertEqual(verified["license_id"], "lic-local-001")
                self.assertEqual(verified["max_users"], 20)
            finally:
                config.NOTES_LOCAL_SIGNING_ENABLED = original_enabled
                config.NOTES_SIGNING_KEY_ROOT = original_root
                if previous_public is None:
                    LICENSE_TRUSTED_KEYS.pop(key_id, None)
                else:
                    LICENSE_TRUSTED_KEYS[key_id] = previous_public

    def test_local_update_signing_builds_verified_manifest(self):
        signing_key = SigningKey.generate()
        key_id = "test-local-update"
        original_enabled = config.NOTES_LOCAL_SIGNING_ENABLED
        original_signing_root = config.NOTES_SIGNING_KEY_ROOT
        original_release_root = config.NOTES_RELEASE_STORAGE_PATH
        previous_public = UPDATE_TRUSTED_KEYS.get(key_id)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            signing_root = root / "signing"
            release_root = root / "releases"
            signing_root.mkdir()
            release_root.mkdir()

            key_path = signing_root / "update.update-secret"
            secret = bytes(signing_key) + bytes(signing_key.verify_key)
            key_path.write_text(
                "wo-update-ed25519-secret-v1:" + b64url(secret) + "\n",
                encoding="utf-8",
            )
            os.chmod(key_path, 0o600)

            package_path = release_root / "workspace-organizer-v1.2.3.zip"
            with zipfile.ZipFile(package_path, "w") as archive:
                archive.writestr("VERSION", "1.2.3\n")

            try:
                config.NOTES_LOCAL_SIGNING_ENABLED = True
                config.NOTES_SIGNING_KEY_ROOT = str(signing_root)
                config.NOTES_RELEASE_STORAGE_PATH = str(release_root)
                UPDATE_TRUSTED_KEYS[key_id] = b64url(bytes(signing_key.verify_key))

                manifest, resolved = _build_release_manifest(
                    package_path=str(package_path),
                    version="1.2.3",
                    version_code=10203,
                    channel="stable",
                    source_commit="a" * 40,
                    min_source_version_code=10200,
                    requires_php="8.1.0",
                )
                self.assertEqual(resolved, package_path.resolve())
                signature = _sign_update_manifest(
                    manifest,
                    private_key_path=str(key_path),
                    key_id=key_id,
                )
                verified = verify_update_manifest(manifest, signature)
                self.assertEqual(verified["version_code"], 10203)
                self.assertEqual(verified["package"]["filename"], package_path.name)
            finally:
                config.NOTES_LOCAL_SIGNING_ENABLED = original_enabled
                config.NOTES_SIGNING_KEY_ROOT = original_signing_root
                config.NOTES_RELEASE_STORAGE_PATH = original_release_root
                if previous_public is None:
                    UPDATE_TRUSTED_KEYS.pop(key_id, None)
                else:
                    UPDATE_TRUSTED_KEYS[key_id] = previous_public

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
