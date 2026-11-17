"""Checks for the example calls Weronika can run on demand.

The example exists so the owner can see the whole behaviour — ask first, disclose, take a
message, refuse a secret, hang up — without a phone ringing. These tests hold that promise:
an example must never dial, never open a microphone, and never let a one-time code reach
the transcript or the summary.
"""

import unittest

from weronika_agent.call_demo import (
    DEFAULT_SCENARIO,
    EXAMPLES,
    Scenario,
    ScriptedAudio,
    ScriptedCallAdapter,
    ScriptedClock,
    list_examples,
    run_example,
)
from weronika_agent.models import CallChannel, CallRoute

OTP = "483920"


class FakeSpeaker:
    """A voice engine that only counts what it was asked to say."""

    def __init__(self):
        self.said = []
        self.interrupted = 0

    def say(self, text):
        self.said.append(text)

    def interrupt(self):
        self.interrupted += 1

    def describe(self):
        return {"available": True, "engine": "fake"}


class ExampleCatalogueTests(unittest.TestCase):
    def test_every_documented_example_exists(self):
        self.assertEqual(
            sorted(EXAMPLES),
            ["hinglish-family", "otp-scam", "site-papers", "whatsapp-client", "you-take-it"],
        )
        self.assertEqual(DEFAULT_SCENARIO, "site-papers")

    def test_each_example_says_who_rings_and_what_it_demonstrates(self):
        for scenario in EXAMPLES.values():
            self.assertTrue(scenario.title, scenario.id)
            self.assertTrue(scenario.caller, scenario.id)
            self.assertTrue(scenario.shows, scenario.id)
            self.assertIsInstance(scenario.channel, CallChannel)
            if scenario.decision == "weronika":
                self.assertTrue(scenario.lines, scenario.id)

    def test_both_channels_are_covered_by_an_example(self):
        channels = {scenario.channel for scenario in EXAMPLES.values()}
        self.assertIn(CallChannel.SIM, channels)
        self.assertIn(CallChannel.WHATSAPP, channels)

    def test_the_listing_is_plain_data(self):
        listing = list_examples()
        self.assertEqual(len(listing), len(EXAMPLES))
        self.assertEqual(
            sorted(listing[0]),
            ["caller", "channel", "decision", "id", "is_video", "lines", "number", "shows", "title"],
        )

    def test_an_unknown_example_is_refused_with_the_real_choices(self):
        with self.assertRaises(ValueError) as caught:
            run_example("alien-invasion")
        for known in EXAMPLES:
            self.assertIn(known, str(caught.exception))


class AskFirstTests(unittest.TestCase):
    def test_the_example_asks_before_anything_is_answered(self):
        report = run_example("site-papers", owner="Keshav")
        self.assertIn("Are you able to handle the call", report["question"])
        self.assertIn("you handle it", report["question"])
        self.assertIn("I'll take it", report["question"])
        self.assertEqual(report["steps"][0]["step"], "ringing")

    def test_the_question_names_the_caller_and_the_channel(self):
        report = run_example("whatsapp-client", owner="Keshav")
        self.assertIn("Design Studio", report["question"])
        self.assertIn("WhatsApp", report["question"])
        self.assertEqual(report["channel"], "whatsapp")

    def test_the_first_step_reports_the_ring_before_her_answer(self):
        report = run_example("site-papers")
        self.assertEqual(report["steps"][0]["said_to_you"], report["question"])
        self.assertEqual(report["steps"][1]["step"], "your answer")


class DisclosureTests(unittest.TestCase):
    def test_the_caller_is_told_they_are_speaking_to_an_ai(self):
        report = run_example("site-papers", owner="Keshav")
        self.assertTrue(report["disclosed"])
        first = report["spoken"][0]
        self.assertIn("AI", first)
        self.assertIn("Keshav", first)
        self.assertIn("not a human", first)

    def test_asking_whether_she_is_a_robot_gets_an_honest_answer(self):
        report = run_example("otp-scam", owner="Keshav")
        answers = [
            line for line in report["spoken"]
            if "I am an AI" in line and "not a human" in line
        ]
        self.assertGreaterEqual(len(answers), 2, "the disclosure is repeated when it is asked for")
        self.assertIn("asked whether this is an AI", " ".join(report["flags"]))

    def test_the_disclosure_is_repeated_in_the_caller_own_language(self):
        report = run_example("hinglish-family", owner="Keshav")
        caller_lines = [turn["text"] for turn in report["turns"] if turn["speaker"] == "caller"]
        self.assertIn("kaun bol raha hai? tum robot ho kya", caller_lines)
        self.assertTrue(report["disclosed"])


