from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import time
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from nacl.signing import SigningKey

from app import create_app
from config.notes_trust import LICENSE_TRUSTED_KEYS, UPDATE_TRUSTED_KEYS
from database import Database
from models.control_plane import LicenseRecord, ReleaseRecord
from services.notes_control_plane import NotesControlPlane, _build_release_manifest
from settings import config


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def signed_license(
    signing_key: SigningKey,
    key_id: str,
    installation_id: str,
    *,
    expires_at: int,
) -> str:
    now = int(time.time())
    payload = {
        "v": 1,
        "license_id": "lic-update-e2e-" + installation_id[:8],
        "installation_id": installation_id,
        "issued_at": now - 5,
        "not_before": now - 5,
        "expires_at": expires_at,
        "edition": "standard",
        "features": ["workspace.notes", "workspace.tasks"],
        "max_users": 20,
    }
    encoded = b64url(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    signed = f"wo1.{key_id}.{encoded}"
    signature = signing_key.sign(signed.encode("ascii")).signature
    return f"{signed}.{b64url(signature)}"


class NotesUpdateDeliveryE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()
        cls.base = "https://localhost"

    def setUp(self):
        self.original_control_plane = config.NOTES_CONTROL_PLANE_ENABLED
        self.original_base_url = config.NOTES_UPDATE_BASE_URL
        self.original_release_root = config.NOTES_RELEASE_STORAGE_PATH

        self.temp = tempfile.TemporaryDirectory()
        config.NOTES_CONTROL_PLANE_ENABLED = True
        config.NOTES_UPDATE_BASE_URL = "https://localhost/api/notes/v1/"
        config.NOTES_RELEASE_STORAGE_PATH = self.temp.name

        self.installation_id = str(uuid4())
        self.license_key_id = "test-license-e2e"
        self.update_key_id = "test-update-e2e"
        self.license_key = SigningKey.generate()
        self.update_key = SigningKey.generate()
        LICENSE_TRUSTED_KEYS[self.license_key_id] = b64url(bytes(self.license_key.verify_key))
        UPDATE_TRUSTED_KEYS[self.update_key_id] = b64url(bytes(self.update_key.verify_key))

        expires = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        self.license_token = signed_license(
            self.license_key,
            self.license_key_id,
            self.installation_id,
            expires_at=expires,
        )

        session = Database.connect_database()
        try:
            record = LicenseRecord(
                installation_id=UUID(self.installation_id),
                license_id="lic-update-e2e-" + self.installation_id[:8],
                signed_license=self.license_token,
                key_id=self.license_key_id,
                status="active",
                updates_until=datetime.now(timezone.utc) + timedelta(days=30),
                customer="CI update E2E",
                edition="standard",
                max_users=20,
                features=["workspace.notes", "workspace.tasks"],
                license_not_before=datetime.now(timezone.utc) - timedelta(minutes=1),
                license_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

        self.package_bytes = self._publish_release("1.0.4", 10004, 10003, "1" * 40)

    def tearDown(self):
        session = Database.connect_database()
        try:
            session.query(ReleaseRecord).filter(
                ReleaseRecord.source_commit.in_(["1" * 40, "2" * 40, "3" * 40])
            ).delete(synchronize_session=False)
            session.query(LicenseRecord).filter(
                LicenseRecord.installation_id == UUID(self.installation_id)
            ).delete(synchronize_session=False)
            session.commit()
        finally:
            session.close()

        LICENSE_TRUSTED_KEYS.pop(self.license_key_id, None)
        UPDATE_TRUSTED_KEYS.pop(self.update_key_id, None)
        config.NOTES_CONTROL_PLANE_ENABLED = self.original_control_plane
        config.NOTES_UPDATE_BASE_URL = self.original_base_url
        config.NOTES_RELEASE_STORAGE_PATH = self.original_release_root
        self.temp.cleanup()

    def _publish_release(
        self,
        version: str,
        version_code: int,
        min_source_version_code: int,
        source_commit: str,
    ) -> bytes:
        package_path = Path(self.temp.name) / f"workspace-organizer-v{version}.zip"
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                f"workspace-organizer-v{version}/core/Version.php",
                "<?php\nnamespace Core;\nclass Version {\n"
                f"public const VERSION = '{version}';\n"
                f"public const VERSION_CODE = {version_code};\n"
                "public const STATUS = 'stable';\n"
                "}\n",
            )

        manifest_bytes, resolved = _build_release_manifest(
            package_path=str(package_path),
            version=version,
            version_code=version_code,
            channel="stable",
            source_commit=source_commit,
            min_source_version_code=min_source_version_code,
            requires_php="8.1.0",
        )
        domain = b"WorkspaceOrganizerUpdateManifest/v1\n"
        signature = self.update_key.sign(
            domain + manifest_bytes.encode("utf-8")
        ).signature
        signature_token = f"wou1.{self.update_key_id}.{b64url(signature)}"

        session = Database.connect_database()
        try:
            NotesControlPlane.publish_release(
                session,
                manifest_bytes=manifest_bytes,
                signature=signature_token,
                package_path=str(resolved),
            )
        finally:
            session.close()

        return package_path.read_bytes()

    def _activate_103(self) -> dict:
        response = self.client.post(
            "/api/notes/v1/activate",
            base_url=self.base,
            json={
                "installation_id": self.installation_id,
                "license_token": self.license_token,
                "version": "1.0.3",
                "version_code": 10003,
                "channel": "stable",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["installation_id"], self.installation_id)
        self.assertEqual(payload["base_url"], config.NOTES_UPDATE_BASE_URL)
        self.assertRegex(payload["token"], r"^[0-9a-f]{64}$")
        return payload

    def _headers(
        self,
        credential: str,
        *,
        version: str | None = None,
        version_code: int | None = None,
    ) -> dict[str, str]:
        headers = {
            "Authorization": "Bearer " + credential,
            "X-Notes-Installation": self.installation_id,
        }
        if version is not None:
            headers["X-Notes-Version"] = version
        if version_code is not None:
            headers["X-Notes-Version-Code"] = str(version_code)
        return headers

    def test_active_103_license_receives_complete_signed_104_feed(self):
        activation = self._activate_103()
        headers = self._headers(activation["token"])

        feed_response = self.client.get(
            "/api/notes/v1/stable/feed.json",
            base_url=self.base,
            headers=headers,
        )
        self.assertEqual(feed_response.status_code, 200, feed_response.get_data(as_text=True))
        feed = feed_response.get_json()
        self.assertEqual(feed["schema"], 1)
        self.assertEqual(feed["product"], "workspace-organizer")
        self.assertEqual(feed["channel"], "stable")
        self.assertEqual(feed["manifest"], "release-10004.json")
        self.assertEqual(feed["signature"], "release-10004.sig")

        manifest_response = self.client.get(
            "/api/notes/v1/stable/" + feed["manifest"],
            base_url=self.base,
            headers=headers,
        )
        self.assertEqual(manifest_response.status_code, 200)
        manifest_bytes = manifest_response.get_data(as_text=True)
        manifest = json.loads(manifest_bytes)
        self.assertEqual(manifest["version"], "1.0.4")
        self.assertEqual(manifest["version_code"], 10004)
        self.assertEqual(manifest["min_source_version_code"], 10003)
        self.assertEqual(manifest["channel"], "stable")
        self.assertEqual(manifest["requires_php"], "8.1.0")

        signature_response = self.client.get(
            "/api/notes/v1/stable/" + feed["signature"],
            base_url=self.base,
            headers=headers,
        )
        self.assertEqual(signature_response.status_code, 200)
        self.assertTrue(
            signature_response.get_data(as_text=True).strip().startswith(
                "wou1." + self.update_key_id + "."
            )
        )

        package_name = manifest["package"]["filename"]
        package_response = self.client.get(
            "/api/notes/v1/stable/" + package_name,
            base_url=self.base,
            headers=headers,
        )
        self.assertEqual(package_response.status_code, 200)
        package = package_response.get_data()
        self.assertEqual(package, self.package_bytes)
        self.assertEqual(len(package), manifest["package"]["size"])
        self.assertEqual(hashlib.sha256(package).hexdigest(), manifest["package"]["sha256"])

        session = Database.connect_database()
        try:
            record = session.query(LicenseRecord).filter(
                LicenseRecord.installation_id == UUID(self.installation_id)
            ).one()
            self.assertEqual(record.last_client_version, "1.0.3")
            self.assertEqual(record.last_client_version_code, 10003)
            self.assertEqual(record.last_client_channel, "stable")
            self.assertEqual(record.last_seen_action, "update-package")
        finally:
            session.close()

    def test_feed_returns_latest_release_compatible_with_reported_client_version(self):
        activation = self._activate_103()
        self._publish_release("1.0.5", 10005, 10004, "2" * 40)
        self._publish_release("1.0.6", 10006, 10005, "3" * 40)

        cases = [
            ("1.0.3", 10003, "release-10004.json"),
            ("1.0.4", 10004, "release-10005.json"),
            ("1.0.5", 10005, "release-10006.json"),
            ("1.0.6", 10006, "release-10006.json"),
        ]
        for version, version_code, expected_manifest in cases:
            with self.subTest(version=version):
                response = self.client.get(
                    "/api/notes/v1/stable/feed.json",
                    base_url=self.base,
                    headers=self._headers(
                        activation["token"],
                        version=version,
                        version_code=version_code,
                    ),
                )
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                self.assertEqual(response.get_json()["manifest"], expected_manifest)

        session = Database.connect_database()
        try:
            record = session.query(LicenseRecord).filter(
                LicenseRecord.installation_id == UUID(self.installation_id)
            ).one()
            self.assertEqual(record.last_client_version, "1.0.6")
            self.assertEqual(record.last_client_version_code, 10006)
        finally:
            session.close()

    def test_legacy_client_without_version_headers_keeps_previous_latest_behavior(self):
        activation = self._activate_103()
        self._publish_release("1.0.5", 10005, 10004, "2" * 40)

        response = self.client.get(
            "/api/notes/v1/stable/feed.json",
            base_url=self.base,
            headers=self._headers(activation["token"]),
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["manifest"], "release-10005.json")

    def test_update_access_stops_immediately_when_entitlement_expires(self):
        activation = self._activate_103()
        session = Database.connect_database()
        try:
            record = session.query(LicenseRecord).filter(
                LicenseRecord.installation_id == UUID(self.installation_id)
            ).one()
            record.updates_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.add(record)
            session.commit()
        finally:
            session.close()

        response = self.client.get(
            "/api/notes/v1/stable/feed.json",
            base_url=self.base,
            headers=self._headers(activation["token"]),
        )
        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload["error"], "update_access_denied")


if __name__ == "__main__":
    unittest.main()
