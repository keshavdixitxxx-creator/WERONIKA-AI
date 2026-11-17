"""Checks for the WhatsApp Web call channel.

No browser is involved: a fake page answers the same ``evaluate`` calls Playwright would,
which is what makes the risky part testable — deciding what an unfamiliar call screen
means, and refusing to press anything that is not certainly the right control.
"""

import base64
import unittest

from weronika_agent.call_audio import ManualTranscriber, float_to_pcm
from weronika_agent.models import CallChannel, CallRoute
from weronika_agent.whatsapp_calls import (
    AUDIO_TAP_JS,
    CALL_SCAN_JS,
    CLICK_JS,
    CLEAR_JS,
    BrowserCallAudio,
    Candidate,
    WhatsappCallAdapter,
    WhatsappCallError,
    caller_from_panel,
    interpret_call_dom,
    parse_candidates,
    pick_button,
)

RINGING_PAGE = {
    "url": "https://web.whatsapp.com/",
    "signed_in": True,
    "needs_login": False,
    "candidates": [
        {
            "index": 0,
            "label": "",
            "icon": "",
            "text": "Incoming call from Rahul",
            "tag": "DIV",
            "clickable": False,
            "panel_text": "Rahul\nIncoming call from Rahul\nDecline\nAnswer",
        },
        {"index": 1, "label": "Decline", "icon": "decline", "text": "Decline", "tag": "DIV",
         "clickable": True, "panel_text": "Rahul\nIncoming call from Rahul"},
        {"index": 2, "label": "Answer", "icon": "answer", "text": "Answer", "tag": "DIV",
         "clickable": True, "panel_text": "Rahul\nIncoming call from Rahul"},
    ],
}

ACTIVE_PAGE = {
    "url": "https://web.whatsapp.com/",
    "signed_in": True,
    "needs_login": False,
    "candidates": [
        {"index": 0, "label": "Mute", "icon": "mute", "text": "Mute", "tag": "DIV", "clickable": True,
         "panel_text": "Rahul\n00:12"},
        {"index": 1, "label": "Speakerphone", "icon": "speaker", "text": "Speakerphone", "tag": "DIV",
         "clickable": True, "panel_text": "Rahul\n00:12"},
        {"index": 2, "label": "End call", "icon": "call-end", "text": "End call", "tag": "DIV",
         "clickable": True, "panel_text": "Rahul\n00:12"},
    ],
}

IDLE_PAGE = {"url": "https://web.whatsapp.com/", "signed_in": True, "needs_login": False, "candidates": []}

LOGIN_PAGE = {
    "url": "https://web.whatsapp.com/",
    "signed_in": False,
    "needs_login": True,
    "candidates": [],
}

AMBIGUOUS_PAGE = {
    "url": "https://web.whatsapp.com/",
    "signed_in": True,
    "needs_login": False,
    "candidates": [
        {"index": 0, "label": "", "icon": "", "text": "Incoming call from Rahul", "tag": "DIV",
         "clickable": False, "panel_text": "Rahul\nIncoming call from Rahul"},
        {"index": 1, "label": "Decline", "icon": "decline", "text": "Decline", "tag": "DIV",
         "clickable": True, "panel_text": "Rahul\nIncoming call from Rahul"},
    ],
}

VIDEO_RINGING_PAGE = {
    "url": "https://web.whatsapp.com/",
    "signed_in": True,
    "needs_login": False,
    "candidates": [
        {"index": 0, "label": "", "icon": "video-call", "text": "Incoming video call from Priya",
         "tag": "DIV", "clickable": False, "panel_text": "Priya\nIncoming video call"},
        {"index": 1, "label": "Answer with video", "icon": "video-answer", "text": "Answer with video",
         "tag": "DIV", "clickable": True, "panel_text": "Priya\nIncoming video call"},
        {"index": 2, "label": "Decline", "icon": "decline", "text": "Decline", "tag": "DIV",
         "clickable": True, "panel_text": "Priya\nIncoming video call"},
    ],
}


