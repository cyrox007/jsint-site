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
        self.assertIn("Код для 1.0.0/1.0.1", template)
        self.assertIn("Для 1.0.2 и новее этот код не нужен", template)
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

    def test_control_plane_docs_match_browser_license_signing(self):
        docs = self.read("docs/CONTROL_PLANE.md")
        self.assertIn(".license-secret", docs)
        self.assertIn("Web Crypto", docs)
        self.assertIn("Обычный web-интерфейс выпуска лицензий и релизов от него не зависит", docs)
        self.assertNotIn("Для лицензий пока сохраняется отдельный локальный signer", docs)
        self.assertNotIn("нажимает «Выбрать папку…»", docs)

    def test_normal_license_issue_mirrors_update_access_to_license_expiry(self):
        views = self.read("views/dashboard/control_plane/views.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn("updates_follow_license_expiry=True", views)
        self.assertIn("if updates_follow_license_expiry:", service)
        self.assertIn("updates_until = license_expires_at", service)
        self.assertIn("max_version=None", views)

    def test_machine_api_can_bootstrap_updates_from_registered_license(self):
        api = self.read("views/notes_api.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn('license_token = data.get("license_token")', api)
        self.assertIn("NotesControlPlane.activate_with_license(", api)
        self.assertIn("def activate_with_license(", service)
        self.assertIn("hmac.compare_digest(record.signed_license.strip(), token)", service)
        self.assertIn("verify_license_token(token, str(record.installation_id))", service)
        self.assertIn('action="license-bootstrap"', service)
        self.assertIn("activation_code", api)
        self.assertIn("def activate(", service)

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


    def test_control_plane_audit_is_append_only_and_filterable(self):
        model = self.read("models/control_plane.py")
        migration = self.read("alembic/versions/d4e9a61b7c20_control_plane_audit.py")
        service = self.read("services/control_plane_audit.py")
        router = self.read("views/dashboard/control_plane/router.py")
        template = self.read("templates/dashboard/control_plane/audit.html")
        views = self.read("views/dashboard/control_plane/views.py")

        self.assertIn("class ControlPlaneAuditRecord", model)
        self.assertIn("reject_control_plane_audit_mutation", migration)
        self.assertIn("BEFORE UPDATE OR DELETE", migration)
        self.assertIn("ControlPlaneAuditService.list_records", views)
        self.assertIn("admin.control-plane.audit", router)
        self.assertIn("Журнал операций", template)
        self.assertIn("installation_id", service)
        self.assertIn("license_id", service)
        self.assertIn("release_id", service)
        self.assertIn("actor_label", service)
        self.assertNotIn("activation_code", service.split("blocked =", 1)[0])

    def test_dashboard_has_operational_control_plane_metrics(self):
        views = self.read("views/dashboard/main/views.py")
        template = self.read("templates/dashboard/main/index.html")
        service = self.read("services/control_plane_audit.py")

        self.assertIn("ControlPlaneAuditService.dashboard", views)
        self.assertIn("Установки на связи", template)
        self.assertIn("Истекают обновления", template)
        self.assertIn("Ошибки updater", template)
        self.assertIn("Отказы по правам", template)
        self.assertIn("active_installations", service)
        self.assertIn("artifact_errors_24h", service)
        self.assertIn("denied_access_24h", service)

    def test_release_preflight_and_feed_state_are_visible(self):
        views = self.read("views/dashboard/control_plane/views.py")
        template = self.read("templates/dashboard/control_plane/releases.html")

        self.assertIn("def _release_preflight", views)
        self.assertIn("version_code", views)
        self.assertIn("channel_state", views)
        self.assertIn("Текущее состояние update feed", template)
        self.assertIn("Предрелизная проверка остановила выпуск", template)
        self.assertIn("Текущая голова канала", template)
        self.assertIn("Снять с ленты", template)

    def test_machine_api_audits_failed_artifact_access(self):
        api = self.read("views/notes_api.py")
        self.assertIn("ControlPlaneAuditService.machine_failure", api)
        self.assertIn('action="machine.artifact_denied"', api)
        self.assertNotIn("credential=", api)

if __name__ == "__main__":
    unittest.main()
