from __future__ import annotations

import base64
import json
import time
import unittest
from uuid import uuid4

from nacl.signing import SigningKey

from services.notes_control_plane import (
    ControlPlaneError,
    verify_license_token,
    verify_update_manifest,
)


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


if __name__ == "__main__":
    unittest.main()