class FakePage:
    """Answers the four evaluate calls this adapter makes, in the order it makes them."""

    def __init__(self, payloads=None):
        self.payloads = list(payloads or [IDLE_PAGE])
        self.scripts: list[str] = []
        self.clicked: list[int] = []
        self.tap_attached = True
        self.drain_payload = None
        self.error = ""

    def evaluate(self, script, *args):
        label = next(
            (name for name, known in (("clear", CLEAR_JS), ("scan", CALL_SCAN_JS),
                                      ("click", CLICK_JS), ("tap", AUDIO_TAP_JS)) if script is known),
            "attach()" if "attach()" in script else "drain()" if "drain()" in script else "other",
        )
        self.scripts.append(label)
        if self.error:
            raise RuntimeError(self.error)
        if script is CLEAR_JS:
            return True
        if script is CALL_SCAN_JS:
            return self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
        if script is CLICK_JS:
            self.clicked.append(int(args[1]))
            return {"clicked": True, "label": "pressed"}
        if script is AUDIO_TAP_JS:
            return {"installed": True, "attached": False, "error": "", "queued": 0, "sampleRate": 48000}
        if "attach()" in script:
            return self.tap_attached
        if "drain()" in script:
            return self.drain_payload or {"sampleRate": 48000, "attached": True, "error": "", "pcm": ""}
        return None


def adapter(page):
    return WhatsappCallAdapter(page_provider=lambda: page)


class InterpretationTests(unittest.TestCase):
    def test_a_ringing_call_is_recognised_with_its_caller(self):
        reading = interpret_call_dom(RINGING_PAGE)
        self.assertEqual(reading.state, "ringing")
        self.assertEqual(reading.caller, "Rahul")
        self.assertIsNotNone(reading.pick("accept"))
        self.assertIsNotNone(reading.pick("decline"))

    def test_a_connected_call_is_recognised_as_active(self):
        reading = interpret_call_dom(ACTIVE_PAGE)
        self.assertEqual(reading.state, "active")
        self.assertIsNotNone(reading.pick("end"))

    def test_a_page_with_no_call_is_idle(self):
        self.assertEqual(interpret_call_dom(IDLE_PAGE).state, "idle")

    def test_a_signed_out_page_says_so_instead_of_looking_for_calls(self):
        reading = interpret_call_dom(LOGIN_PAGE)
        self.assertEqual(reading.state, "idle")
        self.assertIn("not signed in", reading.reason)

    def test_an_incoming_call_with_no_answer_control_is_never_guessed_at(self):
        reading = interpret_call_dom(AMBIGUOUS_PAGE)
        self.assertEqual(reading.state, "unknown")
        self.assertIn("cannot find a control", reading.reason)

    def test_a_video_call_is_labelled_as_one(self):
        reading = interpret_call_dom(VIDEO_RINGING_PAGE)
        self.assertEqual(reading.state, "ringing")
        self.assertEqual(reading.caller, "Priya")
        self.assertTrue(any("video" in item.words for item in reading.candidates))

    def test_garbage_from_the_page_is_unknown_not_idle(self):
        self.assertEqual(interpret_call_dom({}).state, "idle")
        self.assertEqual(interpret_call_dom(None).state, "unknown")

    def test_candidates_without_an_index_are_ignored(self):
        parsed = parse_candidates([{"label": "Answer"}, {"index": "x", "label": "Answer"},
                                   {"index": 3, "label": "Answer"}])
        self.assertEqual([item.index for item in parsed], [3])