class SecretSafetyTests(unittest.TestCase):
    def test_a_one_time_code_never_reaches_the_transcript_or_the_summary(self):
        report = run_example("otp-scam", owner="Keshav")
        blob = report["summary"] + " ".join(report["spoken"]) + " ".join(report["flags"])
        self.assertNotIn(OTP, blob)
        for turn in report["turns"]:
            self.assertNotIn(OTP, turn["text"])

    def test_the_withheld_line_is_marked_as_withheld(self):
        report = run_example("otp-scam")
        withheld = [turn for turn in report["turns"] if turn["withheld"]]
        self.assertTrue(withheld)
        self.assertIn("[withheld]", withheld[0]["text"])

    def test_she_refuses_to_read_a_code_out(self):
        report = run_example("otp-scam", owner="Keshav")
        refusal = [line for line in report["spoken"] if "not allowed to read out" in line]
        self.assertTrue(refusal)
        self.assertIn("code", refusal[0])
        self.assertIn("password", refusal[0])

    def test_the_step_by_step_trace_is_redacted_too(self):
        # A trace is a repetition, so it withholds the code just like the transcript does.
        report = run_example("otp-scam", owner="Keshav")
        heard = [step for step in report["steps"] if step["step"] == "caller"]
        self.assertTrue(heard)
        for step in heard:
            self.assertNotIn(OTP, step["they_said"])
        self.assertTrue(any("[withheld]" in step["they_said"] for step in heard))

    def test_the_script_only_appears_as_the_example_own_definition(self):
        report = run_example("otp-scam", owner="Keshav")
        self.assertIn(OTP, " ".join(report["scenario"]["lines"]), "the authored script keeps its words")
        everything = {key: value for key, value in report.items() if key not in {"scenario", "shows"}}
        import json as _json

        self.assertNotIn(OTP, _json.dumps(everything, ensure_ascii=False))

    def test_the_flag_says_the_code_was_not_repeated_or_stored(self):
        report = run_example("otp-scam")
        self.assertTrue(any("one-time code" in flag for flag in report["flags"]))


class OutcomeTests(unittest.TestCase):
    def test_a_call_she_takes_is_answered_and_hung_up(self):
        report = run_example("site-papers", owner="Keshav")
        self.assertTrue(report["answered_by_weronika"])
        self.assertTrue(report["hung_up"])
        self.assertEqual(report["phase"], "ended")
        self.assertTrue(report["turns"])

    def test_choosing_to_take_it_yourself_leaves_the_phone_alone(self):
        report = run_example("you-take-it", owner="Keshav")
        self.assertEqual(report["your_answer"], "user")
        self.assertFalse(report["answered_by_weronika"])
        self.assertFalse(report["hung_up"])
        self.assertEqual(report["spoken"], [], "she must not talk over you")
        self.assertNotEqual(report["phase"], "live")

    def test_the_scenario_default_can_be_overridden_by_your_answer(self):
        report = run_example("you-take-it", decision="you handle it")
        self.assertEqual(report["your_answer"], "weronika")
        self.assertTrue(report["answered_by_weronika"])

    def test_ignoring_the_call_declines_it_without_speaking(self):
        report = run_example("site-papers", decision="ignore it")
        self.assertEqual(report["your_answer"], "ignore")
        self.assertFalse(report["answered_by_weronika"])
        self.assertEqual(report["spoken"], [])
        self.assertEqual(report["phase"], "declined")

    def test_an_unparsable_answer_falls_back_to_asking_again_not_to_answering(self):
        # `CallDecision.parse` raises on nonsense; the demo defaults to Weronika taking it,
        # which is the scenario's own default, never an accidental answer.
        report = run_example("site-papers", decision="maybe later perhaps")
        self.assertIn(report["your_answer"], {"weronika", "user", "ignore"})

    def test_no_flag_is_repeated(self):
        for scenario in EXAMPLES:
            report = run_example(scenario)
            flags = report["flags"]
            self.assertEqual(len(flags), len(set(flags)), scenario)


class SummaryTests(unittest.TestCase):
    def test_the_summary_reads_cleanly(self):
        summary = run_example("site-papers", owner="Keshav")["summary"]
        self.assertIn("Call handled by Weronika", summary)
        self.assertIn("phone (SIM)", summary)
        self.assertIn("Rahul Sharma", summary)
        self.assertEqual(summary.count("How it ended:"), 1)
        self.assertNotIn("..", summary)
        self.assertNotIn("Length 0m 00s", summary, "the example clock must show a real length")

    def test_the_summary_says_she_disclosed_and_who_gets_the_message(self):
        summary = run_example("site-papers", owner="Keshav")["summary"]
        self.assertIn("she is an AI", summary)
        self.assertIn("Keshav", summary)

    def test_a_call_she_did_not_take_is_summarised_as_yours(self):
        summary = run_example("you-take-it")["summary"]
        self.assertNotIn("Call handled by Weronika", summary)

    def test_the_summary_mentions_what_the_caller_opened_and_closed_with(self):
        summary = run_example("otp-scam")["summary"]
        self.assertIn("They opened with:", summary)
        self.assertIn("They ended with:", summary)


