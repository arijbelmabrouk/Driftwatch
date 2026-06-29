import os
import unittest

from notifications.emailer import build_report_email, get_smtp_settings


class EmailerTests(unittest.TestCase):
    def test_build_report_email_contains_recipient_and_report_details(self):
        message = build_report_email(
            recipient="user@example.com",
            topic="transformers",
            report_paths=["/tmp/summary/report.txt"],
            report_text="Latest trend summary",
        )

        self.assertEqual(message["To"], "user@example.com")
        self.assertIn("Driftwatch report", message["Subject"])
        body = message.get_content()
        self.assertIn("transformers", body)
        self.assertIn("Latest trend summary", body)
        self.assertIn("summary/report.txt", body)

    def test_get_smtp_settings_uses_gmail_variables(self):
        original = {key: os.environ.get(key) for key in ["SMTP_SERVER", "SMTP_PORT", "SMTP_USE_TLS", "GMAIL_SENDER_EMAIL", "GMAIL_SENDER_PASSWORD"]}
        try:
            os.environ["SMTP_SERVER"] = "smtp.gmail.com"
            os.environ["SMTP_PORT"] = "587"
            os.environ["SMTP_USE_TLS"] = "true"
            os.environ["GMAIL_SENDER_EMAIL"] = "sender@gmail.com"
            os.environ["GMAIL_SENDER_PASSWORD"] = "secret"

            settings = get_smtp_settings()
            self.assertEqual(settings["host"], "smtp.gmail.com")
            self.assertEqual(settings["port"], 587)
            self.assertTrue(settings["use_tls"])
            self.assertEqual(settings["username"], "sender@gmail.com")
            self.assertEqual(settings["password"], "secret")
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