class ButtonChoiceTests(unittest.TestCase):
    def test_decline_is_never_chosen_as_the_answer_button(self):
        candidates = parse_candidates(AMBIGUOUS_PAGE["candidates"])
        self.assertIsNone(pick_button(candidates, "accept"))
        self.assertEqual(pick_button(candidates, "decline").label, "Decline")

    def test_a_label_beats_an_icon(self):
        candidates = parse_candidates([
            {"index": 0, "label": "", "icon": "call-accept", "clickable": True},
            {"index": 1, "label": "Answer", "icon": "", "clickable": True},
        ])
        self.assertEqual(pick_button(candidates, "accept").index, 1)

    def test_an_icon_only_control_can_still_be_used(self):
        candidates = parse_candidates([{"index": 0, "label": "", "icon": "call-end", "clickable": True}])
        self.assertEqual(pick_button(candidates, "end").index, 0)

    def test_a_control_that_cannot_be_clicked_is_not_chosen(self):
        candidates = parse_candidates([{"index": 0, "label": "Answer", "clickable": False}])
        self.assertIsNone(pick_button(candidates, "accept"))

    def test_an_unknown_kind_chooses_nothing(self):
        candidates = parse_candidates(RINGING_PAGE["candidates"])
        self.assertIsNone(pick_button(candidates, "answer-everything"))

    def test_a_long_sentence_is_not_mistaken_for_a_button_label(self):
        candidates = parse_candidates([
            {"index": 0, "label": "", "text": "Answering this call means you agree to the terms",
             "clickable": True},
        ])
        self.assertIsNone(pick_button(candidates, "accept"))


class CallerNameTests(unittest.TestCase):
    def test_the_first_line_of_the_panel_is_the_caller(self):
        self.assertEqual(caller_from_panel("Rahul\nIncoming call from Rahul\nAnswer"), "Rahul")

    def test_a_control_word_is_not_a_name(self):
        self.assertEqual(caller_from_panel("Incoming call\nDecline\nAnswer"), "")

    def test_a_bare_number_is_not_read_as_a_name(self):
        self.assertEqual(caller_from_panel("+91 98765 43210\nAnswer"), "")

    def test_a_long_sentence_is_not_a_name(self):
        self.assertEqual(caller_from_panel("x" * 90), "")


class AdapterTests(unittest.TestCase):
    def test_a_ringing_call_becomes_an_incoming_call_on_the_whatsapp_channel(self):
        page = FakePage([RINGING_PAGE])
        calls = adapter(page).ringing_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].channel, CallChannel.WHATSAPP)
        self.assertEqual(calls[0].caller, "Rahul")
        self.assertEqual(calls[0].device, "whatsapp-web")

    def test_answering_presses_the_answer_control_only(self):
        page = FakePage([RINGING_PAGE, ACTIVE_PAGE])
        adapter(page).answer()
        self.assertEqual(page.clicked, [2])

    def test_answering_is_verified_and_a_page_that_stays_ringing_is_a_failure(self):
        page = FakePage([RINGING_PAGE])
        with self.assertRaises(WhatsappCallError) as caught:
            adapter(page).answer()
        self.assertIn("did not show the call as connected", str(caught.exception))

    def test_an_unrecognised_answer_control_is_not_pressed(self):
        page = FakePage([AMBIGUOUS_PAGE])
        with self.assertRaises(WhatsappCallError) as caught:
            adapter(page).answer()
        self.assertEqual(page.clicked, [])
        self.assertIn("cannot find an answer control", str(caught.exception))

    def test_hanging_up_presses_the_end_control(self):
        page = FakePage([ACTIVE_PAGE])
        adapter(page).hang_up()
        self.assertEqual(page.clicked, [2])

    def test_declining_presses_decline(self):
        page = FakePage([RINGING_PAGE])
        adapter(page).decline()
        self.assertEqual(page.clicked, [1])

    def test_an_unknown_screen_is_reported_rather_than_answered(self):
        page = FakePage([AMBIGUOUS_PAGE])
        with self.assertRaises(WhatsappCallError):
            adapter(page).ringing_calls()
        self.assertEqual(page.clicked, [])

    def test_a_page_that_refuses_to_be_read_is_reported(self):
        page = FakePage([IDLE_PAGE])
        page.error = "Target page, context or browser has been closed"
        report = adapter(page).capabilities()
        self.assertFalse(report["available"])
        self.assertIn("could not be read", str(report["reason"]))

    def test_a_closed_window_explains_what_to_do(self):
        report = WhatsappCallAdapter(page_provider=lambda: None).capabilities()
        self.assertFalse(report["available"])
        self.assertIn("open WhatsApp", str(report["reason"]))

    def test_capabilities_are_true_only_for_a_signed_in_page(self):
        report = adapter(FakePage([RINGING_PAGE])).capabilities()
        self.assertTrue(report["available"])
        self.assertTrue(report["answer"])
        self.assertFalse(report["speaker"])
        self.assertIn("stops instead of guessing", str(report["note"]))

    def test_stale_markers_are_cleared_before_each_scan(self):
        page = FakePage([IDLE_PAGE])
        adapter(page).ringing_calls()
        self.assertEqual(page.scripts[:2], ["clear", "scan"])


