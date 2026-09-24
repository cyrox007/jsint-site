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
        self.assertIn('id="license-signing-key-file"', template)
        self.assertIn("Выбрать файл ключа…", template)
        self.assertIn("Выпустить лицензию", template)
        self.assertIn("Владелец лицензии", template)
        self.assertNotIn("Название клиента", template)
        self.assertIn('id="license-not-before"', template)
        self.assertIn('id="license-expires-at"', template)
        self.assertIn("Доступ к обновлениям автоматически действует до даты окончания лицензии", template)
        self.assertNotIn("Код подключения local signer", template)
        self.assertNotIn("Выбрать папку…", template)
        self.assertNotIn("Проверить ключи", template)
        self.assertIn("last_seen", self.read("models/control_plane.py"))

    def test_release_ui_uses_single_form_browser_signing(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        self.assertIn('id="release-one-click-form"', template)
        self.assertIn('id="release-update-key-file"', template)
        self.assertIn("Выпустить релиз", template)
        self.assertIn("crypto.subtle", template)
        self.assertIn("wo-update-ed25519-secret-v1:", template)
        self.assertIn("indexedDB", template)
        self.assertIn("privateKey: key.privateKey", template)
        self.assertNotIn("showOpenFilePicker", template)
        self.assertNotIn("Код подключения local signer", template)
        self.assertNotIn("Расширенный импорт</a>", template)

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

    def test_license_private_key_is_used_only_in_browser(self):
        template = self.read("templates/dashboard/control_plane/licenses.html")
        self.assertIn('id="license-signing-key-file"', template)
        self.assertNotIn('name="license-signing-key-file"', template)
        self.assertIn("wo-ed25519-secret-v1:", template)
        self.assertIn("crypto.subtle.importKey", template)
        self.assertIn("crypto.subtle.sign", template)
        self.assertIn("indexedDB", template)
        self.assertIn("privateKey: key.privateKey", template)
        self.assertIn("license_trusted_keys|tojson", template)
        self.assertIn('name="signed_license"', template)
        self.assertIn("addOneCalendarYear", template)
        self.assertIn("standardFeatures", template)
        self.assertIn('accept=".license-secret"', template)
        self.assertIn('id="license-signing-key-name"', template)
        self.assertIn('id="license-issue-submit"', template)
        self.assertNotIn("OperatorSigner.", template)
        self.assertNotIn("signer.js", template)

    def test_normal_license_issue_mirrors_update_access_to_license_expiry(self):
        views = self.read("views/dashboard/control_plane/views.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn("updates_follow_license_expiry=True", views)
        self.assertIn("if updates_follow_license_expiry:", service)
        self.assertIn("updates_until = license_expires_at", service)
        self.assertIn("max_version=None", views)

    def test_machine_api_records_presence_and_has_heartbeat(self):
        api = self.read("views/notes_api.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn('f"{prefix}/heartbeat"', api)
        self.assertIn('action="heartbeat"', api)
        self.assertIn("def touch_seen(", service)
        self.assertIn("update-feed", api)

    def test_release_zip_is_downloaded_from_github_for_normal_flow(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        router = self.read("views/dashboard/control_plane/router.py")
        service = self.read("services/github_release_automation.py")
        self.assertNotIn('id="release-package-file"', template)
        self.assertNotIn("Выбрать ZIP…", template)
        self.assertIn('f"{prefix}/releases/github"', router)
        self.assertIn("_download_package", service)
        self.assertIn("api.github.com", service)

    def test_release_ui_has_one_click_github_preparation(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        router = self.read("views/dashboard/control_plane/router.py")
        service = self.read("services/github_release_automation.py")
        settings = self.read("settings.py")

        self.assertIn("Обычный выпуск", template)
        self.assertIn("GitHub → подпись → публикация", template)
        self.assertIn("admin.releases.github", template)
        self.assertIn('f"{prefix}/releases/github"', router)
        self.assertIn("GitHubReleaseAutomation", service)
        self.assertIn("workspace-organizer-", service)
        self.assertIn(".sha256", service)
        self.assertIn(".source-sha", service)
        self.assertIn("api.github.com", service)
        self.assertIn("NOTES_RELEASE_GITHUB_REPOSITORY", settings)
        self.assertNotIn("private signing key", service.lower())

    def test_release_manifest_is_built_server_side_then_signed_in_browser(self):
        service = self.read("services/notes_control_plane.py")
        template = self.read("templates/dashboard/control_plane/releases.html")
        self.assertIn("def _build_release_manifest(", service)
        self.assertIn('"sha256": sha256', service)
        self.assertIn('"size": size', service)
        self.assertIn("signManifest", template)
        self.assertIn("release.manifest", template)
        self.assertNotIn("def publish_release_local(", service)

    def test_signed_manifest_is_published_as_json_without_form_normalization(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        views = self.read("views/dashboard/control_plane/views.py")
        self.assertIn("'Content-Type': 'application/json'", template)
        self.assertIn("JSON.stringify({", template)
        self.assertIn("manifest_bytes: release.manifest", template)
        self.assertNotIn("publishForm.submit()", template)
        self.assertIn("json_mode = request.is_json", views)
        self.assertIn('manifest_bytes = str(payload.get("manifest_bytes", ""))', views)


if __name__ == "__main__":
    unittest.main()
