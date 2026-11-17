"""Hearing the caller and speaking Weronika's lines on this computer.

A call's audio cannot travel through a USB cable: Android does not expose call audio
over adb, and no browser hands a live call's audio to a local program without being
asked in the page itself. So the sound has to move by air or wire, and this module owns
the three honest routes:

``speaker_mic``
    The phone is on speaker, standing on or beside the laptop. The laptop's microphone
    hears the caller; the laptop's speakers play Weronika's voice into the phone's
    microphone. Nothing to buy, works at once, and quality depends on a quiet room.
``bluetooth``
    The phone is paired to this computer as a hands-free headset, so the call audio
    arrives digitally and Weronika's voice goes back the same way. Best quality; needs a
    one-time pairing and a Bluetooth adapter.
``aux``
    A 3.5 mm cable from the phone's headphone socket into the laptop's line-in for
    hearing the caller, with the laptop's speaker or microphone feeding the phone.

``browser`` is the fourth route, used by a WhatsApp Web call: the signed-in page taps its
own remote audio stream and posts the samples here, and plays back the voice this module
synthesises. Nothing is recorded from a microphone in that case.

Every piece below is optional and degrades out loud. With no speech engine installed,
``automatic`` is False and the call runs in **typed mode**: Weronika still answers, still
discloses who she is, and still hangs up — but you type what the caller said. That is the
same "report it, never guess it" rule the rest of the worker follows.

Call audio is never written to disk. One utterance lives in memory just long enough to be
transcribed, the words go into the in-memory transcript, and the samples are dropped. A
recording of a phone call is exactly the kind of thing that should not be lying around in
a folder, so nothing here saves one — not even for debugging.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import os
import platform
import shutil
import struct
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .models import CallChannel, CallRoute

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # 16-bit PCM, which every speech engine here accepts
CHANNELS = 1

MAX_UTTERANCE_SECONDS = 20.0
MIN_UTTERANCE_SECONDS = 0.35
SPEECH_END_SILENCE_SECONDS = 0.7
START_TIMEOUT_GRACE_SECONDS = 1.0

# Energy-based voice detection, tuned for a phone lying on a desk in a quiet room.
NOISE_FLOOR_FRAMES = 12
SPEECH_FACTOR = 2.6
ABSOLUTE_SPEECH_RMS = 0.006
# A floor measured from speech (a caller who talks over the very first frames) would
# silence the rest of the call, so the floor is capped at a level a loud room still fits
# under. Above the cap the absolute threshold decides what counts as a voice.
MAX_NOISE_FLOOR = ABSOLUTE_SPEECH_RMS * 4
FRAME_SECONDS = 0.03
# A little trailing silence is kept: speech engines use it to settle on the last word.
KEEP_TAIL_SECONDS = 0.15

MODEL_ROOT = Path.home() / ".weronika" / "models"
TTS_TIMEOUT_SECONDS = 40

_VOICE_HINTS = (
    "natural", "neural", "premium", "online", "wavenet", "studio",
    "female", "woman", "samantha", "zira", "aria", "jenny", "ava", "swara",
    "heera", "kalpana", "veena", "aditi", "lekha", "google uk english female",
)


class AudioError(RuntimeError):
    """An expected, user-actionable audio problem."""


@dataclass(frozen=True)
class AudioDevice:
    name: str
    is_input: bool
    is_output: bool
    kind: CallRoute = CallRoute.SPEAKER_MIC
    sample_rate: int = SAMPLE_RATE

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "is_input": self.is_input,
            "is_output": self.is_output,
            "kind": self.kind.value,
        }


def classify_device(name: str, is_input: bool = False) -> CallRoute:
    """Guess what a device is for, from the name the operating system gives it.

    Only Bluetooth and wired line-in are recognisable by name. Everything else — the
    laptop's own microphone and speakers — is the ``speaker_mic`` route, which is also the
    one that needs no extra hardware.
    """
    lowered = (name or "").casefold()
    if any(
        word in lowered
        for word in ("bluetooth", "airpods", "buds", "hands-free", "handsfree", "handset", "sco", "headset")
    ):
        return CallRoute.BLUETOOTH
    if any(word in lowered for word in ("line in", "line-in", "linein", "aux", "usb audio", "3.5")):
        return CallRoute.AUX
    return CallRoute.SPEAKER_MIC


def noise_floor(levels: Sequence[float]) -> float:
    """The room's background level, from the quieter half of the calibration frames.

    Taking the mean of everything would let the caller's own first words lift the floor
    and make the rest of the call look like silence; the quiet half resists that.
    """
    values = sorted(level for level in levels if level >= 0.0)
    if not values:
        return 0.0
    quiet = values[: max(1, len(values) // 2)]
    return sum(quiet) / len(quiet)


# --------------------------------------------------------------------------- devices


def list_devices() -> list[AudioDevice]:
    """List audio devices, using sounddevice when installed and nothing else."""
    try:
        import sounddevice  # type: ignore
    except Exception:
        return []
    devices: list[AudioDevice] = []
    try:
        entries = sounddevice.query_devices()
    except Exception:
        return []
    for entry in entries:
        try:
            name = str(entry.get("name") or "")
            inputs = int(entry.get("max_input_channels") or 0)
            outputs = int(entry.get("max_output_channels") or 0)
        except Exception:
            continue
        if not name or (inputs <= 0 and outputs <= 0):
            continue
        devices.append(
            AudioDevice(
                name=name,
                is_input=inputs > 0,
                is_output=outputs > 0,
                kind=classify_device(name, inputs > 0),
                sample_rate=int(entry.get("default_samplerate") or SAMPLE_RATE),
            )
        )
    return devices


def pick_route(preference: CallRoute = CallRoute.NONE) -> tuple[CallRoute, str]:
    """Choose the best available audio route, or explain why there is none.

    ``preference`` is what you asked for in the orb; it is honoured only when a device of
    that kind actually exists, so a wished-for Bluetooth pairing never silently falls back
    to the room microphone without the orb saying so.
    """
    devices = list_devices()
    if not devices:
        return CallRoute.NONE, (
            "No audio device could be listed. Install the call audio support "
            "(setup-calls.bat) and check that the operating system exposes a microphone."
        )
    inputs = [item for item in devices if item.is_input]
    outputs = [item for item in devices if item.is_output]
    if not inputs or not outputs:
        return CallRoute.NONE, "This computer has no usable microphone and speaker pair for a call."

    def of_kind(kind: CallRoute) -> tuple[AudioDevice | None, AudioDevice | None]:
        return (
            next((item for item in inputs if item.kind is kind), None),
            next((item for item in outputs if item.kind is kind), None),
        )

    order = [CallRoute.BLUETOOTH, CallRoute.AUX, CallRoute.SPEAKER_MIC]
    if preference is not CallRoute.NONE:
        wanted_in, wanted_out = of_kind(preference)
        if wanted_in and wanted_out:
            return preference, f"Using {wanted_in.name} and {wanted_out.name}."
        if preference is CallRoute.SPEAKER_MIC:
            return preference, f"Using {inputs[0].name} and {outputs[0].name}."
        return CallRoute.NONE, (
            f"No {preference.value.replace('_', ' ')} device was found. Pair or plug it in, "
            f"or choose another route. Available inputs: {', '.join(item.name for item in inputs[:4])}."
        )
    for kind in order:
        found_in, found_out = of_kind(kind)
        if found_in and found_out:
            return kind, f"Using {found_in.name} and {found_out.name}."
    return CallRoute.SPEAKER_MIC, f"Using {inputs[0].name} and {outputs[0].name}."


# --------------------------------------------------------------------------- capture


def rms(frame: Sequence[float]) -> float:
    """Root-mean-square loudness of one frame, without needing numpy."""
    if not frame:
        return 0.0
    total = 0.0
    for sample in frame:
        total += sample * sample
    return (total / len(frame)) ** 0.5


def pcm_to_float(pcm: bytes) -> list[float]:
    count = len(pcm) // SAMPLE_WIDTH
    if count <= 0:
        return []
    samples = struct.unpack(f"<{count}h", pcm[: count * SAMPLE_WIDTH])
    return [sample / 32768.0 for sample in samples]


def float_to_pcm(frames: Sequence[float]) -> bytes:
    clipped = [max(-1.0, min(1.0, value)) for value in frames]
    return struct.pack(f"<{len(clipped)}h", *(int(value * 32767) for value in clipped))


def resample_pcm(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample 16-bit mono PCM by linear interpolation.

    A browser's AudioContext usually runs at 48 kHz, and every speech engine here wants
    16 kHz. Linear interpolation is good enough for voice, and it keeps the in-page tap
    free of any resampling dependency.
    """
    if not pcm or from_rate <= 0 or to_rate <= 0 or from_rate == to_rate:
        return pcm
    count = len(pcm) // SAMPLE_WIDTH
    if count < 2:
        return pcm
    samples = struct.unpack(f"<{count}h", pcm[: count * SAMPLE_WIDTH])
    ratio = from_rate / to_rate
    out_count = int(count / ratio)
    if out_count <= 0:
        return b""
    out: list[int] = []
    for index in range(out_count):
        position = index * ratio
        left = int(position)
        right = min(left + 1, count - 1)
        fraction = position - left
        value = samples[left] * (1.0 - fraction) + samples[right] * fraction
        out.append(int(max(-32768.0, min(32767.0, value))))
    return struct.pack(f"<{len(out)}h", *out)


