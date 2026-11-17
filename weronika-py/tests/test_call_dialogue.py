"""Checks for what Weronika says on a call, and what she refuses to say.

The brain responder is tested against a tiny local HTTP server that behaves like the
hosted brain, so the "did the brain really write this line?" rule is checked rather than
assumed.
"""

import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from weronika_agent.call_dialogue import (
    DISCLOSURE_CONFIRMATION,
    DISCLOSURE_TEMPLATE,
    SECRET_REFUSAL,
    UNSUPPORTED_REQUEST,
    SpokenLine,
    build_brain_responder,
    caller_asks_for_human,
    caller_is_done,
    detect_secret,
    fallback_line,
    fill,
    looks_like_hinglish,
    mentions_decision,
    mentions_spam,
    owner_words,
    redact_secrets,
    summary_lines,
    RE_DISCLOSURE_QUESTION,
)


class DisclosureTests(unittest.TestCase):
    def test_the_opening_line_names_the_owner_and_says_ai_not_human(self):
        line = fill(DISCLOSURE_TEMPLATE, "Keshav")
        self.assertIn("Keshav's phone", line)
        self.assertIn("Weronika", line)
        self.assertIn("AI assistant", line)
        self.assertIn("not a human", line)

    def test_a_name_ending_in_s_does_not_read_oddly(self):
        words = owner_words("Das")
        self.assertEqual(words["owner_possessive"], "Das'")
        self.assertIn("Das' phone", fill(DISCLOSURE_TEMPLATE, "Das"))

    def test_with_no_owner_name_the_line_still_makes_sense(self):
        line = fill(DISCLOSURE_TEMPLATE, "")
        self.assertIn("the owner of this phone", line)
        self.assertIn("not a human", line)

    def test_asking_again_gets_the_same_honest_answer(self):
        line = fill(DISCLOSURE_CONFIRMATION, "Keshav")
        self.assertIn("I am an AI assistant", line)
        self.assertIn("not a human being", line)

    def test_the_question_is_recognised_in_english_and_hinglish(self):
        for text in (
            "are you a robot?",
            "Is this a bot?",
            "am I talking to a real person",
            "you are an AI, right",
            "tum robot ho kya",
            "kya aap insaan ho",
            "kaun bol raha hai",
        ):
            self.assertIsNotNone(RE_DISCLOSURE_QUESTION.search(text), text)

    def test_an_ordinary_question_is_not_read_as_asking_about_the_ai(self):
        for text in ("when will he be free?", "can you take a message?", "kya woh ghar par hai"):
            self.assertIsNone(RE_DISCLOSURE_QUESTION.search(text), text)


class SecretTests(unittest.TestCase):
    def test_codes_cards_pins_and_upi_handles_are_all_caught(self):
        self.assertEqual(detect_secret("your otp is 483920"), "one-time code")
        self.assertEqual(detect_secret("the verification code is 9911"), "one-time code")
        self.assertEqual(detect_secret("card 4111 1111 1111 1111"), "card or account number")
        self.assertEqual(detect_secret("my password is hunter2"), "password or PIN")
        self.assertEqual(detect_secret("send it to keshav@okaxis"), "UPI handle")

    def test_an_ordinary_sentence_holds_no_secret(self):
        self.assertEqual(detect_secret("I am calling about the site papers"), "")
        self.assertEqual(detect_secret("he will call you back at five"), "")

    def test_a_secret_is_replaced_before_anything_is_stored(self):
        redacted = redact_secrets("your otp is 483920, ok?")
        self.assertNotIn("483920", redacted)
        self.assertIn("[withheld]", redacted)

    def test_the_refusal_line_never_repeats_the_secret(self):
        line = fill(SECRET_REFUSAL, "Keshav")
        self.assertIn("not allowed to read out", line)
        self.assertNotIn("483920", line)


