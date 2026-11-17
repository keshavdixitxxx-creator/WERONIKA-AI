"""Checks for the call audio pipeline: routes, voice detection, and honest fallbacks.

Nothing here needs a microphone, a speaker, or a speech model. The voice detector is fed
a synthetic stream so the behaviour that matters on a real call — waiting for speech,
stopping after the caller pauses, ignoring a room's background hum, and refusing to
invent words out of silence — can be checked exactly.
"""

import math
import struct
import unittest

from weronika_agent.call_audio import (
    ABSOLUTE_SPEECH_RMS,
    CHANNELS,
    AudioError,
    LocalCallAudio,
    ManualTranscriber,
    SAMPLE_RATE,
    SilentSpeaker,
    UtteranceReader,
    build_speaker,
    build_transcriber,
    classify_device,
    float_to_pcm,
    noise_floor,
    pcm_to_float,
    pick_route,
    rms,
    wav_bytes,
)
from weronika_agent.models import CallRoute


def tone(seconds: float, amplitude: float = 0.35, frequency: float = 220.0) -> list[float]:
    count = int(SAMPLE_RATE * seconds)
    return [
        amplitude * math.sin(2 * math.pi * frequency * (index / SAMPLE_RATE))
        for index in range(count)
    ]


def silence(seconds: float, amplitude: float = 0.0008) -> list[float]:
    """A quiet room is never digital zero, so the noise floor has something to measure."""
    count = int(SAMPLE_RATE * seconds)
    return [amplitude * math.sin(2 * math.pi * 60 * (index / SAMPLE_RATE)) for index in range(count)]


class FakeStream:
    """A microphone that plays back prepared blocks, one block per read."""

    def __init__(self, blocks, blocksize):
        self.blocks = list(blocks)
        self.blocksize = blocksize
        self.started = False
        self.stopped = False
        self.closed = False
        self.reads = 0

    def start(self):
        self.started = True

    def read(self, count):
        self.reads += 1
        if self.blocks:
            return self.blocks.pop(0), False
        return struct.pack(f"<{count}h", *([0] * count)), False

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


def stream_of(samples: list[float], block_seconds: float = 0.03):
    """Chunk samples into microphone blocks and build a factory that serves them."""
    blocksize = int(SAMPLE_RATE * block_seconds)
    blocks = [
        float_to_pcm(samples[start : start + blocksize])
        for start in range(0, len(samples), blocksize)
    ]
    made = {}

    def factory(size, rate):
        stream = FakeStream(blocks, size)
        made["stream"] = stream
        return stream

    return factory, made


class LevelTests(unittest.TestCase):
    def test_silence_is_quiet_and_a_voice_is_loud(self):
        self.assertLess(rms(silence(0.1)), ABSOLUTE_SPEECH_RMS)
        self.assertGreater(rms(tone(0.1)), ABSOLUTE_SPEECH_RMS * 5)

    def test_an_empty_frame_has_no_level(self):
        self.assertEqual(rms([]), 0.0)

    def test_pcm_survives_the_round_trip(self):
        samples = tone(0.05, amplitude=0.5)
        restored = pcm_to_float(float_to_pcm(samples))
        self.assertEqual(len(restored), len(samples))
        self.assertLess(max(abs(a - b) for a, b in zip(samples, restored)), 0.001)

    def test_samples_are_clipped_instead_of_wrapping(self):
        restored = pcm_to_float(float_to_pcm([3.0, -3.0]))
        self.assertLessEqual(max(restored), 1.0)
        self.assertGreaterEqual(min(restored), -1.0)

    def test_a_wav_header_describes_the_samples_correctly(self):
        data = wav_bytes(float_to_pcm(tone(0.05)))
        self.assertTrue(data.startswith(b"RIFF"))
        self.assertIn(b"WAVE", data[:16])
        start = data.index(b"fmt ") + 8
        _format, channels, rate, _byte_rate, _align, bits = struct.unpack("<HHIIHH", data[start : start + 16])
        self.assertEqual(channels, CHANNELS)
        self.assertEqual(rate, SAMPLE_RATE)
        self.assertEqual(bits, 16)
        self.assertIn(b"data", data)

    def test_the_noise_floor_ignores_a_loud_first_word(self):
        quiet = [0.001] * 10
        self.assertAlmostEqual(noise_floor(quiet + [0.4]), 0.001, places=3)
        self.assertEqual(noise_floor([]), 0.0)


class DeviceClassificationTests(unittest.TestCase):
    def test_bluetooth_line_in_and_the_laptop_microphone_are_told_apart(self):
        self.assertEqual(classify_device("Headset (Galaxy Buds Hands-Free)"), CallRoute.BLUETOOTH)
        self.assertEqual(classify_device("Line In (Realtek(R) Audio)"), CallRoute.AUX)
        self.assertEqual(classify_device("Microphone Array (Realtek Audio)"), CallRoute.SPEAKER_MIC)
        self.assertEqual(classify_device("Speakers (High Definition Audio)"), CallRoute.SPEAKER_MIC)


