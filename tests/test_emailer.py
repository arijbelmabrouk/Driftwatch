import unittest

from notifications.emailer import build_report_email


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


if __name__ == "__main__":
    unittest.main()
