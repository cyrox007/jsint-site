import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ContactFormContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_contact_storage_and_migration_exist(self):
        model = self.read("models/contact.py")
        migration = self.read("alembic/versions/f3b7e91c2a40_contact_messages.py")

        self.assertIn('__tablename__ = "contact_messages"', model)
        self.assertIn('down_revision = "e6a1c4d8f930"', migration)
        self.assertIn('ForeignKey("sites.id", ondelete="CASCADE")', model)
        self.assertNotIn("remote_addr", model)
        self.assertNotIn("ip_address", model)

    def test_public_contact_form_has_security_layers(self):
        view = self.read("views/public/contact/views.py")
        template = self.read("templates/public/contact/index.html")
        limiter = self.read("components/security/contact_rate_limit.py")
        headers = self.read("components/security/headers.py")

        self.assertIn("ContactRateLimiter.blocked()", view)
        self.assertIn("ContactRateLimiter.record_submission()", view)
        self.assertIn('request.form.get("website"', view)
        self.assertIn('name="_csrf_token"', template)
        self.assertIn('name="website"', template)
        self.assertIn('form-action \'self\'', headers)
        self.assertIn('request.path == "/contact"', headers)
        self.assertIn('"no-store, private"', headers)
        self.assertIn("sha256", limiter)

    def test_public_ui_exposes_no_direct_git_or_email_links(self):
        paths = [
            "templates/public/^shared/header/index.html",
            "templates/public/^shared/footer/index.html",
            "templates/public/home/section/hero.html",
        ]
        text = "\n".join(self.read(path) for path in paths).lower()

        self.assertNotIn("mailto:", text)
        self.assertNotIn("github", text)
        self.assertNotIn("gitlab", text)
        self.assertNotIn("bitbucket", text)
        self.assertNotIn("codeberg", text)
        self.assertIn("url_for('contact')", text)

    def test_public_site_config_hides_legacy_contacts_and_git_navigation(self):
        service = self.read("services/site.py")

        self.assertIn('settings["contact"] = {}', service)
        self.assertIn("PUBLIC_BLOCKED_LINK_HOSTS", service)
        self.assertIn('"github.com"', service)
        self.assertIn('"gitlab.com"', service)
        self.assertIn('"bitbucket.org"', service)
        self.assertIn('"codeberg.org"', service)

    def test_contact_inbox_is_admin_only(self):
        router = self.read("views/dashboard/contact/router.py")
        view = self.read("views/dashboard/contact/views.py")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")

        self.assertIn("config.ADMIN_ROUTE_PREFIX", router)
        self.assertIn("@login_required", view)
        self.assertIn("ContactMessage.site_id == site.id", view)
        self.assertIn("<span>Обращения</span>", sidebar)

    def test_legacy_contact_fields_are_removed_from_site_editor(self):
        template = self.read("templates/dashboard/sites/edit.html")
        controller = self.read("views/dashboard/sites/views.py")

        self.assertNotIn('name="contact_email"', template)
        self.assertNotIn('name="github_url"', template)
        self.assertNotIn('name="hero_github_label"', template)
        self.assertNotIn('request.form.get("contact_email"', controller)
        self.assertNotIn('request.form.get("github_url"', controller)


if __name__ == "__main__":
    unittest.main()
