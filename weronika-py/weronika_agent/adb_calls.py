"""SIM calls on a phone linked to this computer with a cable (Android Debug Bridge).

What this adapter really does:

* **Sees the call.** ``dumpsys telecom`` and ``dumpsys telephony.registry`` are read to
  find a ringing call, its state, and the number or name behind it. Both are parsed
  because different Android versions print them differently, and a state that cannot
  be read is reported as unknown rather than guessed.
* **Answers, rejects, hangs up, and turns on the speaker.** Every action is one of a
  short list of fixed key events or a tap on a button the phone is actually showing
  (found with ``uiautomator dump``), and the state is read back afterwards. If the
  verification fails, the adapter says so instead of pretending the call was answered.
* **Resolves the caller's name** from the phone's own contacts by number, so the orb can
  ask you "Are you able to handle the call?" with a name and not just digits.

What it cannot do, stated plainly so nobody is surprised mid-call:

* **Audio does not travel through the cable.** Android does not expose call audio over
  ADB. The voice has to move by air or wire — the phone on speaker with this computer's
  microphone and speakers, a Bluetooth hands-free pairing, or a 3.5 mm cable into
  line-in. :mod:`call_audio` owns those routes; this module only reports which route the
  *phone* is using so the two can be compared.
* **An iPhone cannot be driven this way.** iOS offers no equivalent of ``adb`` for
  answering a cellular call, so iPhone users get the WhatsApp route instead.
* Nothing is ever typed into your phone as free text. Only fixed key events and taps on
  buttons the phone itself lists are sent; a serial number or phone number is used in a
  command only after it matches a strict pattern.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from .calls import IncomingCall
from .models import CallChannel, CallRoute

ADB_COMMAND_TIMEOUT_SECONDS = 8
UI_DUMP_TIMEOUT_SECONDS = 12
# How often the cable is re-checked for a phone. A scan loop runs every couple of
# seconds, and `adb devices` plus two `getprop` calls is too much to repeat that often.
DEVICE_REFRESH_SECONDS = 10.0

# `adb devices` serials look like "emulator-5554", "RZ8M12ABC", or "192.168.1.5:5555".
_SERIAL_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")
# E.164-ish: an optional + and digits. Anything else is never used in a command.
_NUMBER_RE = re.compile(r"^\+?[0-9]{3,16}$")

_RINGING_STATES = {"ringing", "incoming", "ring", "alerting"}
_ACTIVE_STATES = {"active", "offhook", "off_hook", "dialing", "on_hold", "held", "audio_processing"}
_ENDED_STATES = {"idle", "disconnected", "terminated", "none", "unknown_call_state"}

# Ordered because the reliable one differs by Android version and by OEM skin.
ANSWER_KEYEVENTS = ("KEYCODE_CALL", "KEYCODE_HEADSETHOOK")
END_KEYEVENTS = ("KEYCODE_ENDCALL",)

# Buttons on the in-call screen, in the languages Weronika's owner is likely to see.
_ACCEPT_WORDS = (
    "accept", "answer", "swipe to answer", "tap to answer", "receive",
    "स्वीकार", "स्वीकार करें", "उत्तर दें", "जवाब दें", "उठाएं",
)
_DECLINE_WORDS = (
    "decline", "reject", "end", "deny", "swipe to decline",
    "अस्वीकार", "अस्वीकार करें", "काट दें", "इनकार",
)
_SPEAKER_WORDS = ("speaker", "speakerphone", "loud speaker", "स्पीकर", "लाउड स्पीकर")

# Last-resort speakerphone commands. They exist on some Android versions and not on
# others, so each is attempted only until `dumpsys audio` confirms the route changed.
_SPEAKER_COMMANDS = (
    ("cmd", "audio", "set-communication-device", "speaker"),
    ("cmd", "phone", "set-speakerphone", "true"),
)


class AdbError(RuntimeError):
    """An expected, user-actionable problem talking to the phone."""


@dataclass(frozen=True)
class PhoneDevice:
    serial: str
    model: str = ""
    android_version: str = ""
    authorized: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "serial": self.serial,
            "model": self.model or "unknown model",
            "android_version": self.android_version or "unknown version",
            "authorized": self.authorized,
        }


@dataclass(frozen=True)
class PhoneCall:
    """One call the phone reports, before it becomes a tracked item."""

    state: str
    number: str = ""
    name: str = ""
    is_video: bool = False
    call_id: str = ""

    @property
    def ringing(self) -> bool:
        return self.state in _RINGING_STATES

    @property
    def active(self) -> bool:
        return self.state in _ACTIVE_STATES


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str], float], CommandResult]


def _subprocess_runner(args: Sequence[str], timeout: float) -> CommandResult:
    try:
        completed = subprocess.run(
            list(args), capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return CommandResult(127, "", "command not found")
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "timed out")
    except OSError as exc:
        return CommandResult(1, "", str(exc))
    return CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")


def find_adb(explicit: str | None = None) -> str:
    """Locate the adb executable: an override, the environment, or PATH.

    The common Windows location (``%LOCALAPPDATA%\\Android\\Sdk\\platform-tools``) is
    checked too, because that is where Android Studio leaves it and it is rarely on PATH.
    """
    candidate = (explicit or os.environ.get("WERONIKA_ADB") or "").strip()
    if candidate:
        return candidate if os.path.isabs(candidate) or os.path.exists(candidate) else candidate
    found = shutil.which("adb")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        guess = os.path.join(local, "Android", "Sdk", "platform-tools", "adb.exe")
        if os.path.exists(guess):
            return guess
    home = os.path.expanduser("~")
    for guess in (
        os.path.join(home, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
        os.path.join(home, "Android", "Sdk", "platform-tools", "adb"),
        "/usr/lib/android-sdk/platform-tools/adb",
        "/opt/homebrew/bin/adb",
    ):
        if os.path.exists(guess):
            return guess
    return ""


# --------------------------------------------------------------------------- parsing


def parse_call_state(telecom: str, registry: str = "") -> list[PhoneCall]:
    """Read the phone's call state from two dumps, tolerating both formats.

    ``dumpsys telecom`` groups its output per call with keys such as ``state``,
    ``handle`` and ``callerDisplayName``; some builds instead print one line per call,
    and ``dumpsys telephony.registry`` carries a single ``mCallState`` integer with
    ``mCallIncomingNumber``. The richest source that yields a call wins, so a version
    this worker has not seen still reports "something is ringing" instead of nothing.
    """
    for parse in (_parse_telecom, _parse_inline):
        calls = parse(telecom or "")
        if calls:
            return calls
    for parse in (_parse_registry, _parse_inline):
        calls = parse(registry or "")
        if calls:
            return calls
    return []


_STATE_WORD_RE = re.compile(
    r"\b(?:RINGING|INCOMING|ACTIVE|DIALING|ON_HOLD|DISCONNECTED|IDLE)\b", re.IGNORECASE
)
_INLINE_NUMBER_RE = re.compile(r"\b(?:tel:)?(\+?\d{5,15})\b")
_INLINE_NAME_RE = re.compile(
    # Stop at the next key= so "callerDisplayName=Priya video=false" yields "Priya".
    r"\b(?:callerDisplayName|caller_display_name|displayName|name)\b\s*[:=]\s*"
    r"(.+?)(?=\s+[A-Za-z_][A-Za-z0-9_]*\s*[:=]|\s*$)",
    re.IGNORECASE,
)


def _parse_inline(text: str) -> list[PhoneCall]:
    """Handle builds that print a call on one line, e.g. ``Call@f2a: RINGING tel:+91…``.

    A line only counts when it also looks like call data — a ``state``/``handle`` key or a
    phone number — so legend lines that merely list possible states are not mistaken for
    a ringing call.
    """
    found: list[PhoneCall] = []
    seen: set[tuple[str, str]] = set()
    for index, line in enumerate((text or "").splitlines()):
        match = _STATE_WORD_RE.search(line)
        if not match:
            continue
        state = _normalize_state(match.group(0))
        if state in _ENDED_STATES or state == "unknown_call_state":
            continue
        digits = _INLINE_NUMBER_RE.search(line)
        number = _clean_number(digits.group(1) if digits else "")
        # Require real call data on the line, so a legend such as "state can be RINGING
        # or ACTIVE" in the same dump is never mistaken for a ringing call.
        looks_like_call = bool(
            re.search(
                r"\b(?:state|handle|address|callerDisplayName|callerNumber)\b\s*[:=]",
                line,
                re.IGNORECASE,
            )
            or "tel:" in line.casefold()
            or (digits is not None and len(digits.group(1)) >= 7)
        )
        if not looks_like_call:
            continue
        name_match = _INLINE_NAME_RE.search(line)
        name = name_match.group(1).strip().strip('"') if name_match else ""
        video = bool(re.search(r"\bvideo\b\s*[:=]?\s*(?:true|1)", line, re.IGNORECASE))
        identity = (state, number or name or str(index))
        if identity in seen:
            continue
        seen.add(identity)
        found.append(
            PhoneCall(state=state, number=number, name=name, is_video=video, call_id=str(index))
        )
    return found


def _parse_telecom(text: str) -> list[PhoneCall]:
    """Group telecom's per-call blocks. Keys vary in case and in spacing across versions."""
    groups: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^(?:Call|call|CALL)\s*#?\s*\d*\s*:?$", line) or re.match(
            r"^call\s*#?\d+", line, re.IGNORECASE
        ):
            current = {}
            groups.append(current)
            continue
        if current is None:
            # Keys can appear before any "Call #n" header on some builds.
            current = {}
            groups.append(current)
        match = re.match(r"^([A-Za-z][A-Za-z0-9_ .]{0,40}?)\s*[:=]\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip().casefold().replace(" ", "_")
        value = match.group(2).strip().strip(",").strip('"')
        if not value:
            continue
        current.setdefault(key, value)

    calls: list[PhoneCall] = []
    for index, group in enumerate(groups):
        state = _normalize_state(
            group.get("state") or group.get("call_state") or group.get("status") or ""
        )
        if state in _ENDED_STATES and not group:
            continue
        number = _clean_number(
            group.get("handle")
            or group.get("address")
            or group.get("callernumber")
            or group.get("caller_number")
            or group.get("number")
            or ""
        )
        name = (
            group.get("callerdisplayname")
            or group.get("caller_display_name")
            or group.get("displayname")
            or group.get("name")
            or ""
        ).strip()
        video = str(group.get("video") or group.get("is_video") or "").casefold() in {"true", "1", "yes"}
        if state in _ENDED_STATES and not number and not name:
            continue
        calls.append(
            PhoneCall(state=state, number=number, name=name, is_video=video, call_id=str(index))
        )
    live = [call for call in calls if call.state not in _ENDED_STATES]
    if live:
        return live
    # A call block whose state this worker cannot read is still reported: it is better
    # to ask you about a call than to stay silent about one. A state that was read and
    # says "disconnected" is never resurrected.
    return [call for call in calls if call.state == "unknown_call_state"][:1]


def _parse_registry(text: str) -> list[PhoneCall]:
    state_match = re.search(r"mCallState\s*=\s*(\w+)", text)
    number_match = re.search(r"mCallIncomingNumber\s*=\s*([+\d]*)", text)
    if not state_match:
        return []
    raw = state_match.group(1).strip()
    mapping = {"0": "idle", "1": "ringing", "2": "active", "idle": "idle", "ringing": "ringing",
               "offhook": "active", "active": "active"}
    state = mapping.get(raw.casefold(), _normalize_state(raw))
    if state in _ENDED_STATES:
        return []
    number = _clean_number(number_match.group(1) if number_match else "")
    return [PhoneCall(state=state, number=number, call_id="0")]


def _normalize_state(value: str) -> str:
    cleaned = re.sub(r"[^a-z_]", "", str(value or "").casefold().replace(" ", "_").replace("-", "_"))
    cleaned = cleaned.strip("_")
    if not cleaned:
        return "unknown_call_state"
    if cleaned in _RINGING_STATES:
        return "ringing"
    if cleaned in _ACTIVE_STATES:
        return "active"
    if cleaned in _ENDED_STATES or cleaned in {"0", "1", "2"}:
        return {"0": "idle", "1": "ringing", "2": "active"}.get(cleaned, cleaned)
    return cleaned


def _clean_number(value: str) -> str:
    """Reduce a handle such as ``tel:+919876543210`` to digits, or "" if it is not one."""
    text = str(value or "").strip()
    if text.startswith("tel:"):
        text = text[4:]
    text = re.sub(r"[^+\d]", "", text)
    return text if _NUMBER_RE.match(text) else ""


def parse_audio_route(dumpsys_audio: str) -> CallRoute:
    """Which output the phone is using for a call: speaker, wired headset, or Bluetooth."""
    text = (dumpsys_audio or "").casefold()
    # The communication device is the one that matters during a call, and it is printed
    # in a few shapes across versions.
    patterns = (
        (r"bluetooth[_ ]?sco|bt[_ ]?sco|bluetooth headset|ble_headset", CallRoute.BLUETOOTH),
        (r"wired[_ ]?headset|usb[_ ]?headset|headphones|line[_ ]?analog|3\.5", CallRoute.AUX),
        (r"speaker|built[_ ]?in[_ ]?speaker|earpiece", CallRoute.SPEAKER_MIC),
    )
    scoped = re.search(
        r"(?:communication device|current communication|setcommunicationdevice)[^\n]{0,160}", text
    )
    haystack = scoped.group(0) if scoped else text[:4000]
    for pattern, route in patterns:
        if re.search(pattern, haystack):
            return route
    for pattern, route in patterns:
        if re.search(pattern, text):
            return route
    return CallRoute.NONE


def parse_uiautomator_buttons(dump: str, words: Sequence[str]) -> list[tuple[int, int, str]]:
    """Find tappable in-call buttons in a ``uiautomator dump`` XML by their label.

    Returns centre coordinates and the label that matched. Bounds look like
    ``[24,1450][336,1594]``; a node without bounds cannot be tapped and is skipped.
    """
    wanted = [word.casefold() for word in words]
    found: list[tuple[int, int, str]] = []
    for node in re.finditer(r"<node\b[^>]*>", dump or ""):
        tag = node.group(0)
        if 'clickable="true"' not in tag:
            continue
        labels = re.findall(r'(?:text|content-desc)="([^"]*)"', tag)
        label = next((item for item in labels if item.strip()), "")
        lowered = label.strip().casefold()
        if not lowered or not any(word in lowered for word in wanted):
            continue
        bounds = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        if not bounds:
            continue
        left, top, right, bottom = (int(value) for value in bounds.groups())
        if right <= left or bottom <= top:
            continue
        found.append(((left + right) // 2, (top + bottom) // 2, label.strip()))
    return found


def parse_contact_name(query_output: str) -> str:
    """Read the display name out of a `content query` row for one phone number."""
    for line in (query_output or "").splitlines():
        match = re.search(r"display_name(?:=|:)\s*([^,]+)", line)
        if match:
            return match.group(1).strip()
    return ""


# --------------------------------------------------------------------------- adapter


class PhoneCallAdapter:
    """Drives one Android phone over ``adb``. One instance per linked device."""

    def __init__(
        self,
        device: PhoneDevice | None = None,
        *,
        adb: str | None = None,
        runner: Runner | None = None,
    ) -> None:
        self._adb = adb if adb is not None else find_adb()
        self._run = runner or _subprocess_runner
        self._device = device
        # A device handed to the constructor counts as freshly scanned, so a test or an
        # explicit binding is not immediately replaced by whatever the cable reports.
        self._scanned_at = time.monotonic() if device is not None else 0.0
        self.channel = CallChannel.SIM

    def refresh(self, *, force: bool = False) -> PhoneDevice | None:
        """Re-check the cable for a phone, at most once every few seconds.

        The worker starts before you plug the phone in, and you may unplug it mid-session,
        so the bound device is re-discovered rather than fixed at start-up. A device given
        to the constructor is kept, and is only re-scanned after the throttle expires.
        """
        now = time.monotonic()
        if not force and now - self._scanned_at < DEVICE_REFRESH_SECONDS:
            return self._device
        if not self._adb:
            self._scanned_at = now
            return None
        phones = list_phones(adb=self._adb, runner=self._run)
        self._scanned_at = time.monotonic()
        usable = [phone for phone in phones if phone.authorized]
        self._device = usable[0] if usable else (phones[0] if phones else None)
        return self._device

    def forget_device(self) -> None:
        """Drop the bound phone after it stops answering, so the next scan re-discovers."""
        self._device = None
        self._scanned_at = 0.0

    # ------------------------------------------------------------------ plumbing

    @property
    def device(self) -> PhoneDevice | None:
        return self._device

    def _shell(self, *args: str, timeout: float = ADB_COMMAND_TIMEOUT_SECONDS) -> CommandResult:
        if not self._adb:
            raise AdbError("adb was not found on this computer.")
        if self._device is None:
            raise AdbError("No phone is linked, so there is nothing to send a command to.")
        command = [self._adb, "-s", self._device.serial, "shell", *args]
        return self._run(command, timeout)

    def _out(self, *args: str, timeout: float = ADB_COMMAND_TIMEOUT_SECONDS) -> str:
        result = self._shell(*args, timeout=timeout)
        if result.returncode != 0 and not result.stdout.strip():
            detail = " ".join((result.stderr or "").split())[:200]
            raise AdbError(f"`{' '.join(args[:2])} …` failed on the phone{f': {detail}' if detail else '.'}")
        return result.stdout

    def _read_state(self) -> list[PhoneCall]:
        """Read both dumps. If neither can be read, say so instead of implying "idle"."""
        telecom = ""
        registry = ""
        errors: list[str] = []
        try:
            telecom = self._out("dumpsys", "telecom")
        except AdbError as exc:
            errors.append(str(exc))
        try:
            registry = self._out("dumpsys", "telephony.registry")
        except AdbError as exc:
            errors.append(str(exc))
        if len(errors) == 2:
            self.forget_device()
            raise AdbError(
                "The phone would not report its call state, so Weronika cannot tell whether it is "
                f"ringing. ({errors[0]})"
            )
        return parse_call_state(telecom, registry)

    # -------------------------------------------------------------- capabilities

    def capabilities(self) -> dict[str, object]:
        self.refresh()
        if not self._adb:
            return {
                "available": False,
                "detect": False,
                "answer": False,
                "reason": (
                    "adb is not installed on this computer. Install Android platform-tools, "
                    "or set WERONIKA_ADB to the adb executable."
                ),
            }
        if self._device is None:
            return {
                "available": False,
                "detect": False,
                "answer": False,
                "reason": "No Android phone is linked over the cable right now.",
            }
        if not self._device.authorized:
            return {
                "available": False,
                "detect": False,
                "answer": False,
                "reason": (
                    f"The phone {self._device.serial} is connected but has not allowed USB debugging. "
                    "Unlock it and tap “Allow” on the debugging prompt."
                ),
                "device": self._device.to_dict(),
            }
        report: dict[str, object] = {
            "available": True,
            "detect": True,
            "answer": True,
            "hang_up": True,
            "decline": True,
            "speaker": True,
            "device": self._device.to_dict(),
            "audio_over_cable": False,
            "reason": "",
            "note": (
                "The call can be answered over the cable, but its audio cannot: Android does not "
                "send call audio through adb. Use the phone's speaker with this computer's "
                "microphone, a Bluetooth hands-free pairing, or a 3.5 mm cable into line-in."
            ),
        }
        try:
            route = self.phone_audio_route()
            report["phone_audio_route"] = route.value
        except AdbError as exc:
            report["phone_audio_route"] = CallRoute.NONE.value
            report["phone_audio_note"] = str(exc)
        return report

    def phone_audio_route(self) -> CallRoute:
        """What the phone itself is using for call audio right now."""
        return parse_audio_route(self._out("dumpsys", "audio"))

    # ------------------------------------------------------------------ detection

    def ringing_calls(self) -> list[IncomingCall]:
        """Every call the phone reports as ringing or connected."""
        self.refresh()
        calls: list[IncomingCall] = []
        now = time.time()
        for call in self._read_state():
            if not (call.ringing or call.active):
                continue
            name = call.name or self.lookup_name(call.number)
            calls.append(
                IncomingCall(
                    channel=CallChannel.SIM,
                    call_id=call.call_id or call.number or "sim-call",
                    caller=name,
                    number=call.number,
                    seen_at=now,
                    is_video=call.is_video,
                    device=self._device.serial if self._device else "",
                    active=call.active,
                )
            )
        return calls

    def lookup_name(self, number: str) -> str:
        """Ask the phone's own contacts for the name behind a number. Best effort only."""
        if not _NUMBER_RE.match(number or ""):
            return ""
        # The number is validated above and is quoted, so this stays a fixed query shape.
        where = f"data1='{number}'"
        try:
            output = self._out(
                "content", "query",
                "--uri", "content://com.android.contacts/data/phones",
                "--projection", "display_name:data1",
                "--where", where,
            )
        except AdbError:
            return ""
        name = parse_contact_name(output)
        if name:
            return name
        # Some builds match only the local form, so retry without the country code.
        local = number.lstrip("+")[-10:]
        if local and local != number:
            try:
                output = self._out(
                    "content", "query",
                    "--uri", "content://com.android.contacts/data/phones",
                    "--projection", "display_name:data1",
                    "--where", f"data1 LIKE '%{local}'",
                )
            except AdbError:
                return ""
            return parse_contact_name(output)
        return ""

    def is_active(self, call=None) -> bool:
        """True when the phone reports a connected call — used to verify an answer."""
        try:
            states = self._read_state()
        except AdbError:
            return False
        return any(item.active for item in states)

    def is_ringing(self) -> bool:
        try:
            states = self._read_state()
        except AdbError:
            return False
        return any(item.ringing for item in states)

    # ------------------------------------------------------------------- actions

    def answer(self, call=None) -> None:
        """Answer the ringing call, checking after each attempt that it connected."""
        for keyevent in ANSWER_KEYEVENTS:
            self._shell("input", "keyevent", keyevent)
            if self.is_active():
                return
        if self._tap_button(_ACCEPT_WORDS):
            if self.is_active():
                return
        raise AdbError(
            "The phone did not confirm the call was answered. It may need the screen unlocked, "
            "or this model answers with a swipe the worker cannot verify."
        )

    def hang_up(self, call=None) -> None:
        for keyevent in END_KEYEVENTS:
            self._shell("input", "keyevent", keyevent)
            if not self.is_active():
                return
        if self._tap_button(_DECLINE_WORDS):
            if not self.is_active():
                return
        raise AdbError("The phone still reports a connected call after hanging up.")

    def decline(self, call=None) -> None:
        """Reject a ringing call. Ending it while ringing is a rejection on Android."""
        if not self.is_ringing():
            return
        if self._tap_button(_DECLINE_WORDS):
            return
        for keyevent in END_KEYEVENTS:
            self._shell("input", "keyevent", keyevent)
            if not self.is_ringing():
                return

    def set_speaker(self, call=None, enabled: bool = True) -> None:
        """Put the phone on speaker so this computer can hear it. Best effort, reported."""
        if not enabled:
            self._tap_button(_SPEAKER_WORDS)
            return
        before = self.phone_audio_route()
        if before is CallRoute.SPEAKER_MIC:
            return
        if self._tap_button(_SPEAKER_WORDS):
            if self.phone_audio_route() is CallRoute.SPEAKER_MIC:
                return
        for command in _SPEAKER_COMMANDS:
            self._shell(*command)
            if self.phone_audio_route() is CallRoute.SPEAKER_MIC:
                return
        # Not fatal: with a Bluetooth or wired route the speaker is not needed at all.

    def _tap_button(self, words: Sequence[str]) -> bool:
        """Dump the visible UI and tap the first button whose label matches ``words``."""
        dump = ""
        for path in ("/sdcard/window_dump.xml", "/sdcard/weronika_ui_dump.xml"):
            result = self._shell("uiautomator", "dump", path, timeout=UI_DUMP_TIMEOUT_SECONDS)
            if result.returncode == 0:
                read = self._shell("cat", path, timeout=UI_DUMP_TIMEOUT_SECONDS)
                if read.stdout.strip().startswith("<"):
                    dump = read.stdout
                    break
        if not dump:
            return False
        buttons = parse_uiautomator_buttons(dump, words)
        if not buttons:
            return False
        x, y, _label = buttons[0]
        self._shell("input", "tap", str(x), str(y))
        return True


# --------------------------------------------------------------------------- discovery


def list_phones(adb: str | None = None, runner: Runner | None = None) -> list[PhoneDevice]:
    """List Android devices linked over the cable, with their authorization state."""
    executable = adb if adb is not None else find_adb()
    run = runner or _subprocess_runner
    if not executable:
        return []
    result = run([executable, "devices"], ADB_COMMAND_TIMEOUT_SECONDS)
    devices: list[PhoneDevice] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or not _SERIAL_RE.match(parts[0]):
            continue
        state = parts[1].casefold()
        if state in {"offline", "unauthorized"}:
            devices.append(PhoneDevice(serial=parts[0], authorized=False))
            continue
        if state != "device":
            continue
        devices.append(PhoneDevice(serial=parts[0], model="", android_version="", authorized=True))

    for device in devices:
        if not device.authorized:
            continue
        adapter = PhoneCallAdapter(device, adb=executable, runner=run)
        try:
            model = adapter._out("getprop", "ro.product.model").strip()
            version = adapter._out("getprop", "ro.build.version.release").strip()
        except AdbError:
            model, version = "", ""
        devices[devices.index(device)] = PhoneDevice(
            serial=device.serial,
            model=" ".join(model.split())[:60],
            android_version=" ".join(version.split())[:20],
            authorized=True,
        )
    return devices


def adapter_for_first_phone(adb: str | None = None, runner: Runner | None = None) -> PhoneCallAdapter | None:
    phones = list_phones(adb=adb, runner=runner)
    if not phones:
        return None
    return PhoneCallAdapter(phones[0], adb=adb if adb is not None else find_adb(), runner=runner)