class JudgementTests(unittest.TestCase):
    def test_decisions_and_money_are_flagged_as_yours_to_make(self):
        for text in ("please approve the payment", "sign the deal today", "salary hike chahiye"):
            self.assertTrue(mentions_decision(text), text)
        self.assertFalse(mentions_decision("I am calling about the site papers"))

    def test_spam_shapes_are_recognised_in_english_and_hindi(self):
        for text in ("you have won the lottery prize", "your account is blocked, do kyc now",
                     "आपका अकाउंट बंद होने वाला है"):
            self.assertTrue(mentions_spam(text), text)
        self.assertFalse(mentions_spam("the site papers are ready"))

    def test_asking_for_a_person_is_recognised(self):
        for text in ("let me speak to Keshav", "is he there?", "keshav se baat karni hai",
                     "phone do unhe"):
            self.assertTrue(caller_asks_for_human(text), text)
        self.assertFalse(caller_asks_for_human("tell him I called"))

    def test_a_goodbye_is_a_goodbye_and_a_message_is_not(self):
        for text in ("ok thanks bye", "thanks", "thank you", "that's all", "nothing else",
                     "bas itna hi", "bye", "chalo cut karta hoon".replace("karta hoon", "")):
            self.assertTrue(caller_is_done(text), text)
        for text in ("tell him the payment is done", "I need to talk about the site",
                     "ok I will call again tomorrow about the papers", "all the documents are ready"):
            self.assertFalse(caller_is_done(text), text)

    def test_hinglish_is_recognised_so_the_reply_language_matches(self):
        self.assertTrue(looks_like_hinglish("kya aap free ho"))
        self.assertTrue(looks_like_hinglish("आप कब आओगे"))
        self.assertFalse(looks_like_hinglish("when will you be free"))


class FallbackWordingTests(unittest.TestCase):
    def test_with_nothing_said_yet_she_greets(self):
        line = fallback_line([], owner="Keshav")
        self.assertIn("listening", line)

    def test_a_message_is_taken_without_promising_anything(self):
        line = fallback_line([("caller", "the site papers are ready")], owner="Keshav")
        self.assertIn("written that down", line)
        self.assertIn("Keshav", line)

    def test_a_caller_wanting_a_person_is_told_the_truth(self):
        line = fallback_line([("caller", "let me speak to Keshav")], owner="Keshav")
        self.assertIn("I am an AI", line)
        self.assertIn("cannot hand this phone over", line)

    def test_a_decision_is_never_made_for_you(self):
        line = fallback_line([("caller", "approve the payment now")], owner="Keshav")
        self.assertEqual(line, fill(UNSUPPORTED_REQUEST, "Keshav"))
        self.assertIn("cannot make decisions", line)

    def test_a_goodbye_closes_the_call(self):
        line = fallback_line([("caller", "ok thanks bye")], owner="Keshav")
        self.assertIn("everything I need", line)

    def test_repeated_mishearing_escalates_to_a_callback_offer(self):
        first = fallback_line([("caller", "hello?")], owner="Keshav", misheard=1)
        second = fallback_line([("caller", "hello?")], owner="Keshav", misheard=2)
        self.assertIn("say that again", first)
        self.assertIn("call you back", second)
        self.assertNotEqual(first, second)


