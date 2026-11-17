"""Checks for the call-request grammar understood in the orb chat.

The most important assertions here are the negative ones. A sentence that merely contains
the word "call" — "call me a cab", "I'll call you back", "Call of Duty" — is ordinary
conversation and must reach the cloud brain untouched.
"""

import unittest

from weronika_agent.call_intents import (
    has_call_intent,
    parse_call_request,
    parse_channel,
    parse_route,
    telegram_note,
)
from weronika_agent.models import CallChannel, CallRoute


def action(text):
    intent = parse_call_request(text)
    return "" if intent.action == "unhandled" else intent.action


class TurningItOnAndOffTests(unittest.TestCase):
    def test_asking_her_to_handle_calls_switches_watching_on(self):
        for text in (
            "handle my calls",
            "Can you handle my calls?",
            "answer my phone calls for me",
            "take my calls",
            "watch my calls",
            "start handling my calls",
            "call handling on",
            "be my call screener",
        ):
            self.assertEqual(action(text), "enable", text)

    def test_the_same_request_in_hinglish_is_understood(self):
        for text in ("meri calls uthao", "calls sambhalo", "phone uthao", "कॉल उठाओ"):
            self.assertEqual(action(text), "enable", text)

    def test_a_channel_can_be_named(self):
        intent = parse_call_request("handle calls on whatsapp")
        self.assertEqual(intent.action, "enable")
        self.assertEqual(intent.channel, CallChannel.WHATSAPP)
        self.assertEqual(parse_call_request("handle my phone calls").channel, CallChannel.SIM)

    def test_an_audio_route_can_be_named(self):
        intent = parse_call_request("handle my calls on bluetooth")
        self.assertEqual(intent.action, "enable")
        self.assertEqual(intent.route, CallRoute.BLUETOOTH)

    def test_switching_off_is_understood_in_both_verb_forms(self):
        # "don't answer my calls" is a refusal, and must never be read as a request to
        # answer. This is the single most dangerous misreading in the grammar.
        for text in (
            "stop handling my calls",
            "don't answer my calls",
            "do not take my calls",
            "never answer my calls",
            "turn off call handling",
            "call handling off",
        ):
            self.assertEqual(action(text), "disable", text)


class LookingAndCheckingTests(unittest.TestCase):
    def test_looking_for_a_ringing_call(self):
        for text in ("scan calls", "check my calls", "is anyone calling?", "who is calling?",
                     "any calls?", "is the phone ringing", "kaun call kar raha hai"):
            self.assertEqual(action(text), "scan", text)

    def test_asking_about_the_state_of_call_handling(self):
        for text in ("call status", "what calls did you handle", "show me the call summary",
                     "give me the call summary", "call settings"):
            self.assertEqual(action(text), "status", text)

    def test_asking_what_is_plugged_in(self):
        for text in ("is my phone connected", "which phone is connected", "check my call setup",
                     "what audio route for calls", "test my call link"):
            self.assertEqual(action(text), "links", text)

    def test_asking_for_an_example_call(self):
        for text in ("show me an example call", "give me an example of a call",
                     "simulate a call", "demo call", "run a test call", "call demo"):
            self.assertEqual(action(text), "simulate", text)

    def test_an_example_request_can_name_the_channel_it_wants_to_see(self):
        for text in ("show me an example of a whatsapp call", "simulate a whatsapp call",
                     "run the whatsapp call example", "give me an example of a phone call"):
            intent = parse_call_request(text)
            self.assertEqual(intent.action, "simulate", text)
            self.assertIsNotNone(intent.channel, text)
        self.assertEqual(
            parse_call_request("show me an example of a whatsapp call").channel, CallChannel.WHATSAPP
        )
        self.assertEqual(parse_call_request("give me an example of a phone call").channel, CallChannel.SIM)

    def test_an_example_request_without_a_channel_still_runs_one(self):
        self.assertIsNone(parse_call_request("show me an example call").channel)

    def test_ordinary_example_requests_are_not_read_as_call_examples(self):
        for text in ("give me an example of a python function", "show me an example email",
                     "an example of a resume", "run the report example"):
            self.assertEqual(action(text), "", text)


