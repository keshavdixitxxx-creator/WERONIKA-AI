"""Checks for the call routes the orb talks to, on a real loopback server.

The call service here is the real one, driven by the example call's scripted channel and
audio, so these tests exercise the wiring rather than a mock of it: what the orb receives
when a call rings, when it answers, when it refuses an unsafe setting, and when a sentence
typed in chat is recognised as a call request.
"""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest import mock

from weronika_agent.call_demo import EXAMPLES, ScriptedAudio, ScriptedCallAdapter, ScriptedClock
from weronika_agent.call_dialogue import build_brain_responder
from weronika_agent.calls import CallWatchService
from weronika_agent.http_server import LocalServer, make_handler
from weronika_agent.watch_skills import SkillRegistry
from weronika_agent.workflow import MessagingService
from weronika_agent.workspace import LocalWorkspace


class FakeDraft:
    def __init__(self, recipient, text):
        self.recipient = recipient
        self.text = text
        self.sent = False

    def to_dict(self):
        return {
            "draft_id": "draft-1",
            "recipient": self.recipient,
            "message": self.text,
            "state": "awaiting_confirmation",
            "sent": self.sent,
        }


class FakeMessaging:
    """Prepares a summary draft; sending is a separate, confirmed step."""

    def __init__(self):
        self.prepared = []

    def prepare(self, platform, recipient, text):
        draft = FakeDraft(recipient, text)
        self.prepared.append((platform.value, draft))
        return draft


class UnusedAdapter:
    """Nothing in these tests may send a message through a browser."""

    def __init__(self):
        self.sent = []

    def find_recipients(self, query):
        return []

    def open_chat_and_draft(self, candidate, message):
        raise AssertionError("a call route must not open a chat")

    def send_and_verify(self, message):
        self.sent.append(message)
        return True


def build_calls(scenario_id="site-papers", owner="Keshav", messaging=None):
    scenario = EXAMPLES[scenario_id]
    adapter = ScriptedCallAdapter(scenario)
    clock = ScriptedClock()
    audio = ScriptedAudio(scenario.lines, clock=clock)
    calls = CallWatchService(
        [adapter], audio, clock=clock, responder=build_brain_responder(""), messaging=messaging
    )
    calls.configure({"owner": owner})
    return SimpleNamespace(calls=calls, adapter=adapter, audio=audio, clock=clock, scenario=scenario)


class CallHttpHarness(unittest.TestCase):
    """Starts the worker's HTTP server with a scripted call service behind it."""

    scenario_id = "site-papers"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = LocalWorkspace(self.temp.name)
        self.messaging_adapter = UnusedAdapter()
        self.messaging = FakeMessaging()
        self.service = MessagingService(lambda _: self.messaging_adapter)
        self.skills = SkillRegistry()
        self.rig = build_calls(self.scenario_id, messaging=self.messaging)
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                self.service,
                SimpleNamespace(browser=None),
                self.workspace,
                skills=self.skills,
                calls=self.rig.calls,
            ),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def post(self, path, payload, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        request = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
        if body.startswith("{"):
            return [json.loads(body)]
        return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]

    def call(self, path, payload):
        """POST to a call route and return (progress messages, result payload, error)."""
        events = self.post(path, payload, origin=self.base)
        notes = [event["message"] for event in events if event.get("type") == "progress"]
        result = next((event["workflow"] for event in events if event.get("type") == "result"), None)
        error = next((event["message"] for event in events if event.get("type") == "error"), "")
        return notes, result, error

    def ring(self):
        """Scan so the scripted call rings, and return its item id."""
        _notes, result, error = self.call("/api/call/scan", {})
        self.assertFalse(error, error)
        return str(result["raised"][0]["item_id"])

    def message(self, text):
        return self.post("/api/message", {"text": text}, origin=self.base)[0]