def wav_bytes(pcm: bytes) -> bytes:
    """Wrap raw PCM in a WAV header, which is what every speech engine here reads."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(CHANNELS)
        output.setsampwidth(SAMPLE_WIDTH)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(pcm)
    return buffer.getvalue()


class UtteranceReader:
    """Reads one caller utterance from the microphone: speech in, then silence, then stop.

    Energy-based, with a noise floor measured from the first frames of the call so a noisy
    room does not look like continuous speech. Pure Python on purpose: ``sounddevice`` is
    the only dependency, and it is optional.
    """

    def __init__(
        self,
        stream_factory: Callable[[int, int], object] | None = None,
        *,
        max_seconds: float = MAX_UTTERANCE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._factory = stream_factory
        self._max_seconds = max_seconds
        self._clock = clock

    def read(self, wait_seconds: float) -> bytes:
        """Return the PCM of one utterance, or b"" when nobody spoke in ``wait_seconds``."""
        factory = self._factory
        if factory is None:
            # Only the real microphone needs sounddevice; an injected reader does not,
            # which is what makes the voice detection testable without audio hardware.
            try:
                import sounddevice  # type: ignore
            except Exception as exc:
                raise AudioError(
                    "No microphone support is installed. Run setup-calls.bat, or use typed mode."
                ) from exc

            def factory(blocksize, samplerate):  # type: ignore[misc]
                return sounddevice.RawInputStream(
                    samplerate=samplerate,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=blocksize,
                )

        blocksize = max(160, int(SAMPLE_RATE * FRAME_SECONDS))
        deadline = self._clock() + max(0.5, wait_seconds) + START_TIMEOUT_GRACE_SECONDS
        noise: list[float] = []
        floor = 0.0
        speech: list[float] = []
        voiced_seconds = 0.0
        trailing_silence = 0.0
        silence_seconds = 0.0
        started = False
        stream = None
        try:
            stream = factory(blocksize, SAMPLE_RATE)
            stream.start()
            while self._clock() < deadline:
                data, _overflowed = stream.read(blocksize)
                frames = pcm_to_float(bytes(data))
                if not frames:
                    continue
                level = rms(frames)
                if not started and len(noise) < NOISE_FLOOR_FRAMES:
                    # Calibrating, but a loud frame still counts as speech: a caller who
                    # starts talking at once must not be swallowed by the noise floor.
                    noise.append(level)
                    floor = min(noise_floor(noise), MAX_NOISE_FLOOR)
                    if len(noise) >= 4 and level >= max(
                        floor * SPEECH_FACTOR, ABSOLUTE_SPEECH_RMS * 2.0
                    ):
                        started = True
                        voiced_seconds += len(frames) / SAMPLE_RATE
                        speech.extend(frames)
                    continue
                threshold = max(floor * SPEECH_FACTOR, ABSOLUTE_SPEECH_RMS)
                if level >= threshold:
                    started = True
                    silence_seconds = 0.0
                    voiced_seconds += len(frames) / SAMPLE_RATE
                    speech.extend(frames)
                    if voiced_seconds >= self._max_seconds:
                        break
                elif started:
                    silence_seconds += len(frames) / SAMPLE_RATE
                    trailing_silence += len(frames) / SAMPLE_RATE
                    speech.extend(frames)
                    if silence_seconds >= SPEECH_END_SILENCE_SECONDS:
                        break
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        if not started:
            return b""
        # A cough is not a sentence: only the frames that were actually loud count towards
        # the minimum, and the long tail of silence is trimmed before transcription.
        if voiced_seconds < MIN_UTTERANCE_SECONDS:
            return b""
        keep_tail = int(SAMPLE_RATE * KEEP_TAIL_SECONDS)
        drop = int(SAMPLE_RATE * trailing_silence) - keep_tail
        if drop > 0:
            del speech[len(speech) - drop :]
        return float_to_pcm(speech)


# --------------------------------------------------------------------------- speech-to-text


class Transcriber:
    """Base class: turns one utterance of PCM into words."""

    name = "none"
    automatic = False

    def transcribe(self, pcm: bytes, language: str = "") -> str:  # pragma: no cover - interface
        return ""

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "automatic": self.automatic, "reason": ""}


class ManualTranscriber(Transcriber):
    """No engine installed: you type what the caller said, Weronika still runs the call."""

    name = "typed"
    automatic = False

    def __init__(self, reason: str = "") -> None:
        self._reason = reason or (
            "No speech engine is installed. Run setup-calls.bat for local transcription, "
            "or type what the caller says and Weronika will answer it."
        )

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "automatic": False, "reason": self._reason}


class WhisperTranscriber(Transcriber):
    """Local ``faster-whisper`` transcription. The model loads once and stays in memory."""

    name = "whisper"
    automatic = True

    def __init__(self, model_size: str = "", device: str = "cpu") -> None:
        self._size = model_size or os.environ.get("WERONIKA_WHISPER_MODEL") or "small"
        self._device = device
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel  # type: ignore

                self._model = WhisperModel(self._size, device=self._device, compute_type="int8")
            return self._model

    @staticmethod
    def available() -> bool:
        try:
            import faster_whisper  # type: ignore  # noqa: F401
        except Exception:
            return False
        return True

    def transcribe(self, pcm: bytes, language: str = "") -> str:
        if not pcm:
            return ""
        import numpy  # type: ignore

        samples = numpy.frombuffer(pcm, dtype="int16").astype("float32") / 32768.0
        model = self._load()
        segments, _info = model.transcribe(
            samples,
            language=language or None,
            vad_filter=False,
            beam_size=1,
            condition_on_previous_text=False,
        )
        text = " ".join(str(segment.text) for segment in segments)
        return " ".join(text.split())[:1000]

    def describe(self) -> dict[str, object]:
        return {
            "engine": f"whisper-{self._size}",
            "automatic": True,
            "reason": "",
            "loaded": self._model is not None,
        }


class VoskTranscriber(Transcriber):
    """Local Vosk transcription — a smaller, faster model than Whisper."""

    name = "vosk"
    automatic = True

    def __init__(self, model_path: str = "") -> None:
        self._path = model_path or os.environ.get("WERONIKA_VOSK_MODEL") or ""
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from vosk import Model  # type: ignore

                if self._path and Path(self._path).is_dir():
                    self._model = Model(self._path)
                else:
                    candidates = sorted((MODEL_ROOT / "vosk").glob("vosk-model*")) if (MODEL_ROOT / "vosk").is_dir() else []
                    if not candidates:
                        raise AudioError(
                            "Vosk is installed but no model folder was found under ~/.weronika/models/vosk."
                        )
                    self._model = Model(str(candidates[-1]))
            return self._model

    @staticmethod
    def available() -> bool:
        try:
            import vosk  # type: ignore  # noqa: F401
        except Exception:
            return False
        return True

    def transcribe(self, pcm: bytes, language: str = "") -> str:
        if not pcm:
            return ""
        from vosk import KaldiRecognizer  # type: ignore

        recognizer = KaldiRecognizer(self._load(), SAMPLE_RATE)
        recognizer.SetWords(False)
        chunk = 8000
        for start in range(0, len(pcm), chunk):
            recognizer.AcceptWaveform(pcm[start : start + chunk])
        import json

        final = json.loads(recognizer.FinalResult() or "{}")
        return " ".join(str(final.get("text") or "").split())[:1000]

    def describe(self) -> dict[str, object]:
        return {"engine": "vosk", "automatic": True, "reason": "", "loaded": self._model is not None}


def build_transcriber(preference: str = "auto") -> Transcriber:
    """Pick the best installed engine: Whisper, then Vosk, then typed mode.

    The order matters because accuracy on Hinglish and Indian English differs a lot, and
    the fallback must never be silence — it is a clear "type it yourself" mode.
    """
    wanted = (preference or "auto").strip().casefold()
    if wanted in {"whisper", "auto"} and WhisperTranscriber.available():
        return WhisperTranscriber()
    if wanted in {"vosk", "auto"} and VoskTranscriber.available():
        try:
            return VoskTranscriber()
        except Exception:
            pass
    if wanted in {"typed", "manual", "off", "none"}:
        return ManualTranscriber("You chose typed mode, so Weronika will not listen by herself.")
    reasons = []
    if not WhisperTranscriber.available():
        reasons.append("faster-whisper is not installed")
    if not VoskTranscriber.available():
        reasons.append("vosk is not installed")
    return ManualTranscriber(
        "No speech engine is installed (" + "; ".join(reasons) + "). Run setup-calls.bat, "
        "or type what the caller says."
    )


#: What ``setup-calls.bat`` installs, and what each piece is for. The import name comes
#: first because that is what a readiness check can look for.
CALL_SETUP_PACKAGES: tuple[tuple[str, str, str], ...] = (
    ("sounddevice", "sounddevice", "hears the caller through a microphone or line-in"),
    ("faster_whisper", "faster-whisper", "the accurate speech engine (best on Hinglish)"),
    ("vosk", "vosk", "the light speech engine, used when Whisper is absent"),
    ("pyttsx3", "pyttsx3", "Weronika's voice on Windows"),
)


def speech_setup_status() -> dict[str, object]:
    """Report call-audio readiness without importing or downloading anything heavy.

    Same shape as :func:`weronika_agent.blueprint.blueprint_status`, so the orb and the
    hardware inventory can show both opt-in features the same way.
    """
    missing = [
        pip_name
        for import_name, pip_name, _purpose in CALL_SETUP_PACKAGES
        if importlib.util.find_spec(import_name) is None
    ]
    installed = [
        pip_name
        for import_name, pip_name, _purpose in CALL_SETUP_PACKAGES
        if importlib.util.find_spec(import_name) is not None
    ]
    transcriber = build_transcriber("auto")
    engine = transcriber.name
    engine_reason = str(transcriber.describe().get("reason") or "")
    route, note = pick_route()
    vosk_models = sorted((MODEL_ROOT / "vosk").glob("vosk-model*")) if (MODEL_ROOT / "vosk").is_dir() else []
    ready = engine != "typed" and route is not CallRoute.NONE
    return {
        "available": ready,
        "engine": engine,
        "engine_reason": engine_reason,
        "audio_route": route.value,
        "audio_note": note,
        "missing_packages": missing,
        "installed_packages": installed,
        "vosk_models": [item.name for item in vosk_models],
        "model_root": str(MODEL_ROOT),
        "setup_command": "weronika-py\\setup-calls.bat",
        "automatic": ready,
        "message": (
            f"Call audio is ready: {engine} for hearing, {route.value.replace('_', ' ')} for sound."
            if ready
            else "Install the optional call audio support with setup-calls.bat; until then "
            "Weronika answers calls in typed mode and says so out loud."
        ),
    }


# --------------------------------------------------------------------------- text-to-speech


class Speaker:
    """Base class: speaks one line and can be interrupted."""

    name = "none"

    def say(self, text: str) -> None:  # pragma: no cover - interface
        return None

    def interrupt(self) -> None:
        return None

    def voices(self) -> list[str]:
        return []

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "available": False, "reason": ""}


class SilentSpeaker(Speaker):
    """No voice engine: lines are shown in the orb and written to the transcript only."""

    name = "silent"

    def __init__(self, reason: str = "") -> None:
        self._reason = reason or "No voice engine is available on this computer."

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "available": False, "reason": self._reason}


class Pyttsx3Speaker(Speaker):
    """Offline speech through pyttsx3 (SAPI5 on Windows, NSSpeech on macOS, espeak elsewhere)."""

    name = "pyttsx3"

    def __init__(self, voice_hint: str = "", rate: int = 178) -> None:
        self._hint = voice_hint
        self._rate = rate
        self._engine = None
        self._lock = threading.Lock()
        self._speaking = False

    def _load(self):
        with self._lock:
            if self._engine is None:
                import pyttsx3  # type: ignore

                engine = pyttsx3.init()
                engine.setProperty("rate", self._rate)
                engine.setProperty("volume", 1.0)
                chosen = _choose_pyttsx3_voice(engine, self._hint)
                if chosen:
                    engine.setProperty("voice", chosen)
                self._engine = engine
            return self._engine

    @staticmethod
    def available() -> bool:
        try:
            import pyttsx3  # type: ignore  # noqa: F401
        except Exception:
            return False
        return True

    def voices(self) -> list[str]:
        try:
            engine = self._load()
            return [str(getattr(voice, "name", "") or getattr(voice, "id", "")) for voice in engine.getProperty("voices")]
        except Exception:
            return []

    def say(self, text: str) -> None:
        line = " ".join(str(text or "").split())
        if not line:
            return
        engine = self._load()
        self._speaking = True
        try:
            engine.stop()
            engine.say(line)
            engine.runAndWait()
        finally:
            self._speaking = False

    def interrupt(self) -> None:
        if not self._speaking:
            return
        try:
            self._load().stop()
        except Exception:
            pass

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "available": True, "reason": "", "voice_hint": self._hint}


def _choose_pyttsx3_voice(engine, hint: str) -> str:
    """Prefer a natural-sounding feminine voice, the way the orb picks Weronika's voice."""
    try:
        voices = engine.getProperty("voices") or []
    except Exception:
        return ""
    best = ""
    best_score = -1
    for voice in voices:
        name = str(getattr(voice, "name", "") or "").casefold()
        identifier = str(getattr(voice, "id", "") or "").casefold()
        text = f"{name} {identifier}"
        score = 0
        if any(word in text for word in _VOICE_HINTS):
            score += 20
        if hint and hint.casefold() in text:
            score += 60
        if any(tag in text for tag in ("en-in", "en_in", "india", "heera", "kalpana", "veena", "swara")):
            score += 25
        if "english" in text:
            score += 10
        if score > best_score:
            best_score = score
            best = str(getattr(voice, "id", "") or "")
    return best if best_score > 0 else ""


