import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class OperatorControlPlaneContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_license_ui_has_registry_issue_and_import_tabs(self):
        template = self.read("templates/dashboard/control_plane/licenses.html")
        self.assertIn("Реестр", template)
        self.assertIn("Выпустить", template)
        self.assertIn("Импорт готовой", template)
        self.assertIn("Новый activation code", template)
        self.assertIn("Папка с ключами на этом ПК", template)
        self.assertIn("Выбрать папку…", template)
        self.assertIn("Проверить ключи", template)
        self.assertIn("last_seen", self.read("models/control_plane.py"))

    def test_release_ui_uses_two_stage_local_signing_flow(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        self.assertIn("Опубликовать", template)
        self.assertIn("version_code", template)
        self.assertIn("min_source_version_code", template)
        self.assertIn("Проверить ZIP и подготовить manifest", template)
        self.assertIn("Подписать на этом ПК и опубликовать", template)

    def test_web_server_never_reads_private_signing_keys(self):
        settings = self.read("settings.py")
        env = self.read("default.env")
        service = self.read("services/notes_control_plane.py")
        views = self.read("views/dashboard/control_plane/views.py")

        self.assertIn("NOTES_OPERATOR_SIGNER_URL", settings)
        self.assertIn("http://127.0.0.1:17843/v1", env)
        self.assertNotIn("NOTES_LOCAL_SIGNING_ENABLED", settings)
        self.assertNotIn("NOTES_SIGNING_KEY_ROOT", settings)
        self.assertNotIn("def _local_signing_key(", service)
        self.assertNotIn("private_key_path", service)
        self.assertNotIn("private_key_path", views)

    def test_local_signer_is_loopback_paired_and_restricted(self):
        router = self.read("tools/operator-signer/router.php")
        self.assertIn("['127.0.0.1', '::1']", router)
        self.assertIn("OPERATOR_SIGNER_TOKEN", router)
        self.assertIn("OPERATOR_SIGNER_ORIGIN", router)
        self.assertIn("/v1/select-directory", router)
        self.assertIn("FolderBrowserDialog", router)
        self.assertIn("/v1/scan", router)
        self.assertIn("/v1/sign-license", router)
        self.assertIn("/v1/sign-manifest", router)
        self.assertNotIn("/v1/sign-raw", router)
        self.assertIn("Private key не соответствует trust root", router)

    def test_browser_sends_local_path_only_to_loopback_signer(self):
        template = self.read("templates/dashboard/control_plane/licenses.html")
        bridge = self.read("templates/dashboard/control_plane/signer.js")
        self.assertIn('id="operator-signer-directory"', template)
        self.assertNotIn('name="operator-signer-directory"', template)
        self.assertIn("credentials: 'omit'", bridge)
        self.assertIn("directory: directory()", bridge)
        self.assertIn("submitHidden", bridge)

    def test_machine_api_records_presence_and_has_heartbeat(self):
        api = self.read("views/notes_api.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn('f"{prefix}/heartbeat"', api)
        self.assertIn('action="heartbeat"', api)
        self.assertIn("def touch_seen(", service)
        self.assertIn("update-feed", api)

    def test_release_zip_is_selected_and_uploaded_from_browser(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        router = self.read("views/dashboard/control_plane/router.py")
        service = self.read("services/notes_control_plane.py")
        nginx = self.read("deploy/checkout/nginx.conf.example")
        self.assertIn('type="file" id="release-package-file"', template)
        self.assertIn("Выбрать ZIP…", template)
        self.assertIn("uploadReleasePackage", template)
        self.assertIn("xhr.send(formData)", template)
        self.assertIn("/api/operator/v1/release-upload", router)
        self.assertIn("def store_release_upload(", service)
        self.assertIn("location = /api/operator/v1/release-upload", nginx)
        self.assertIn("client_max_body_size 520m", nginx)

    def test_release_manifest_is_built_server_side_then_signed_locally(self):
        service = self.read("services/notes_control_plane.py")
        template = self.read("templates/dashboard/control_plane/releases.html")
        self.assertIn("def _build_release_manifest(", service)
        self.assertIn('"sha256": sha256', service)
        self.assertIn('"size": size', service)
        self.assertIn("prepared_manifest", template)
        self.assertNotIn("def publish_release_local(", service)


if __name__ == "__main__":
    unittest.main()