class LiveCallTests(unittest.TestCase):
    def test_answering_her_question(self):
        cases = {
            "you handle it": "weronika",
            "handle it": "weronika",
            "answer it": "weronika",
            "take the call": "weronika",
            "tum utha lo": "weronika",
            "Weronika, you take it": "weronika",
            "I'll take it": "user",
            "i will handle it": "user",
            "let me take it": "user",
            "main uthaunga": "user",
            "ignore it": "ignore",
            "let it ring": "ignore",
            "decline it": "ignore",
            "mat uthao": "ignore",
        }
        for text, decision in cases.items():
            intent = parse_call_request(text)
            self.assertEqual(intent.action, "decide", text)
            self.assertEqual(intent.decision, decision, text)

    def test_taking_the_phone_back(self):
        for text in ("give me the call", "hand it over", "I'm here now", "main aa gaya",
                     "le lo", "phone mujhe do", "pass me the line"):
            self.assertEqual(action(text), "handover", text)

    def test_hanging_up(self):
        for text in ("end the call", "hang up", "cut the call", "kaat do", "band kar do",
                     "disconnect the call"):
            self.assertEqual(action(text), "end", text)

    def test_reporting_what_the_caller_said(self):
        intent = parse_call_request("he said the papers are ready")
        self.assertEqual(intent.action, "hear")
        self.assertEqual(intent.text, "the papers are ready")
        self.assertEqual(parse_call_request("usne kaha shaam ko aayega").action, "hear")

    def test_dictating_your_own_words_with_an_explicit_prefix(self):
        intent = parse_call_request("say: I will call you back in ten minutes")
        self.assertEqual(intent.action, "dictate")
        self.assertEqual(intent.text, "I will call you back in ten minutes")

    def test_dictating_without_a_prefix_needs_a_call_context(self):
        self.assertEqual(action("tell them I am in a meeting on the call"), "dictate")
        # No call context, so this stays ordinary conversation for the cloud brain.
        self.assertEqual(action("say: hello"), "dictate")  # explicit prefix is enough
        self.assertEqual(action("tell mom I am coming"), "")

    def test_insisting_a_code_be_read_out(self):
        self.assertEqual(action("read it out anyway"), "read_secret")
        self.assertEqual(action("say the code anyway"), "read_secret")

    def test_sending_the_summary_on_a_platform(self):
        intent = parse_call_request("send the summary on WhatsApp to Boss")
        self.assertEqual(intent.action, "summary_send")
        self.assertEqual(intent.platform, "whatsapp")
        self.assertEqual(intent.recipient, "Boss")

        telegram = parse_call_request("send the call summary to Rahul on telegram")
        self.assertEqual(telegram.platform, "telegram")
        self.assertEqual(telegram.recipient, "Rahul")

    def test_a_summary_request_without_a_name_still_reports_the_action(self):
        intent = parse_call_request("send the summary on WhatsApp")
        self.assertEqual(intent.action, "summary_send")
        self.assertEqual(intent.recipient, "")


class OrdinaryConversationTests(unittest.TestCase):
    def test_sentences_about_calling_are_not_call_instructions(self):
        for text in (
            "call me a cab",
            "call me an uber",
            "I'll call you back tomorrow",
            "I will call him later",
            "what do you call this?",
            "we call it the blue box",
            "lets play Call of Duty",
            "that is a wake-up call",
            "phone a friend",
        ):
            self.assertEqual(action(text), "", text)
            self.assertFalse(has_call_intent(text), text)

    def test_other_features_are_not_stolen_by_call_handling(self):
        for text in (
            "watch my WhatsApp chat with Boss",
            "send a WhatsApp message to Boss saying call me when free",
            "open WhatsApp",
            "play Kesariya on Spotify",
            "tell me the news",
            "how are you",
            "give me a summary of the report",
            "search for today's weather in Ghaziabad",
        ):
            self.assertEqual(action(text), "", text)

    def test_a_long_paragraph_is_left_to_the_cloud_brain(self):
        self.assertEqual(action("handle my calls " * 60), "")

    def test_an_empty_request_is_not_an_instruction(self):
        self.assertEqual(action(""), "")
        self.assertEqual(action("   "), "")
        self.assertFalse(has_call_intent(""))

    def test_has_call_intent_is_broader_than_the_parser(self):
        # The gate decides whether the worker answers locally; the parser decides what to do.
        self.assertTrue(has_call_intent("handle my calls"))
        self.assertTrue(has_call_intent("say: I will call you back"))
        self.assertFalse(has_call_intent("you handle it"))  # no call word: only live routing
        self.assertFalse(has_call_intent("how are you"))


class ChannelAndRouteParsingTests(unittest.TestCase):
    def test_channels_and_routes_are_named_in_plain_words(self):
        self.assertEqual(parse_channel("on whatsapp"), CallChannel.WHATSAPP)
        self.assertEqual(parse_channel("on the sim"), CallChannel.SIM)
        self.assertEqual(parse_channel("over the cable"), CallChannel.SIM)
        self.assertEqual(parse_channel("nothing relevant"), None)
        self.assertEqual(parse_route("use bluetooth"), CallRoute.BLUETOOTH)
        self.assertEqual(parse_route("through line-in"), CallRoute.AUX)
        self.assertEqual(parse_route("on speaker"), CallRoute.SPEAKER_MIC)
        self.assertEqual(parse_route("nothing relevant"), None)

    def test_the_telegram_answer_is_plain_and_complete(self):
        note = telegram_note()
        self.assertIn("Telegram Web has no calling", note)
        self.assertIn("Bot API", note)
        self.assertIn("WhatsApp Web", note)


if __name__ == "__main__":
    unittest.main()