class StatusRouteTests(CallHttpHarness):
    def test_the_status_route_reports_a_running_service(self):
        status, data = self.get("/api/call/status")
        self.assertEqual(status, 200)
        self.assertTrue(data["available"])
        self.assertEqual(data["items"], [])
        self.assertFalse(data["busy"])

    def test_the_status_route_carries_the_settings_the_orb_shows(self):
        _status, data = self.get("/api/call/status")
        self.assertEqual(data["settings"]["owner"], "Keshav")
        self.assertTrue(data["settings"]["enabled"])
        self.assertIn("channels", data["settings"])

    def test_the_status_route_reports_the_audio_situation(self):
        _status, data = self.get("/api/call/status")
        self.assertFalse(data["audio"]["automatic"], "an example call opens no microphone")

    def test_capabilities_name_every_channel_this_worker_watches(self):
        _status, data = self.get("/api/call/capabilities")
        channels = {channel["channel"] for channel in data["channels"]}
        self.assertEqual(channels, {"sim"}, "this rig has one scripted channel")

    def test_a_worker_with_both_channels_reports_both(self):
        rig = build_calls("whatsapp-client")
        handler = make_handler(
            self.service,
            SimpleNamespace(browser=None),
            self.workspace,
            skills=self.skills,
            calls=CallWatchService(
                [self.rig.adapter, rig.adapter], self.rig.audio, clock=self.rig.clock,
                responder=build_brain_responder(""),
            ),
        )
        server = LocalServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/api/call/capabilities", timeout=5
            ) as response:
                data = json.load(response)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual({channel["channel"] for channel in data["channels"]}, {"sim", "whatsapp"})

    def test_capabilities_tell_the_truth_about_telegram(self):
        _status, data = self.get("/api/call/capabilities")
        self.assertIn("Telegram Web has no calling", data["telegram"])
        self.assertIn("Bot API", data["telegram"])

    def test_capabilities_include_the_cable_phone_scan(self):
        _status, data = self.get("/api/call/capabilities")
        self.assertIn("links", data)
        self.assertTrue(data["links"]["summary"])

    def test_capabilities_report_the_audio_route_with_its_reason(self):
        _status, data = self.get("/api/call/capabilities")
        self.assertEqual(data["audio"]["route"], "none")
        self.assertTrue(data["audio"]["reason"] or data["audio"]["engine"])

    def test_the_automation_status_advertises_call_handling(self):
        _status, data = self.get("/api/automation/status")
        self.assertTrue(data["call_watch"])