def _stepping_clock(step: float):
    """A clock that walks forward on every read, so a polling loop always reaches its deadline."""
    state = {"now": 0.0}

    def clock():
        state["now"] += step
        return state["now"]

    return clock


class BrowserAudioTests(unittest.TestCase):
    def test_the_page_tap_supplies_samples_for_transcription(self):
        page = FakePage([ACTIVE_PAGE])
        pcm = float_to_pcm([0.2 if index % 4 else -0.2 for index in range(4800)])
        page.drain_payload = {
            "sampleRate": 48000,
            "attached": True,
            "error": "",
            "pcm": base64.b64encode(pcm).decode("ascii"),
        }
        engine = Recorder()
        audio = BrowserCallAudio(adapter(page), transcriber=engine, clock=_stepping_clock(0.2))
        heard = audio.hear(1.0)
        self.assertEqual(heard, "hello from the page tap")
        self.assertTrue(engine.sizes)
        # 48 kHz down to 16 kHz: a third of the samples reach the speech engine.
        self.assertAlmostEqual(engine.sizes[0] / len(pcm), 1 / 3, delta=0.02)
        self.assertEqual(audio.route(), CallRoute.BROWSER)

    def test_a_tap_that_returns_no_audio_reports_nothing_rather_than_words(self):
        page = FakePage([ACTIVE_PAGE])
        audio = BrowserCallAudio(adapter(page), transcriber=Recorder(), clock=_stepping_clock(0.4))
        self.assertEqual(audio.hear(1.0), "")

    def test_when_the_tap_cannot_attach_the_microphone_route_is_used(self):
        page = FakePage([ACTIVE_PAGE])
        page.tap_attached = False

        class Fallback:
            def __init__(self):
                self.heard = 0
                self._route = CallRoute.SPEAKER_MIC

            def route(self):
                return self._route

            def hear(self, seconds):
                self.heard += 1
                return "heard through the microphone"

            def say(self, text):
                return None

            def interrupt(self):
                return None

        fallback = Fallback()
        audio = BrowserCallAudio(adapter(page), fallback=fallback, transcriber=Recorder())
        self.assertEqual(audio.hear(1.0), "heard through the microphone")
        self.assertEqual(fallback.heard, 1)
        self.assertEqual(audio.route(), CallRoute.SPEAKER_MIC)

    def test_in_typed_mode_the_tap_does_not_pretend_to_hear(self):
        page = FakePage([ACTIVE_PAGE])
        audio = BrowserCallAudio(adapter(page), transcriber=ManualTranscriber())
        self.assertFalse(audio.automatic)
        self.assertEqual(audio.hear(1.0), "")

    def test_a_broken_page_falls_back_instead_of_reporting_silence(self):
        page = FakePage([ACTIVE_PAGE])
        page.error = "execution context was destroyed"

        class Fallback:
            def route(self):
                return CallRoute.SPEAKER_MIC

            def hear(self, seconds):
                return "heard through the microphone"

            def say(self, text):
                return None

            def interrupt(self):
                return None

        audio = BrowserCallAudio(adapter(page), fallback=Fallback(), transcriber=Recorder())
        self.assertEqual(audio.hear(1.0), "heard through the microphone")


class Recorder(ManualTranscriber):
    automatic = True
    name = "fake"

    def __init__(self):
        super().__init__("")
        self.sizes = []

    def transcribe(self, data, language=""):
        self.sizes.append(len(data))
        return "hello from the page tap"


if __name__ == "__main__":
    unittest.main()
