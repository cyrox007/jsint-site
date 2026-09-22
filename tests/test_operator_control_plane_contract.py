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
        self.assertIn("last_seen", self.read("models/control_plane.py"))

    def test_release_ui_has_operator_publish_flow(self):
        template = self.read("templates/dashboard/control_plane/releases.html")
        self.assertIn("Опубликовать", template)
        self.assertIn("version_code", template)
        self.assertIn("min_source_version_code", template)
        self.assertIn("Подготовить manifest для офлайн-подписи", template)
        self.assertIn("Собрать, подписать и опубликовать", template)

    def test_local_signing_is_opt_in_and_path_is_not_persisted(self):
        settings = self.read("settings.py")
        env = self.read("default.env")
        model = self.read("models/control_plane.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn('NOTES_LOCAL_SIGNING_ENABLED = _env_bool("NOTES_LOCAL_SIGNING_ENABLED", False)', settings)
        self.assertIn("NOTES_LOCAL_SIGNING_ENABLED=false", env)
        self.assertIn("NOTES_SIGNING_KEY_ROOT", settings)
        self.assertNotIn("private_key_path:", model)
        self.assertIn('resolved.stat().st_mode & 0o077', service)
        self.assertIn("Private key не соответствует выбранному public trust root", service)

    def test_machine_api_records_presence_and_has_heartbeat(self):
        api = self.read("views/notes_api.py")
        service = self.read("services/notes_control_plane.py")
        self.assertIn('f"{prefix}/heartbeat"', api)
        self.assertIn('action="heartbeat"', api)
        self.assertIn("def touch_seen(", service)
        self.assertIn("update-feed", api)

    def test_release_manifest_is_built_from_operator_fields(self):
        service = self.read("services/notes_control_plane.py")
        self.assertIn("def _build_release_manifest(", service)
        self.assertIn('"sha256": sha256', service)
        self.assertIn('"size": size', service)
        self.assertIn("def publish_release_local(", service)


if __name__ == "__main__":
    unittest.main()
