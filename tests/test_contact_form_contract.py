import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ContactFormContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_contact_storage_and_migrations_exist(self):
        model = self.read("models/contact.py")
        base_migration = self.read("alembic/versions/f3b7e91c2a40_contact_messages.py")
        guard_migration = self.read("alembic/versions/a4c8d12e7b60_contact_spam_guard.py")

        self.assertIn('__tablename__ = "contact_messages"', model)
        self.assertIn('down_revision = "e6a1c4d8f930"', base_migration)
        self.assertIn('down_revision = "f3b7e91c2a40"', guard_migration)
        self.assertIn('ForeignKey("sites.id", ondelete="CASCADE")', model)
        self.assertIn("fingerprint", model)
        self.assertIn("unique=True", guard_migration)
        self.assertNotIn("remote_addr", model)
        self.assertNotIn("ip_address", model)

    def test_public_contact_form_has_multiple_security_layers(self):
        view = self.read("views/public/contact/views.py")
        template = self.read("templates/public/contact/index.html")
        guard = self.read("components/security/contact_rate_limit.py")
        headers = self.read("components/security/headers.py")
        settings = self.read("settings.py")

        self.assertIn("ContactSpamGuard.volume_blocked()", view)
        self.assertIn("ContactSpamGuard.record_attempt()", view)
        self.assertIn("ContactSpamGuard.consume_challenge", view)
        self.assertIn("ContactSpamGuard.honeypot_triggered()", view)
        self.assertIn("ContactSpamGuard.content_errors(values)", view)
        self.assertIn("ContactSpamGuard.reply_blocked", view)
        self.assertIn("ContactSpamGuard.verify_turnstile", view)
        self.assertIn("ContactSpamGuard.reserve_fingerprint", view)
        self.assertIn("request.content_length", view)
        self.assertIn("CONTACT_MAX_REQUEST_BYTES", view)
        self.assertIn('name="_csrf_token"', template)
        self.assertIn('name="_contact_nonce"', template)
        self.assertIn('name="website"', template)
        self.assertIn('name="company_site"', template)
        self.assertIn('name="fax_number"', template)
        self.assertIn("cf-turnstile", template)
        self.assertIn("form-action 'self'", headers)
        self.assertIn('request.path == "/contact"', headers)
        self.assertIn('"no-store, private"', headers)
        self.assertIn("CONTACT_DAILY_LIMIT_ATTEMPTS", settings)
        self.assertIn("CONTACT_GLOBAL_LIMIT_ATTEMPTS", settings)
        self.assertIn("CONTACT_DUPLICATE_WINDOW_SECONDS", settings)
        self.assertIn("CONTACT_FORM_MIN_SECONDS", settings)
        self.assertIn("CONTACT_TURNSTILE_REQUIRED", settings)

    def test_spam_checks_happen_before_database_insert(self):
        view = self.read("views/public/contact/views.py")

        insert_at = view.index("db_session.add(")
        checks = (
            "volume_blocked",
            "consume_challenge",
            "honeypot_triggered",
            "content_errors",
            "reply_blocked",
            "verify_turnstile",
            "reserve_fingerprint",
        )
        for check in checks:
            with self.subTest(check=check):
                self.assertLess(view.index(check), insert_at)

    def test_spam_guard_uses_hmac_and_does_not_persist_raw_ip(self):
        guard = self.read("components/security/contact_rate_limit.py")

        self.assertIn("hmac.new", guard)
        self.assertIn("request.remote_addr", guard)
        self.assertIn("_ip_digest", guard)
        self.assertIn("set_if_absent", guard)
        self.assertIn("storage_fingerprint", guard)
        self.assertNotIn("db_session", guard)

    def test_turnstile_is_optional_but_fail_closed_when_enabled(self):
        guard = self.read("components/security/contact_rate_limit.py")
        settings = self.read("settings.py")
        headers = self.read("components/security/headers.py")

        self.assertIn("challenges.cloudflare.com/turnstile/v0/siteverify", guard)
        self.assertIn("return False", guard)
        self.assertIn("CONTACT_TURNSTILE_REQUIRED", settings)
        self.assertIn("CONTACT_TURNSTILE_SITE_KEY", settings)
        self.assertIn("CONTACT_TURNSTILE_SECRET_KEY", settings)
        self.assertIn("https://challenges.cloudflare.com", headers)

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
