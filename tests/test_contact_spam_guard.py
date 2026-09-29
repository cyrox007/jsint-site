import unittest
from unittest.mock import patch

from flask import Flask

from components.security.contact_rate_limit import ContactSpamGuard
from settings import config


class ContactSpamGuardTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "contact-spam-guard-tests-secret-key-123456"

    def test_challenge_is_time_bound_and_one_time(self):
        with self.app.test_request_context("/contact", method="POST"):
            with (
                patch.object(config, "CONTACT_FORM_MIN_SECONDS", 3),
                patch.object(config, "CONTACT_FORM_TTL_SECONDS", 30),
                patch(
                    "components.security.contact_rate_limit.time.time",
                    return_value=1000,
                ),
            ):
                nonce = ContactSpamGuard.issue_challenge()

            with patch(
                "components.security.contact_rate_limit.time.time",
                return_value=1004,
            ):
                self.assertTrue(ContactSpamGuard.consume_challenge(nonce))
                self.assertFalse(ContactSpamGuard.consume_challenge(nonce))

    def test_challenge_rejects_too_fast_and_expired_submissions(self):
        with self.app.test_request_context("/contact", method="POST"):
            with (
                patch.object(config, "CONTACT_FORM_MIN_SECONDS", 3),
                patch.object(config, "CONTACT_FORM_TTL_SECONDS", 30),
                patch(
                    "components.security.contact_rate_limit.time.time",
                    return_value=1000,
                ),
            ):
                nonce = ContactSpamGuard.issue_challenge()
            with patch(
                "components.security.contact_rate_limit.time.time",
                return_value=1001,
            ):
                self.assertFalse(ContactSpamGuard.consume_challenge(nonce))

        with self.app.test_request_context("/contact", method="POST"):
            with (
                patch.object(config, "CONTACT_FORM_MIN_SECONDS", 3),
                patch.object(config, "CONTACT_FORM_TTL_SECONDS", 30),
                patch(
                    "components.security.contact_rate_limit.time.time",
                    return_value=1000,
                ),
            ):
                nonce = ContactSpamGuard.issue_challenge()
            with patch(
                "components.security.contact_rate_limit.time.time",
                return_value=1031,
            ):
                self.assertFalse(ContactSpamGuard.consume_challenge(nonce))

    def test_honeypots_detect_automated_fill(self):
        with self.app.test_request_context(
            "/contact",
            method="POST",
            data={"company_site": "https://spam.example"},
        ):
            self.assertTrue(ContactSpamGuard.honeypot_triggered())

        with self.app.test_request_context(
            "/contact",
            method="POST",
            data={"website": "", "company_site": "", "fax_number": ""},
        ):
            self.assertFalse(ContactSpamGuard.honeypot_triggered())

    def test_content_filter_rejects_link_flood_and_hidden_text(self):
        values = {
            "name": "Test",
            "reply_to": "test@example.com",
            "subject": "",
            "message": "Нормальный текст https://a.example https://b.example https://c.example",
        }
        with patch.object(config, "CONTACT_MAX_URLS", 2):
            errors = ContactSpamGuard.content_errors(values)
        self.assertTrue(any("слишком много ссылок" in item for item in errors))

        values["message"] = "Нормальный текст с невидимыми символами\u200b\u200b\u200b"
        errors = ContactSpamGuard.content_errors(values)
        self.assertTrue(any("скрытые символы" in item for item in errors))

    def test_content_fingerprint_is_case_insensitive_and_hmac_based(self):
        values = {
            "name": "Test",
            "reply_to": "User@Example.com",
            "subject": "Тема",
            "message": "Сообщение для проверки отпечатка",
        }
        changed = dict(values)
        changed["reply_to"] = "user@example.com"
        changed["subject"] = "тема"
        changed["message"] = "сообщение для проверки отпечатка"

        with patch.object(config, "SECRET_KEY", "unit-test-contact-secret"):
            first = ContactSpamGuard.fingerprint(values)
            second = ContactSpamGuard.fingerprint(changed)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        self.assertNotIn(values["reply_to"].lower(), first)


if __name__ == "__main__":
    unittest.main()