class BrainResponderTests(unittest.TestCase):
    def serve(self, headers, body='data: {"type":"delta","text":"He is in a meeting. "}\n\ndata: {"type":"done"}\n\n', status=200):
        seen = []

        class Brain(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                seen.append(self.rfile.read(length).decode("utf-8"))
                data = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/event-stream")
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = HTTPServer(("127.0.0.1", 0), Brain)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/api/public/brain", seen

    def context(self, **extra):
        base = {"owner": "Keshav", "channel": "phone (SIM)", "caller": "Rahul", "seconds": 12}
        base.update(extra)
        return base

    def test_a_brain_that_names_the_call_task_is_trusted(self):
        endpoint, seen = self.serve({"X-Weronika-Task": "call-reply"})
        line = build_brain_responder(endpoint)(self.context(), [("caller", "is he free?")])
        self.assertEqual(line, "He is in a meeting.")
        self.assertTrue(line.confirmed)
        self.assertIn('"task": "call-reply"', seen[0])
        self.assertIn("is he free?", seen[0])

    def test_the_brain_is_told_the_disclosure_already_happened(self):
        endpoint, seen = self.serve({"X-Weronika-Task": "call-reply"})
        build_brain_responder(endpoint)(self.context(), [("weronika", "I am an AI assistant.")])
        self.assertIn("already told the caller that you are an AI", seen[0])
        self.assertIn("never claim to be a human", seen[0])

    def test_an_older_brain_that_answers_as_chat_is_not_trusted(self):
        endpoint, _ = self.serve({})
        line = build_brain_responder(endpoint)(self.context(), [("caller", "is he free?")])
        self.assertEqual(line, "He is in a meeting.")
        self.assertFalse(line.confirmed)

    def test_a_brain_that_leaks_a_code_has_it_stripped_before_speaking(self):
        endpoint, _ = self.serve(
            {"X-Weronika-Task": "call-reply"},
            body='data: {"type":"delta","text":"Sure, your otp is 483920."}\n\ndata: {"type":"done"}\n\n',
        )
        line = build_brain_responder(endpoint)(self.context(), [("caller", "read the code")])
        self.assertNotIn("483920", line)
        self.assertIn("not allowed to read out", line)
        self.assertFalse(line.confirmed)

    def test_markup_and_stage_directions_are_removed_from_spoken_lines(self):
        endpoint, _ = self.serve(
            {"X-Weronika-Task": "call-reply"},
            body='data: {"type":"delta","text":"**He is busy** [pauses] — I will tell him."}\n\ndata: {"type":"done"}\n\n',
        )
        line = build_brain_responder(endpoint)(self.context(), [])
        self.assertEqual(line, "He is busy — I will tell him.")
        for character in ("*", "[", "]", "_", "`", "#"):
            self.assertNotIn(character, line)

    def test_an_unreachable_brain_falls_back_to_local_wording(self):
        responder = build_brain_responder("http://127.0.0.1:9/api/public/brain")
        line = responder(self.context(), [("caller", "the site papers are ready")])
        self.assertFalse(line.confirmed)
        self.assertIn("written that down", line)

    def test_a_failing_brain_also_falls_back_rather_than_hanging_up(self):
        endpoint, _ = self.serve({"X-Weronika-Task": "call-reply"}, body='{"error":"busy"}', status=503)
        line = build_brain_responder(endpoint)(self.context(), [("caller", "hello?")])
        self.assertTrue(str(line).strip())
        self.assertFalse(line.confirmed)

    def test_with_the_brain_switched_off_every_line_is_local(self):
        responder = build_brain_responder("")
        line = responder(self.context(), [("caller", "approve the payment")])
        self.assertFalse(line.confirmed)
        self.assertIn("cannot make decisions", line)

    def test_a_hinglish_caller_is_described_to_the_brain_as_hinglish(self):
        endpoint, seen = self.serve({"X-Weronika-Task": "call-reply"})
        build_brain_responder(endpoint)(self.context(), [("caller", "kya woh ghar par hai")])
        self.assertIn("Hinglish", seen[0])

    def test_only_the_recent_transcript_is_sent(self):
        endpoint, seen = self.serve({"X-Weronika-Task": "call-reply"})
        transcript = [("caller", f"line {index}") for index in range(40)]
        build_brain_responder(endpoint)(self.context(), transcript)
        self.assertNotIn("line 0", seen[0])
        self.assertIn("line 39", seen[0])

    def test_a_spoken_line_is_a_string_that_carries_its_confirmation(self):
        line = SpokenLine("Hello.", confirmed=True)
        self.assertEqual(line, "Hello.")
        self.assertEqual(str(line).strip(), "Hello.")
        self.assertTrue(line.confirmed)
        self.assertFalse(SpokenLine("Hello.").confirmed)


class SummaryTests(unittest.TestCase):
    def test_the_summary_records_who_called_what_was_said_and_the_disclosure(self):
        text = summary_lines(
            owner="Keshav",
            channel="phone (SIM)",
            caller="Rahul Sharma",
            number="+919876543210",
            seconds=75,
            transcript=[
                ("weronika", "I am Weronika, an AI assistant."),
                ("caller", "the site papers are ready for signature"),
                ("weronika", "I will tell him."),
                ("caller", "thanks, bye"),
            ],
            flags=["The caller asked for you personally"],
            outcome="The caller had nothing more to add.",
        )
        self.assertIn("Rahul Sharma (+919876543210)", text)
        self.assertIn("1m 15s", text)
        self.assertIn("site papers are ready", text)
        self.assertIn("thanks, bye", text)
        self.assertIn("Flagged: The caller asked for you personally.", text)
        self.assertIn("told the caller she is an AI", text)

    def test_a_call_with_nothing_understood_says_so(self):
        text = summary_lines(
            owner="Keshav", channel="WhatsApp", caller="", number="", seconds=9,
            transcript=[("weronika", "Hello?")], flags=[], outcome="Nobody spoke.",
        )
        self.assertIn("Unknown caller", text)
        self.assertIn("said nothing Weronika could understand", text)


if __name__ == "__main__":
    unittest.main()