class PowerShellSpeaker(Speaker):
    """Windows voice with no Python dependency at all, via System.Speech.

    The text is sent as an encoded command, so nothing in the line can be read as
    PowerShell syntax — quoting a caller's words into a shell is exactly the mistake
    this avoids.
    """

    name = "powershell"

    def __init__(self, voice_hint: str = "", rate: int = 0) -> None:
        self._hint = voice_hint
        self._rate = rate
        self._process: subprocess.Popen | None = None

    @staticmethod
    def available() -> bool:
        if platform.system() != "Windows":
            return False
        return shutil.which("powershell") is not None or shutil.which("powershell.exe") is not None

    def _script(self, text: str) -> str:
        escaped = text.replace("'", "''")
        selection = (
            f"try {{ $synth.SelectVoiceByHints("
            f"[System.Speech.Synthesis.VoiceGender]::NotSet,"
            f"[System.Speech.Synthesis.VoiceAge]::NotSet,0,"
            f"'{self._hint.replace(chr(39), '')}') }} catch {{}}"
            if self._hint
            else ""
        )
        return (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"{selection} "
            f"$synth.Rate = {max(-5, min(5, int(self._rate)))}; "
            "$synth.SetOutputToDefaultAudioDevice(); "
            f"$synth.Speak('{escaped}'); "
            "$synth.Dispose()"
        )

    def say(self, text: str) -> None:
        line = " ".join(str(text or "").split())
        if not line:
            return
        encoded = base64.b64encode(self._script(line).encode("utf-16-le")).decode("ascii")
        executable = shutil.which("powershell") or shutil.which("powershell.exe") or "powershell"
        try:
            self._process = subprocess.Popen(
                [executable, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise AudioError(f"The Windows voice could not start: {exc}") from exc
        try:
            _out, err = self._process.communicate(timeout=TTS_TIMEOUT_SECONDS)
            code = self._process.returncode
        except subprocess.TimeoutExpired:
            self._process.kill()
            raise AudioError("The Windows voice took too long to speak that line.") from None
        finally:
            self._process = None
        if code != 0:
            detail = (err or b"").decode("utf-8", "replace").strip()[:200]
            raise AudioError(f"The Windows voice did not speak that line{f': {detail}' if detail else '.'}")

    def interrupt(self) -> None:
        """Stop mid-sentence, because the caller started talking over Weronika."""
        process = self._process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "available": True, "reason": "", "voice_hint": self._hint}


class CommandLineSpeaker(Speaker):
    """macOS ``say`` and Linux ``espeak-ng`` / ``spd-say`` / ``festival``."""

    def __init__(self, command: Sequence[str], name: str, voice_hint: str = "") -> None:
        self._command = list(command)
        self.name = name
        self._hint = voice_hint

    def say(self, text: str) -> None:
        line = " ".join(str(text or "").split())
        if not line:
            return
        try:
            completed = subprocess.run(
                [*self._command, line], capture_output=True, timeout=TTS_TIMEOUT_SECONDS, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AudioError(f"{self.name} could not speak that line: {exc}") from exc
        if completed.returncode != 0:
            raise AudioError(f"{self.name} did not speak that line.")

    def describe(self) -> dict[str, object]:
        return {"engine": self.name, "available": True, "reason": "", "voice_hint": self._hint}


def build_speaker(preference: str = "auto", voice_hint: str = "") -> Speaker:
    """Pick a voice engine that exists on this computer, in order of quality."""
    wanted = (preference or "auto").strip().casefold()
    if wanted == "silent":
        return SilentSpeaker("You switched Weronika's call voice off; she will show her lines instead.")
    if wanted in {"pyttsx3", "auto"} and Pyttsx3Speaker.available():
        return Pyttsx3Speaker(voice_hint=voice_hint)
    if wanted in {"powershell", "sapi", "auto"} and PowerShellSpeaker.available():
        return PowerShellSpeaker(voice_hint=voice_hint)
    if platform.system() == "Darwin":
        say = shutil.which("say")
        if say:
            command = [say, "-v", "Samantha"] if voice_hint == "" else [say, "-v", voice_hint]
            return CommandLineSpeaker(command, "say", voice_hint)
    for executable, name, extra in (
        ("espeak-ng", "espeak-ng", ["-v", "en+f3", "-s", "165"]),
        ("espeak", "espeak", ["-v", "en+f3", "-s", "165"]),
        ("spd-say", "spd-say", ["-w"]),
        ("flite", "flite", []),
    ):
        found = shutil.which(executable)
        if found:
            return CommandLineSpeaker([found, *extra], name, voice_hint)
    return SilentSpeaker(
        "No voice engine was found. Run setup-calls.bat to install one, or Weronika will "
        "show what she would say instead of speaking it."
    )


# --------------------------------------------------------------------------- pipeline


class LocalCallAudio:
    """The ``CallAudio`` the call service uses: one route, one ear, one voice."""

    def __init__(
        self,
        *,
        route: CallRoute = CallRoute.NONE,
        route_preference: CallRoute = CallRoute.NONE,
        route_note: str = "",
        transcriber: Transcriber | None = None,
        speaker: Speaker | None = None,
        language: str = "",
        reader: object = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._preference = route_preference
        self._route = route
        self._route_note = route_note
        if route is CallRoute.NONE:
            self._route, self._route_note = pick_route(route_preference)
        self._transcriber = transcriber if transcriber is not None else build_transcriber()
        self._speaker = speaker if speaker is not None else build_speaker()
        self._language = language
        self._reader = reader if reader is not None else UtteranceReader(clock=clock)
        self._spoken: list[tuple[str, float]] = []
        self._lock = threading.Lock()

    @property
    def automatic(self) -> bool:
        """True when Weronika can listen and speak by herself on this machine."""
        return bool(self._transcriber.automatic and self._route is not CallRoute.NONE)

    def route(self) -> CallRoute:
        return self._route

    def set_route(self, route: CallRoute) -> CallRoute:
        self._route, note = (route, "") if route is not CallRoute.NONE else pick_route(self._preference)
        self._route_note = note
        return self._route

    def capabilities(self) -> dict[str, object]:
        devices = list_devices()
        speech = self._transcriber.describe()
        voice = self._speaker.describe()
        available = self._route is not CallRoute.NONE
        reason = self._route_note or ""
        if not available and not reason:
            reason = "No audio route is available for a call on this computer."
        return {
            "available": available,
            "route": self._route.value,
            "reason": reason,
            "automatic": self.automatic,
            "speech": speech,
            "voice": voice,
            "devices": [item.to_dict() for item in devices[:12]],
            "device_count": len(devices),
            "routes": [
                {"route": item.value, "label": label}
                for item, label in (
                    (CallRoute.SPEAKER_MIC, "Phone on speaker, laptop microphone"),
                    (CallRoute.BLUETOOTH, "Bluetooth hands-free"),
                    (CallRoute.AUX, "3.5 mm cable into line-in"),
                )
            ],
            "language": self._language,
        }

    def hear(self, seconds: float) -> str:
        """Listen for one utterance and return its words, or "" if nothing was understood."""
        if not self._transcriber.automatic:
            return ""
        if self._route is CallRoute.NONE:
            raise AudioError("There is no audio route, so Weronika cannot hear the caller.")
        pcm = self._reader.read(seconds)
        if not pcm:
            return ""
        text = self._transcriber.transcribe(pcm, self._language)
        return " ".join(text.split())

    def say(self, text: str) -> None:
        line = " ".join(str(text or "").split())
        if not line:
            return
        with self._lock:
            self._spoken.append((line, time.time()))
            del self._spoken[:-40]
        self._speaker.say(line)

    def interrupt(self) -> None:
        self._speaker.interrupt()

    def said(self) -> list[dict[str, object]]:
        """What Weronika spoke, for the orb's live transcript."""
        with self._lock:
            return [{"text": text, "at": at} for text, at in self._spoken]


class ChannelAudio:
    """Uses the right ear for the channel that is live.

    A SIM call is heard through this computer's microphone (or a Bluetooth pairing); a
    WhatsApp Web call can be heard straight from the page's own audio stream. The call
    service says which channel it just answered with :meth:`bind`, and everything after
    that goes to the matching pipeline. Speaking always uses one voice, so Weronika sounds
    the same to a caller whichever way she reached the phone.
    """

    def __init__(self, phone_audio, browser_audio=None) -> None:
        self._phone = phone_audio
        self._browser = browser_audio
        self._channel = CallChannel.SIM

    def bind(self, channel: CallChannel) -> None:
        self._channel = channel

    @property
    def active(self):
        if self._browser is not None and self._channel is CallChannel.WHATSAPP:
            return self._browser
        return self._phone

    @property
    def automatic(self) -> bool:
        return bool(self.active.automatic)

    def route(self) -> CallRoute:
        return self.active.route()

    def capabilities(self) -> dict[str, object]:
        phone = self._phone.capabilities() if self._phone is not None else {"available": False}
        browser = (
            self._browser.capabilities()
            if self._browser is not None
            else {"available": False, "reason": "no WhatsApp window is open"}
        )
        report = dict(phone)
        report["active_channel"] = self._channel.value
        report["browser_route"] = browser
        report["automatic"] = self.automatic
        report["route"] = self.route().value
        return report

    def hear(self, seconds: float) -> str:
        return self.active.hear(seconds)

    def say(self, text: str) -> None:
        # One voice for every channel: the caller should not hear a different assistant
        # depending on how the call arrived.
        if self._phone is not None:
            self._phone.say(text)
        elif self._browser is not None:
            self._browser.say(text)

    def interrupt(self) -> None:
        for pipeline in (self._phone, self._browser):
            if pipeline is not None and hasattr(pipeline, "interrupt"):
                pipeline.interrupt()

    def said(self) -> list[dict[str, object]]:
        if self._phone is not None and hasattr(self._phone, "said"):
            return self._phone.said()
        return []