class WorkerWithoutCallsTests(unittest.TestCase):
    """A worker started with --no-calls must say so rather than look idle."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = MessagingService(lambda _: UnusedAdapter())
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(self.service, SimpleNamespace(browser=None), LocalWorkspace(self.temp.name)),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_the_status_route_says_call_handling_is_not_running(self):
        with urllib.request.urlopen(self.base + "/api/call/status", timeout=5) as response:
            data = json.load(response)
        self.assertFalse(data["available"])
        self.assertIn("not running", data["reason"])

    def test_the_capabilities_route_still_explains_telegram(self):
        with urllib.request.urlopen(self.base + "/api/call/capabilities", timeout=5) as response:
            data = json.load(response)
        self.assertFalse(data["available"])
        self.assertIn("Telegram", data["telegram"])

    def test_the_automation_status_does_not_advertise_call_handling(self):
        with urllib.request.urlopen(self.base + "/api/automation/status", timeout=5) as response:
            data = json.load(response)
        self.assertFalse(data["call_watch"])

    def test_a_call_route_answers_with_an_explanation_not_a_crash(self):
        request = urllib.request.Request(
            self.base + "/api/call/scan",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": self.base},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            events = [json.loads(line[6:]) for line in response.read().decode("utf-8").splitlines()
                      if line.startswith("data: ")]
        error = next(event["message"] for event in events if event["type"] == "error")
        self.assertIn("Call handling is not running", error)


class ScanAndAnswerTests(CallHttpHarness):
    def test_scanning_raises_the_call_and_asks_the_owner_first(self):
        notes, result, error = self.call("/api/call/scan", {})
        self.assertEqual(error, "")
        self.assertEqual(result["stage"], "scan")
        self.assertEqual(len(result["raised"]), 1)
        question = result["raised"][0]["question"]
        self.assertIn("Are you able to handle the call", question)
        self.assertTrue(notes)

    def test_the_ringing_call_is_visible_in_the_status_route(self):
        item_id = self.ring()
        _status, data = self.get("/api/call/status")
        self.assertEqual(len(data["awaiting"]), 1)
        self.assertEqual(data["awaiting"][0]["item_id"], item_id)
        self.assertEqual(data["awaiting"][0]["phase"], "awaiting_user")

    def test_scanning_marks_the_ask_first_skill_as_used(self):
        self.ring()
        used = {skill["id"]: skill["used"] for skill in self.skills.catalog()["skills"]}
        self.assertTrue(used.get("call-watch-ask"), "the ask-first skill should be recorded")

    def test_answering_discloses_that_she_is_an_ai(self):
        item_id = self.ring()
        _notes, result, error = self.call("/api/call/decide", {"item_id": item_id, "decision": "weronika"})
        self.assertEqual(error, "")
        self.assertEqual(result["phase"], "live")
        self.assertTrue(result["disclosed"])
        self.assertIn("AI", result["transcript"][0]["text"])
        self.assertTrue(self.rig.adapter.answered)

    def test_answering_marks_the_handle_skill_as_used(self):
        item_id = self.ring()
        self.call("/api/call/decide", {"item_id": item_id, "decision": "weronika"})
        used = {skill["id"]: skill["used"] for skill in self.skills.catalog()["skills"]}
        self.assertTrue(used.get("call-handle"))

    def test_leaving_the_call_to_the_owner_touches_nothing(self):
        item_id = self.ring()
        _notes, result, error = self.call("/api/call/decide", {"item_id": item_id, "decision": "user"})
        self.assertEqual(error, "")
        self.assertEqual(result["decision"], "user")
        # She never answered, so there is nothing to hand back: the call is simply hers no more.
        self.assertNotEqual(result["phase"], "live")
        self.assertEqual(self.rig.adapter.answered, [])
        self.assertEqual(self.rig.adapter.declined, [])
        self.assertEqual(self.rig.adapter.hung_up, [])
        self.assertEqual(result["transcript"], [], "she must not say a word")

    def test_an_unparsable_decision_is_refused_with_the_three_choices(self):
        item_id = self.ring()
        _notes, result, error = self.call("/api/call/decide", {"item_id": item_id, "decision": "maybe"})
        self.assertIsNone(result)
        self.assertIn("did not catch who should take the call", error)
        self.assertIn("you handle it", error)
        self.assertEqual(self.rig.adapter.answered, [])

    def test_an_unknown_call_is_refused_rather_than_guessed(self):
        _notes, result, error = self.call("/api/call/decide", {"item_id": "nope", "decision": "weronika"})
        self.assertIsNone(result)
        self.assertTrue(error)


class LiveCallTests(CallHttpHarness):
    def answer(self):
        item_id = self.ring()
        self.call("/api/call/decide", {"item_id": item_id, "decision": "weronika"})
        return item_id

    def test_a_typed_caller_line_gets_an_answer(self):
        item_id = self.answer()
        _notes, result, error = self.call("/api/call/hear", {"item_id": item_id, "text": "The papers are ready"})
        self.assertEqual(error, "")
        speakers = [turn["speaker"] for turn in result["transcript"]]
        self.assertEqual(speakers[-2:], ["caller", "weronika"])
        self.assertTrue(result["transcript"][-1]["text"])

    def test_your_own_words_can_be_spoken_into_the_call(self):
        item_id = self.answer()
        _notes, result, error = self.call(
            "/api/call/say", {"item_id": item_id, "text": "I will call you back in ten minutes"}
        )
        self.assertEqual(error, "")
        self.assertIn("I will call you back in ten minutes", result["transcript"][-1]["text"])

    def test_asking_her_to_read_a_secret_out_is_refused_the_first_time(self):
        item_id = self.answer()
        self.call("/api/call/hear", {"item_id": item_id, "text": "the otp is 483920"})
        _notes, result, error = self.call("/api/call/say", {"read_secret": True})
        blob = json.dumps(result or {}) + error
        self.assertNotIn("483920", blob)

    def test_ending_the_call_hangs_up_and_writes_a_summary(self):
        item_id = self.answer()
        _notes, result, error = self.call("/api/call/end", {"item_id": item_id, "reason": "You asked."})
        self.assertEqual(error, "")
        self.assertEqual(result["phase"], "ended")
        self.assertTrue(self.rig.adapter.hung_up)
        self.assertIn("How it ended:", result["summary"])

    def test_a_summary_is_prepared_and_nothing_is_sent(self):
        item_id = self.answer()
        self.call("/api/call/end", {"item_id": item_id, "reason": "You asked."})
        _notes, result, error = self.call(
            "/api/call/summary", {"item_id": item_id, "platform": "whatsapp", "recipient": "Boss"}
        )
        self.assertEqual(error, "")
        self.assertEqual(result["recipient"], "Boss")
        self.assertEqual(result["state"], "awaiting_confirmation")
        self.assertEqual(self.messaging_adapter.sent, [])
        self.assertEqual(len(self.messaging.prepared), 1)

    def test_handing_the_phone_back_leaves_the_call_live(self):
        item_id = self.answer()
        _notes, result, error = self.call("/api/call/handover", {"item_id": item_id})
        self.assertEqual(error, "")
        self.assertEqual(result["phase"], "handover")
        self.assertEqual(self.rig.adapter.hung_up, [])


class ConfigureTests(CallHttpHarness):
    def test_settings_are_echoed_back_with_an_explanation(self):
        _notes, result, error = self.call("/api/call/configure", {"owner": "Commander"})
        self.assertEqual(error, "")
        self.assertEqual(result["stage"], "configure")
        self.assertEqual(result["settings"]["owner"], "Commander")
        self.assertTrue(result["prompt"])

    def test_call_handling_can_be_switched_off(self):
        _notes, result, error = self.call("/api/call/configure", {"enabled": False})
        self.assertEqual(error, "")
        self.assertFalse(result["settings"]["enabled"])
        self.assertIn("off", result["prompt"].casefold())

    def test_a_switched_off_service_does_not_answer_a_scan(self):
        self.call("/api/call/configure", {"enabled": False})
        _notes, result, error = self.call("/api/call/scan", {})
        self.assertEqual(error, "")
        self.assertEqual(result["raised"], [])
        self.assertTrue(result["notes"] or result["prompt"])

    def test_an_always_answer_setting_is_refused(self):
        for setting in ("auto_answer", "always_answer", "answer_all"):
            _notes, result, error = self.call("/api/call/configure", {setting: True})
            self.assertIsNone(result, setting)
            self.assertTrue(error, setting)
            self.assertIn("each call", error)

    def test_telegram_cannot_be_switched_on_as_a_call_channel(self):
        _notes, result, error = self.call("/api/call/configure", {"channels": ["telegram"]})
        self.assertIsNone(result)
        self.assertIn("Telegram", error)

    def test_an_unknown_setting_changes_nothing(self):
        # The orb may send extra fields; an unrecognised one must not switch anything on.
        _notes, result, error = self.call("/api/call/configure", {"nonsense": 1})
        self.assertEqual(error, "")
        self.assertTrue(result["settings"]["enabled"])
        self.assertNotIn("nonsense", result["settings"])


class ExampleTests(CallHttpHarness):
    def test_an_example_runs_without_touching_a_phone(self):
        _notes, result, error = self.call("/api/call/simulate", {"scenario": "otp-scam"})
        self.assertEqual(error, "")
        self.assertEqual(result["stage"], "simulate")
        self.assertTrue(result["simulated"])
        self.assertIn("No phone", result["note"])
        self.assertTrue(result["prompt"])

    def test_an_example_can_be_listed_instead_of_run(self):
        _notes, result, error = self.call("/api/call/simulate", {"list": True})
        self.assertEqual(error, "")
        self.assertEqual(len(result["examples"]), len(EXAMPLES))
        self.assertIn("otp-scam", result["prompt"])

    def test_an_example_marks_the_example_skill_as_used(self):
        self.call("/api/call/simulate", {"scenario": "site-papers"})
        used = {skill["id"]: skill["used"] for skill in self.skills.catalog()["skills"]}
        self.assertTrue(used.get("call-example"))

    def test_an_unknown_call_route_is_refused_before_it_reaches_the_service(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/call/teleport", {}, origin=self.base)
        self.assertEqual(caught.exception.code, 404)
        self.assertEqual(self.rig.adapter.answered, [])


class ChatIntentTests(CallHttpHarness):
    def test_asking_her_to_handle_calls_is_answered_locally(self):
        result = self.message("handle my calls")
        self.assertTrue(result["handled"])
        self.assertEqual(result["kind"], "call-setup")
        self.assertTrue(result["settings"]["enabled"])

    def test_a_named_channel_and_route_reach_the_settings(self):
        result = self.message("handle calls on whatsapp")
        self.assertEqual(result["settings"]["channels"], ["whatsapp"])

    def test_refusing_calls_switches_handling_off_not_on(self):
        # The most dangerous misreading in the grammar: a refusal must never enable answering.
        result = self.message("don't answer my calls")
        self.assertEqual(result["kind"], "call-setup")
        self.assertFalse(result["settings"]["enabled"])
        self.assertIn("off", result["prompt"].casefold())

    def test_a_scan_request_is_answered_locally(self):
        result = self.message("scan calls")
        self.assertEqual(result["kind"], "call-scan")
        self.assertEqual(len(result["raised"]), 1)

    def test_a_status_request_is_answered_locally(self):
        result = self.message("show me the call summary")
        self.assertEqual(result["kind"], "call-status")
        self.assertTrue(result["prompt"])

    def test_a_device_question_is_answered_locally(self):
        result = self.message("which phone is connected")
        self.assertEqual(result["kind"], "call-links")
        self.assertIn("links", result)
        self.assertTrue(result["prompt"])

    def test_an_example_request_runs_the_example_on_the_named_channel(self):
        result = self.message("show me an example of a whatsapp call")
        self.assertEqual(result["kind"], "call-example")
        self.assertEqual(result["channel"], "whatsapp")

    def test_a_short_answer_is_understood_while_a_call_is_ringing(self):
        self.ring()
        result = self.message("you handle it")
        self.assertEqual(result["kind"], "call")
        self.assertEqual(result["phase"], "live")
        self.assertTrue(result["disclosed"])

    def test_a_hinglish_answer_is_understood_too(self):
        self.ring()
        result = self.message("tum utha lo")
        self.assertEqual(result["phase"], "live")

    def test_ending_a_live_call_in_chat_hangs_up(self):
        self.ring()
        self.message("you handle it")
        result = self.message("kaat do")
        self.assertEqual(result["phase"], "ended")
        self.assertTrue(self.rig.adapter.hung_up)

    def test_reporting_what_the_caller_said_adds_the_line(self):
        self.ring()
        self.message("you handle it")
        result = self.message("he said the papers are ready")
        self.assertEqual(result["transcript"][-2]["text"], "the papers are ready")

    def test_a_short_answer_with_nothing_ringing_is_not_read_as_a_call_decision(self):
        # "you handle it" only means something while a call is ringing. With no call it stays
        # ordinary conversation, so the cloud brain sees it rather than the call service.
        result = self.message("you handle it")
        self.assertNotEqual(result.get("kind"), "call")
        self.assertEqual(self.rig.adapter.answered, [])

    def test_a_call_word_with_nothing_ringing_explains_itself(self):
        result = self.message("hang up the call")
        self.assertTrue(result["handled"])
        self.assertIn("No call is ringing", result["prompt"])

    def test_sending_a_summary_asks_who_should_get_it(self):
        self.ring()
        self.message("you handle it")
        result = self.message("send the call summary on WhatsApp")
        self.assertIn("Who should get the call summary", result["prompt"])
        self.assertEqual(self.messaging.prepared, [])

    def test_a_summary_with_no_call_behind_it_says_so(self):
        result = self.message("send the call summary on WhatsApp")
        self.assertIn("There is no call summary to send yet", result["prompt"])
        self.assertEqual(self.messaging.prepared, [])

    def test_sending_a_summary_names_the_recipient_and_sends_nothing(self):
        self.ring()
        self.message("you handle it")
        result = self.message("send the call summary to Boss on whatsapp")
        self.assertEqual(result["kind"], "call-summary")
        self.assertEqual(result["recipient"], "Boss")
        self.assertIn("Nothing is sent until you say", result["prompt"])
        self.assertEqual(self.messaging_adapter.sent, [])


class LoopbackGuardTests(CallHttpHarness):
    def test_a_call_route_refuses_a_request_from_another_site(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/call/scan", {}, origin="http://evil.example")
        self.assertEqual(caught.exception.code, 403)
        self.assertEqual(self.rig.adapter.answered, [])

    def test_a_call_route_refuses_a_request_with_no_origin_from_outside(self):
        # The orb always sends its own origin; a bare cross-origin POST is refused.
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/call/scan", {}, origin="null")
        self.assertEqual(caught.exception.code, 403)


class LinkScanFailureTests(CallHttpHarness):
    def test_a_failing_phone_scan_is_reported_not_crashed(self):
        with mock.patch(
            "weronika_agent.http_server.scan_links", side_effect=RuntimeError("usb died")
        ):
            status, data = self.get("/api/call/links")
        self.assertEqual(status, 200)
        self.assertEqual(data["links"], [])
        self.assertIn("usb died", data["summary"])

    def test_a_failing_scan_does_not_stop_the_capabilities_route(self):
        with mock.patch(
            "weronika_agent.http_server.scan_links", side_effect=RuntimeError("usb died")
        ):
            status, data = self.get("/api/call/capabilities")
        self.assertEqual(status, 200)
        self.assertTrue(data["channels"])


if __name__ == "__main__":
    unittest.main()