class VoiceDetectionTests(unittest.TestCase):
    def test_a_caller_who_says_nothing_produces_no_words(self):
        factory, made = stream_of(silence(0.6))
        reader = UtteranceReader(factory, clock=_fast_clock(0.6))
        self.assertEqual(reader.read(0.5), b"")
        self.assertTrue(made["stream"].closed)

    def test_one_utterance_is_captured_and_stops_after_the_pause(self):
        factory, made = stream_of(silence(0.12) + tone(0.8) + silence(1.2))
        reader = UtteranceReader(factory, clock=_fast_clock(3.0))
        pcm = reader.read(2.0)
        self.assertGreater(len(pcm), 0)
        duration = (len(pcm) // 2) / SAMPLE_RATE
        # The words plus the trailing pause, not the whole recording.
        self.assertGreater(duration, 0.8)
        self.assertLess(duration, 1.9)
        self.assertTrue(made["stream"].closed)

    def test_a_cough_shorter_than_a_word_is_not_a_utterance(self):
        factory, _ = stream_of(silence(0.12) + tone(0.1) + silence(1.2))
        reader = UtteranceReader(factory, clock=_fast_clock(3.0))
        self.assertEqual(reader.read(2.0), b"")

    def test_a_caller_who_starts_at_once_is_not_swallowed_by_calibration(self):
        factory, _ = stream_of(tone(0.9) + silence(1.2))
        reader = UtteranceReader(factory, clock=_fast_clock(3.0))
        pcm = reader.read(2.0)
        self.assertGreater((len(pcm) // 2) / SAMPLE_RATE, 0.6)

    def test_a_background_hum_does_not_look_like_speech(self):
        factory, _ = stream_of(silence(1.5, amplitude=0.004))
        reader = UtteranceReader(factory, clock=_fast_clock(2.0))
        self.assertEqual(reader.read(1.0), b"")

    def test_a_long_answer_is_cut_off_at_the_utterance_limit(self):
        factory, _ = stream_of(tone(40.0))
        reader = UtteranceReader(factory, max_seconds=2.0, clock=_fast_clock(60.0))
        pcm = reader.read(30.0)
        self.assertLessEqual((len(pcm) // 2) / SAMPLE_RATE, 2.05)

    def test_without_microphone_support_the_reason_is_actionable(self):
        reader = UtteranceReader()
        try:
            import sounddevice  # type: ignore  # noqa: F401
        except Exception:
            with self.assertRaises(AudioError) as caught:
                reader.read(1.0)
            self.assertIn("setup-calls.bat", str(caught.exception))
        else:  # pragma: no cover - only when audio support really is installed
            self.assertIsInstance(reader.read(0.1), bytes)


def _fast_clock(total: float):
    """A clock that walks forward with each read, so tests never wait in real time."""
    state = {"now": 0.0, "step": max(0.001, total / 400.0)}

    def clock():
        state["now"] += state["step"]
        return state["now"]

    return clock


class EngineSelectionTests(unittest.TestCase):
    def test_with_no_engine_installed_the_fallback_is_typed_mode_not_silence(self):
        transcriber = build_transcriber()
        description = transcriber.describe()
        if not transcriber.automatic:
            self.assertEqual(description["engine"], "typed")
            self.assertIn("setup-calls.bat", str(description["reason"]))
            self.assertEqual(transcriber.transcribe(b"\x01\x02"), "")

    def test_choosing_typed_mode_says_it_was_a_choice(self):
        description = build_transcriber("typed").describe()
        self.assertFalse(description["automatic"])
        self.assertIn("chose typed mode", str(description["reason"]))

    def test_a_silent_voice_is_reported_as_unavailable(self):
        speaker = build_speaker("silent")
        self.assertIsInstance(speaker, SilentSpeaker)
        self.assertFalse(speaker.describe()["available"])

    def test_some_voice_engine_is_chosen_and_described(self):
        speaker = build_speaker()
        description = speaker.describe()
        self.assertIn("engine", description)
        self.assertIn("available", description)
        if not description["available"]:
            self.assertIn("setup-calls.bat", str(description["reason"]))


class RouteSelectionTests(unittest.TestCase):
    def test_with_no_audio_devices_there_is_no_route_and_the_reason_is_actionable(self):
        route, note = pick_route()
        if route is CallRoute.NONE:
            self.assertTrue(note)
            self.assertIn("setup-calls.bat", note)

    def test_a_route_that_does_not_exist_is_not_pretended_to_exist(self):
        # With no Bluetooth device present, asking for Bluetooth must fail loudly rather
        # than quietly use the room microphone.
        from weronika_agent import call_audio

        original = call_audio.list_devices
        call_audio.list_devices = lambda: []
        try:
            route, note = pick_route(CallRoute.BLUETOOTH)
            self.assertEqual(route, CallRoute.NONE)
            self.assertTrue(note)
        finally:
            call_audio.list_devices = original

    def test_a_bluetooth_pairing_is_preferred_over_the_room_microphone(self):
        from weronika_agent import call_audio
        from weronika_agent.call_audio import AudioDevice

        devices = [
            AudioDevice("Microphone Array (Realtek)", True, False, CallRoute.SPEAKER_MIC),
            AudioDevice("Speakers (Realtek)", False, True, CallRoute.SPEAKER_MIC),
            AudioDevice("Headset (Buds Hands-Free)", True, True, CallRoute.BLUETOOTH),
        ]
        original = call_audio.list_devices
        call_audio.list_devices = lambda: devices
        try:
            route, note = pick_route()
            self.assertEqual(route, CallRoute.BLUETOOTH)
            self.assertIn("Buds", note)
            chosen, _ = pick_route(CallRoute.SPEAKER_MIC)
            self.assertEqual(chosen, CallRoute.SPEAKER_MIC)
        finally:
            call_audio.list_devices = original


class FakeTranscriber(ManualTranscriber):
    """Stands in for a real speech engine so the pipeline can be tested end to end."""

    name = "fake-whisper"
    automatic = True

    def __init__(self, words):
        super().__init__("")
        self.words = list(words)
        self.heard = []

    def transcribe(self, pcm, language=""):
        self.heard.append(len(pcm))
        return self.words.pop(0) if self.words else ""

    def describe(self):
        return {"engine": self.name, "automatic": True, "reason": ""}


class FakeVoice:
    def __init__(self):
        self.lines = []
        self.interrupted = 0

    def say(self, text):
        self.lines.append(text)

    def interrupt(self):
        self.interrupted += 1

    def voices(self):
        return ["Weronika"]

    def describe(self):
        return {"engine": "fake", "available": True, "reason": ""}


class LocalCallAudioTests(unittest.TestCase):
    def test_with_a_real_engine_and_a_route_weronika_listens_herself(self):
        transcriber = FakeTranscriber(["hello, this is Rahul"])
        voice = FakeVoice()
        factory, _ = stream_of(silence(0.12) + tone(0.7) + silence(1.0))
        audio = LocalCallAudio(
            route=CallRoute.SPEAKER_MIC,
            transcriber=transcriber,
            speaker=voice,
            reader=UtteranceReader(factory, clock=_fast_clock(3.0)),
        )
        self.assertTrue(audio.automatic)
        self.assertEqual(audio.route(), CallRoute.SPEAKER_MIC)
        self.assertEqual(audio.hear(2.0), "hello, this is Rahul")

    def test_in_typed_mode_she_does_not_pretend_to_hear_anything(self):
        audio = LocalCallAudio(route=CallRoute.SPEAKER_MIC, transcriber=ManualTranscriber())
        self.assertFalse(audio.automatic)
        self.assertEqual(audio.hear(1.0), "")

    def test_with_no_route_listening_is_an_error_not_silence(self):
        audio = LocalCallAudio(route=CallRoute.NONE, transcriber=FakeTranscriber(["hi"]))
        self.assertFalse(audio.automatic)
        with self.assertRaises(AudioError):
            audio.hear(1.0)

    def test_speaking_is_remembered_for_the_live_transcript(self):
        voice = FakeVoice()
        audio = LocalCallAudio(route=CallRoute.SPEAKER_MIC, speaker=voice)
        audio.say("I am Weronika, an AI assistant.")
        audio.say("   ")
        self.assertEqual(voice.lines, ["I am Weronika, an AI assistant."])
        self.assertEqual([item["text"] for item in audio.said()], ["I am Weronika, an AI assistant."])

    def test_interrupting_stops_the_voice(self):
        voice = FakeVoice()
        audio = LocalCallAudio(route=CallRoute.SPEAKER_MIC, speaker=voice)
        audio.interrupt()
        self.assertEqual(voice.interrupted, 1)

    def test_capabilities_report_the_route_the_engines_and_the_devices(self):
        audio = LocalCallAudio(
            route=CallRoute.BLUETOOTH, transcriber=ManualTranscriber("nothing installed")
        )
        report = audio.capabilities()
        self.assertTrue(report["available"])
        self.assertEqual(report["route"], "bluetooth")
        self.assertFalse(report["automatic"])
        self.assertEqual(report["speech"]["engine"], "typed")
        self.assertEqual(len(report["routes"]), 3)

    def test_no_route_explains_itself_in_capabilities(self):
        audio = LocalCallAudio(route=CallRoute.NONE)
        report = audio.capabilities()
        self.assertFalse(report["available"])
        self.assertTrue(report["reason"])


if __name__ == "__main__":
    unittest.main()