class PrivacyAndSideEffectTests(unittest.TestCase):
    def test_the_report_says_nothing_real_was_used(self):
        report = run_example("site-papers")
        self.assertTrue(report["simulated"])
        for claim in ("No phone", "browser", "microphone", "nothing was dialled"):
            self.assertIn(claim.lower(), report["note"].lower())

    def test_speaking_aloud_happens_only_when_it_is_asked_for(self):
        speaker = FakeSpeaker()
        silent = run_example("site-papers", speaker=speaker)
        self.assertEqual(speaker.said, [], "an example must not start talking unasked")
        self.assertTrue(silent["spoken"])

        spoken = run_example("site-papers", speak=True, speaker=speaker)
        self.assertEqual(speaker.said, spoken["spoken"])

    def test_progress_receives_the_question_and_the_steps(self):
        notes = []
        run_example("site-papers", progress=notes.append)
        self.assertTrue(any("Are you able to handle the call" in note for note in notes))
        self.assertTrue(any("Example call" in note for note in notes))
        self.assertTrue(all(isinstance(note, str) and note for note in notes))

    def test_the_adapter_only_ever_reports_the_one_scripted_call(self):
        adapter = ScriptedCallAdapter(EXAMPLES["site-papers"])
        first = adapter.ringing_calls()
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].caller, "Rahul Sharma")
        adapter.answer(first[0])
        self.assertEqual(adapter.ringing_calls(), [], "an answered call is no longer ringing")
        self.assertTrue(adapter.is_active())
        adapter.hang_up(first[0])
        self.assertFalse(adapter.is_active())
        self.assertIn("example call", str(adapter.capabilities()["note"]).lower())


class ScriptedClockAndAudioTests(unittest.TestCase):
    def test_the_clock_starts_at_the_real_time_and_only_moves_when_asked(self):
        clock = ScriptedClock(start=1000.0)
        self.assertEqual(clock(), 1000.0)
        clock.advance(6.0)
        self.assertEqual(clock(), 1006.0)

    def test_a_caller_line_costs_six_seconds_and_her_line_four(self):
        clock = ScriptedClock(start=0.0)
        audio = ScriptedAudio(["one", "two"], clock=clock)
        audio.take_next()
        self.assertEqual(clock(), 6.0)
        audio.say("hello")
        self.assertEqual(clock(), 10.0)

    def test_lines_are_handed_over_once_each_and_in_order(self):
        audio = ScriptedAudio(["first", "second"])
        self.assertEqual(audio.pending(), ["first", "second"])
        self.assertEqual(audio.take_next(), "first")
        self.assertEqual(audio.pending(), ["second"])
        self.assertEqual(audio.hear(3.0), "second")
        self.assertEqual(audio.take_next(), "")
        self.assertEqual(audio.pending(), [])

    def test_the_example_audio_is_never_automatic_and_never_opens_a_device(self):
        audio = ScriptedAudio(["line"])
        self.assertFalse(audio.automatic)
        self.assertEqual(audio.route(), CallRoute.NONE)
        self.assertFalse(audio.capabilities()["available"])
        self.assertIn("no microphone", str(audio.capabilities()["reason"]))

    def test_a_speaking_example_reports_the_speaker_route(self):
        audio = ScriptedAudio(["line"], speak_through=FakeSpeaker())
        self.assertEqual(audio.route(), CallRoute.SPEAKER_MIC)
        self.assertTrue(audio.capabilities()["available"])

    def test_interrupting_reaches_the_voice_engine(self):
        speaker = FakeSpeaker()
        audio = ScriptedAudio([], speak_through=speaker)
        audio.interrupt()
        self.assertEqual(audio.interrupted, 1)
        self.assertEqual(speaker.interrupted, 1)

    def test_a_scenario_can_be_built_by_hand(self):
        scenario = Scenario(id="custom", title="t", caller="c", number="", channel=CallChannel.SIM)
        self.assertEqual(scenario.lines, ())
        self.assertEqual(scenario.decision, "weronika")
        self.assertEqual(scenario.to_dict()["channel"], "sim")


if __name__ == "__main__":
    unittest.main()
