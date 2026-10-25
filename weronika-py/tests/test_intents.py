import unittest

from weronika_agent.intents import parse_message_request
from weronika_agent.models import Platform


class IntentParsingTests(unittest.TestCase):
    def test_whatsapp_example(self):
        result = parse_message_request("Send a message on WhatsApp to Boss that I will be on leave tomorrow")
        self.assertTrue(result.handled)
        self.assertEqual(result.platform, Platform.WHATSAPP)
        self.assertEqual(result.recipient, "Boss")
        self.assertEqual(result.message, "I will be on leave tomorrow")

    def test_telegram_message_with_colon(self):
        result = parse_message_request("Message Alex on Telegram: I'll call at 5:30.")
        self.assertEqual(result.platform, Platform.TELEGRAM)
        self.assertEqual(result.recipient, "Alex")
        self.assertEqual(result.message, "I'll call at 5:30.")

    def test_instagram_handle(self):
        result = parse_message_request("DM @sam.lee on Instagram saying Hi, are we still on for lunch?")
        self.assertEqual(result.platform, Platform.INSTAGRAM)
        self.assertEqual(result.recipient, "@sam.lee")
        self.assertEqual(result.message, "Hi, are we still on for lunch?")

    def test_smart_quoted_message_is_unwrapped(self):
        result = parse_message_request("Send WhatsApp to Boss saying “See you soon.”")
        self.assertEqual(result.message, "See you soon.")

    def test_missing_body_requests_exact_text(self):
        result = parse_message_request("Send a WhatsApp message to Boss")
        self.assertTrue(result.handled)
        self.assertEqual(result.recipient, "")
        self.assertIn("exact message", result.prompt)

    def test_ordinary_chat_is_not_messaging_intent(self):
        self.assertFalse(parse_message_request("Send me a joke").handled)

    def test_each_supported_platform(self):
        cases = [
            ("Send Telegram to Sam saying hello", Platform.TELEGRAM),
            ("Send an Instagram message to Sam saying hello", Platform.INSTAGRAM),
            ("Send Facebook message to Sam saying hello", Platform.FACEBOOK),
            ("Send a message on X to @sam saying hello", Platform.X),
        ]
        for text, platform in cases:
            with self.subTest(platform=platform):
                self.assertEqual(parse_message_request(text).platform, platform)


if __name__ == "__main__":
    unittest.main()
