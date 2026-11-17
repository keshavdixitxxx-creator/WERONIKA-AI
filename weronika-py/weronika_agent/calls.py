"""Call handling: watch for a ringing call, ask you first, then talk for you.

This is the call-side twin of :mod:`reply_watch`, with the same confirmation-first
shape and two extra rules that calls need and messages do not:

1. **Every call asks.** When a call starts ringing, Weronika asks you
   *"Are you able to handle the call, or should I?"* and waits. A previous "you
   handle it" is never carried over to the next call, and there is no always-answer
   setting to turn on. ``configure`` refuses ``auto_answer`` on purpose.
2. **Every answered call discloses.** Her first spoken words say that she is an AI
   assistant and not a human. The caller can ask again and gets the same answer.

What she can do on the call: listen, understand, answer in the caller's language,
take a message, offer a callback, refuse to read out codes or make decisions for
you, hand the phone back when you arrive, hang up politely, and write a summary you
can send on WhatsApp or Telegram through the existing messaging flow (which still
needs your ``confirm send``).

What she will not do: answer without asking you, pretend to be you, promise
anything, invent facts, or keep a call open past its time limit.

The channel adapters (phone over cable, WhatsApp Web) and the audio pipeline are
injected, so this module holds no device or audio code and is fully testable.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Protocol, Sequence

from .call_dialogue import (
    DISCLOSURE_CONFIRMATION,
    DISCLOSURE_TEMPLATE,
    GOODBYE,
    GOODBYE_HANDED_BACK,
    MISHEARD_TWICE,
    RE_DISCLOSURE_QUESTION,
    SECRET_REFUSAL,
    SILENCE_NUDGE,
    SpokenLine,
    caller_asks_for_human,
    caller_is_done,
    detect_secret,
    fallback_line,
    fill,
    redact_secrets,
    summary_lines,
    telegram_unsupported_note,
)
from .contacts import normalize_name
from .models import (
    ACTIVE_CALL_PHASES,
    CallChannel,
    CallDecision,
    CallPhase,
    CallRoute,
    call_channel_display,
)

MAX_ITEMS = 12
MAX_TURNS = 60
MAX_TRANSCRIPT_CHARS = 12_000
MAX_CONTACT_FILTERS = 10
MAX_CONTACT_FILTER_CHARS = 60
ITEM_TTL_SECONDS = 12 * 60 * 60

# How long the "are you able to handle the call?" question waits for your answer
# before Weronika says so and stops re-asking. The phone's own ring timeout still
# decides when the call becomes missed.
DECISION_WINDOW_SECONDS = 45
REMINDER_SECONDS = 12

DEFAULT_MAX_CALL_SECONDS = 6 * 60
MIN_MAX_CALL_SECONDS = 30
HARD_MAX_CALL_SECONDS = 30 * 60

DEFAULT_LISTEN_SECONDS = 6.0
MAX_LISTEN_SECONDS = 20.0

# Two mishearings in a row, then three silences, end a call rather than loop.
MAX_MISHEARD_IN_A_ROW = 2
MAX_SILENCE_IN_A_ROW = 3


class CallWatchError(RuntimeError):
    """An expected, user-actionable call-handling error."""


# --------------------------------------------------------------------------- models


@dataclass(frozen=True)
class IncomingCall:
    """One call a channel adapter can see ringing or talking."""

    channel: CallChannel
    call_id: str
    caller: str = ""
    number: str = ""
    seen_at: float = 0.0
    is_video: bool = False
    device: str = ""
    active: bool = False

    @property
    def key(self) -> str:
        identity = self.call_id or self.number or normalize_name(self.caller) or "unknown"
        return f"{self.channel.value}:{self.device}:{identity}".casefold()


@dataclass(frozen=True)
class CallTurn:
    """One line of the call transcript."""

    speaker: str  # "caller", "weronika", or "you"
    text: str
    at: float = 0.0
    source: str = ""  # how it was heard or written: stt provider, "typed", "disclosure"
    withheld: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "age_seconds": 0,
            "source": self.source,
            "withheld": self.withheld,
        }


@dataclass
class CallItem:
    """One incoming call and everything Weronika decided or said about it."""

    id: str
    channel: CallChannel
    caller: str
    number: str
    is_video: bool = False
    device: str = ""
    phase: CallPhase = CallPhase.RINGING
    decision: CallDecision | None = None
    call: IncomingCall | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    asked_at: float = 0.0
    reminder_at: float = 0.0
    reminder_sent: bool = False
    answered_at: float = 0.0
    ended_at: float = 0.0
    route: CallRoute = CallRoute.NONE
    disclosed: bool = False
    turns: list[CallTurn] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    outcome: str = ""
    summary: str = ""
    last_error: str = ""
    last_spoken: str = ""
    silence_in_a_row: int = 0
    # The adapter that reported this call, kept so the same channel answers and hangs
    # up. Typed loosely because CallAdapter is declared below this dataclass.
    adapter: object = field(default=None, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    # Serialises one caller turn: listening, answering and speaking happen in order
    # even when the live loop and the orb push words at the same time.
    turn_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def transcript(self) -> list[tuple[str, str]]:
        return [(turn.speaker, turn.text) for turn in self.turns]

    @property
    def seconds(self) -> int:
        if not self.answered_at:
            return 0
        end = self.ended_at or time.time()
        return max(0, int(end - self.answered_at))

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def to_dict(self) -> dict[str, object]:
        now = time.time()
        turns: list[dict[str, object]] = []
        for turn in self.turns:
            payload = turn.to_dict()
            payload["age_seconds"] = max(0, int(now - turn.at)) if turn.at else 0
            turns.append(payload)
        return {
            "item_id": self.id,
            "channel": self.channel.value,
            "channel_display": call_channel_display(self.channel),
            "caller": self.caller or "Unknown caller",
            "number": self.number,
            "is_video": self.is_video,
            "device": self.device,
            "phase": self.phase.value,
            "decision": self.decision.value if self.decision else "",
            "route": self.route.value,
            "disclosed": self.disclosed,
            "asked": bool(self.asked_at),
            "reminder_sent": self.reminder_sent,
            "seconds": self.seconds,
            "turns": turns,
            "transcript": [{"speaker": speaker, "text": text} for speaker, text in self.transcript],
            "flags": list(self.flags),
            "outcome": self.outcome,
            "summary": self.summary,
            "last_spoken": self.last_spoken,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class CallResult:
    item: CallItem
    prompt: str

    def to_dict(self) -> dict[str, object]:
        payload = self.item.to_dict()
        payload["prompt"] = self.prompt
        return payload


class CallAdapter(Protocol):
    """One channel a call can arrive on: a phone over cable, or WhatsApp Web."""

    @property
    def channel(self) -> CallChannel: ...

    def capabilities(self) -> dict[str, object]:
        """What this channel can really do on this machine, right now."""
        ...

    def ringing_calls(self) -> list[IncomingCall]:
        """Calls currently ringing or already talking on this channel."""
        ...

    def answer(self, call: IncomingCall) -> None: ...

    def hang_up(self, call: IncomingCall) -> None: ...

    def decline(self, call: IncomingCall) -> None: ...

    def set_speaker(self, call: IncomingCall, enabled: bool) -> None: ...

    def is_active(self, call: IncomingCall) -> bool:
        """True when the adapter can verify the call was really answered."""
        ...


class CallAudio(Protocol):
    """Hears the caller and speaks Weronika's lines on this computer."""

    def capabilities(self) -> dict[str, object]: ...

    def route(self) -> CallRoute: ...

    def hear(self, seconds: float) -> str:
        """Return what the caller said, or "" when nothing was understood."""
        ...

    def say(self, text: str) -> None: ...

    def interrupt(self) -> None:
        """Stop speaking at once, because the caller started talking."""
        ...

    @property
    def automatic(self) -> bool:
        """True when Weronika can listen by herself; False in typed/manual mode."""
        ...


class CallResponder(Protocol):
    def __call__(self, context: dict[str, object], transcript: Sequence[tuple[str, str]]) -> SpokenLine: ...


# --------------------------------------------------------------------------- service


class CallWatchService:
    """Ask about each ringing call, then handle only the ones you hand over."""

    def __init__(
        self,
        adapters: Sequence[CallAdapter] | None = None,
        audio: CallAudio | None = None,
        *,
        clock: Callable[[], float] = time.time,
        responder: CallResponder | None = None,
        messaging: object = None,
    ) -> None:
        self._adapters: list[CallAdapter] = list(adapters or [])
        self._audio = audio
        self._clock = clock
        self._responder = responder or (
            lambda context, transcript: SpokenLine(
                fallback_line(
                    transcript,
                    owner=str(context.get("owner") or ""),
                    misheard=int(context.get("misheard") or 0),
                )
            )
        )
        self._messaging = messaging
        self._items: dict[str, CallItem] = {}
        self._by_call: dict[str, str] = {}
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}
        self._contacts: list[str] = []
        self._unknown_only = False
        self._enabled = True
        self._channels: set[CallChannel] = {CallChannel.SIM, CallChannel.WHATSAPP}
        self._pending_secret: tuple[str, str] | None = None
        self._owner = "Commander"
        self._language = ""
        self._max_call_seconds = DEFAULT_MAX_CALL_SECONDS
        self._decision_seconds = DECISION_WINDOW_SECONDS
        self._listen_seconds = DEFAULT_LISTEN_SECONDS
        self._route_preference = CallRoute.NONE
        self._speaking_secret_ok = False

    # ------------------------------------------------------------------ settings

    @property
    def responder(self) -> CallResponder:
        """The wording source, so an example call uses the same brain as a real one."""
        return self._responder

    @property
    def enabled(self) -> bool:
        return self._enabled

    def configure(self, raw: dict[str, object]) -> dict[str, object]:
        """Set which calls to watch and how long a handled call may run.

        Deliberately missing: any "always answer" switch. Consent is per call.
        """
        if any(str(key).casefold() in {"auto_answer", "always_answer", "answer_all"} for key in raw):
            raise CallWatchError(
                "Weronika cannot be set to answer calls automatically. She asks about each "
                "call, because only you know whether you can take it."
            )
        if "enabled" in raw:
            self._enabled = bool(raw.get("enabled"))
            if not self._enabled:
                # Switching off mid-call must not leave a caller talking to nobody.
                self.stop_all("Call handling was switched off.")
        if "channels" in raw:
            wanted = raw.get("channels")
            if isinstance(wanted, str):
                wanted = [part for part in re.split(r"[,;|\s]+", wanted) if part.strip()]
            parsed: set[CallChannel] = set()
            for entry in wanted or []:
                channel = CallChannel.parse(str(entry))
                if channel is CallChannel.TELEGRAM:
                    raise CallWatchError(telegram_unsupported_note())
                parsed.add(channel)
            if parsed:
                self._channels = parsed
        if "contacts" in raw:
            contacts = raw.get("contacts") or []
            if isinstance(contacts, str):
                contacts = [part for part in re.split(r"[,;|]", contacts) if part.strip()]
            cleaned = [
                " ".join(str(name).split())[:MAX_CONTACT_FILTER_CHARS]
                for name in contacts
                if str(name).strip()
            ]
            self._contacts = cleaned[:MAX_CONTACT_FILTERS]
        if "unknown_only" in raw:
            self._unknown_only = bool(raw.get("unknown_only"))
        if "owner" in raw:
            owner = " ".join(str(raw.get("owner") or "").split())[:60]
            self._owner = owner or "Commander"
        if "language" in raw:
            self._language = " ".join(str(raw.get("language") or "").split())[:40]
        if "max_call_seconds" in raw:
            self._max_call_seconds = _clamp_int(
                raw.get("max_call_seconds"),
                MIN_MAX_CALL_SECONDS,
                HARD_MAX_CALL_SECONDS,
                DEFAULT_MAX_CALL_SECONDS,
            )
        if "decision_seconds" in raw:
            self._decision_seconds = _clamp_int(
                raw.get("decision_seconds"), 5, DECISION_WINDOW_SECONDS * 4, DECISION_WINDOW_SECONDS
            )
        if "listen_seconds" in raw:
            seconds = _clamp_int(raw.get("listen_seconds"), 1, int(MAX_LISTEN_SECONDS), int(DEFAULT_LISTEN_SECONDS))
            self._listen_seconds = float(seconds)
        if "route" in raw:
            value = str(raw.get("route") or "").strip().casefold()
            if value in {"", "auto", "best"}:
                self._route_preference = CallRoute.NONE
            else:
                self._route_preference = CallRoute.parse(value)
        return self.settings()

    def settings(self) -> dict[str, object]:
        return {
            "enabled": self._enabled,
            "channels": sorted(channel.value for channel in self._channels),
            "contacts": list(self._contacts),
            "unknown_only": self._unknown_only,
            "owner": self._owner,
            "language": self._language,
            "max_call_seconds": self._max_call_seconds,
            "decision_seconds": self._decision_seconds,
            "listen_seconds": self._listen_seconds,
            "route": self._route_preference.value,
            "asks_every_call": True,
            "discloses_every_call": True,
        }

    def capabilities(self) -> dict[str, object]:
        """Report, per channel, what is actually available on this machine.

        A channel that cannot be driven is listed with the reason, so the orb shows
        an honest line instead of a button that silently does nothing.
        """
        channels: list[dict[str, object]] = []
        for adapter in self._adapters:
            try:
                report = dict(adapter.capabilities())
            except Exception as exc:  # pragma: no cover - adapter specific
                report = {"available": False, "reason": f"could not be checked ({exc})"}
            report.setdefault("channel", adapter.channel.value)
            report.setdefault("channel_display", call_channel_display(adapter.channel))
            channels.append(report)
        audio_report: dict[str, object] = {"available": False, "reason": "no audio pipeline configured"}
        route = CallRoute.NONE
        if self._audio is not None:
            try:
                audio_report = dict(self._audio.capabilities())
                route = self._audio.route()
            except Exception as exc:  # pragma: no cover - audio specific
                audio_report = {"available": False, "reason": f"could not be checked ({exc})"}
        audio_report.setdefault("route", route.value)
        return {
            "channels": channels,
            "audio": audio_report,
            "settings": self.settings(),
            "enabled": self._enabled,
            "asks_every_call": True,
            "discloses_every_call": True,
            "telegram": telegram_unsupported_note(),
        }

    # --------------------------------------------------------------------- scan

    def scan(self, *, progress: Callable[[str], None] | None = None) -> dict[str, object]:
        """Look for ringing calls once. The orb calls this every couple of seconds."""
        if not self._enabled:
            return {
                "raised": [],
                "gone": [],
                "items": [],
                "active": [],
                "awaiting": [],
                "notes": ["Call handling is switched off."],
                "prompt": (
                    "Call handling is switched off, so Weronika is not watching for calls. "
                    "Say “handle my calls” to switch it on."
                ),
            }
        now = self._clock()
        with self._lock:
            self._prune(now)
        raised: list[CallItem] = []
        notes: list[str] = []
        ringing_keys: set[str] = set()

        for adapter in self._adapters:
            if not self._channel_wanted(adapter.channel):
                continue
            try:
                report = adapter.capabilities()
            except Exception as exc:
                report = {"available": False, "reason": str(exc)}
            if not report.get("available"):
                notes.append(
                    f"{call_channel_display(adapter.channel)}: {report.get('reason') or 'not available'}"
                )
                continue
            try:
                calls = adapter.ringing_calls()
            except Exception as exc:
                notes.append(f"{call_channel_display(adapter.channel)}: could not read the call state ({exc}).")
                continue
            for call in calls:
                ringing_keys.add(call.key)
                if not self._call_wanted(call):
                    continue
                item = self._raise_call(call, adapter, now, progress)
                if item is not None:
                    raised.append(item)

        gone = self._close_vanished(ringing_keys, now, progress)
        with self._lock:
            items = sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)
            active = [item for item in items if item.phase in ACTIVE_CALL_PHASES]
            awaiting = [item for item in active if item.phase == CallPhase.AWAITING_USER]
        return {
            "raised": [self._payload(item) for item in raised],
            "gone": [self._payload(item) for item in gone],
            "items": [self._payload(item) for item in items[:MAX_ITEMS]],
            "active": [self._payload(item) for item in active],
            "awaiting": [self._payload(item) for item in awaiting],
            "notes": notes,
            "prompt": self._scan_prompt(raised, awaiting, notes),
        }

    def _payload(self, item: CallItem) -> dict[str, object]:
        """One call as data for the orb, carrying the question while it is still undecided.

        The orb polls ``/api/call/status`` every couple of seconds, so the ask-first question
        has to travel with the item: a ringing call without its question is a call the orb
        can only show as a name and a number.
        """
        payload = item.to_dict()
        payload["question"] = self.prompt(item) if item.phase is CallPhase.AWAITING_USER else ""
        return payload

    def _scan_prompt(
        self,
        raised: Sequence[CallItem],
        awaiting: Sequence[CallItem],
        notes: Sequence[str],
    ) -> str:
        if raised:
            return self.prompt(raised[0])
        if awaiting:
            return self.prompt(awaiting[0])
        if notes:
            return "Weronika could not watch every channel. " + str(notes[0])
        return "No call is ringing on the channels you asked me to watch."

    def _raise_call(
        self,
        call: IncomingCall,
        adapter: CallAdapter,
        now: float,
        progress: Callable[[str], None] | None,
    ) -> CallItem | None:
        with self._lock:
            existing_id = self._by_call.get(call.key)
            if existing_id and existing_id in self._items:
                existing = self._items[existing_id]
                if existing.phase in ACTIVE_CALL_PHASES:
                    if call.active and existing.phase == CallPhase.AWAITING_USER:
                        # You answered on the phone yourself while she was asking.
                        existing.phase = CallPhase.HANDOVER
                        existing.decision = CallDecision.USER
                        existing.outcome = "You picked the call up yourself."
                        existing.updated_at = now
                        self._notify(progress, "You took this call, so Weronika stepped back.")
                    return None
                if now - existing.updated_at < 60:
                    # The same call re-appeared right after ending; do not re-ask.
                    return None
            item = CallItem(
                id=f"call-{uuid.uuid4().hex[:10]}",
                channel=call.channel,
                caller=call.caller,
                number=call.number,
                is_video=call.is_video,
                device=call.device,
                phase=CallPhase.AWAITING_USER,
                call=call,
                created_at=now,
                updated_at=now,
                asked_at=now,
                reminder_at=now + REMINDER_SECONDS,
                route=self._current_route(),
                adapter=adapter,
            )
            self._items[item.id] = item
            self._by_call[call.key] = item.id
        prompt = self.prompt(item)
        self._notify(progress, prompt)
        return item

    def _close_vanished(
        self, ringing_keys: set[str], now: float, progress: Callable[[str], None] | None
    ) -> list[CallItem]:
        """A ringing call that stopped ringing was missed, or answered elsewhere."""
        closed: list[CallItem] = []
        with self._lock:
            for item in list(self._items.values()):
                if item.phase not in {CallPhase.RINGING, CallPhase.AWAITING_USER}:
                    continue
                if item.call is None or item.call.key in ringing_keys:
                    continue
                item.phase = CallPhase.MISSED
                item.ended_at = now
                item.updated_at = now
                item.outcome = "The call stopped ringing before anyone answered."
                item.stop()
                closed.append(item)
                self._notify(
                    progress,
                    f"Missed call from {item.caller or 'an unknown number'} on "
                    f"{call_channel_display(item.channel)}. Weronika did not answer it.",
                )
        return closed

    def _call_wanted(self, call: IncomingCall) -> bool:
        if self._unknown_only:
            return not call.caller or call.caller == call.number
        if not self._contacts:
            return True
        needle = normalize_name(call.caller) or normalize_name(call.number)
        if not needle:
            return False
        return any(
            needle in normalize_name(name) or normalize_name(name) in needle for name in self._contacts
        )

    def _channel_wanted(self, channel: CallChannel) -> bool:
        # Telegram is never watched: it has no calls to watch (see telegram_unsupported_note).
        return channel in self._channels and channel is not CallChannel.TELEGRAM

    def _current_route(self) -> CallRoute:
        if self._audio is None:
            return CallRoute.NONE
        try:
            route = self._audio.route()
        except Exception:
            return CallRoute.NONE
        if self._route_preference is not CallRoute.NONE and route is not self._route_preference:
            return route
        return route

    # ------------------------------------------------------------------ decide

    def prompt(self, item: CallItem) -> str:
        """The question this feature exists for: asked once per call, never inferred."""
        who = item.caller or ("an unknown number" if not item.number else item.number)
        where = call_channel_display(item.channel)
        kind = "video call" if item.is_video else "call"
        return (
            f"Incoming {kind} from {who} on {where}. "
            "Are you able to handle the call, or should I take it? "
            "Say “you handle it” and I will answer and tell them I am your AI assistant, "
            "or “I'll take it” and I will leave it to you."
        )

    def review_hint(self, item_id: str) -> str:
        return self.prompt(self._item(item_id))

    def decide(
        self,
        item_id: str,
        decision: str,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> CallResult:
        """Your answer for this one call: Weronika takes it, you take it, or ignore."""
        choice = CallDecision.parse(decision)
        item = self._item(item_id)
        now = self._clock()
        if item.phase not in ACTIVE_CALL_PHASES:
            raise CallWatchError(
                f"That call already ended ({item.phase.value.replace('_', ' ')}), so there is nothing to decide."
            )
        adapter = self._adapter_for(item)

        if choice is CallDecision.USER:
            item.decision = choice
            item.phase = CallPhase.HANDOVER if item.answered_at else CallPhase.ENDED
            item.updated_at = now
            item.ended_at = now if not item.answered_at else item.ended_at
            item.outcome = "You took the call yourself."
            item.stop()
            return CallResult(item, f"Right, this one is yours. Weronika will not answer {item.caller or 'it'}.")

        if choice is CallDecision.IGNORE:
            item.decision = choice
            try:
                if adapter is not None and item.call is not None:
                    adapter.decline(item.call)
                item.phase = CallPhase.DECLINED
                item.outcome = "You asked Weronika to leave the call ringing."
            except Exception as exc:
                item.phase = CallPhase.FAILED
                item.last_error = str(exc)
                item.outcome = "Weronika could not reject the call, so it rang out."
            item.ended_at = now
            item.updated_at = now
            item.stop()
            return CallResult(item, f"Left alone — Weronika did not answer {item.caller or 'the call'}.")

        return self._answer(item, adapter, now, progress)

    def _answer(
        self,
        item: CallItem,
        adapter: CallAdapter | None,
        now: float,
        progress: Callable[[str], None] | None,
    ) -> CallResult:
        """Answer, disclose, and start listening. Fails loudly instead of half-answering."""
        if adapter is None or item.call is None:
            raise CallWatchError("The channel that reported this call is no longer available.")
        report = dict(adapter.capabilities())
        if not report.get("answer"):
            raise CallWatchError(
                f"{call_channel_display(item.channel)} calls can be seen but not answered here: "
                f"{report.get('reason') or 'this channel has no answer control'}."
            )
        audio_note = ""
        if self._audio is None or item.route is CallRoute.NONE:
            audio_note = (
                " Weronika has no audio route on this computer, so she will answer, say who she is, "
                "and then you will have to type what the caller says."
            )
        item.decision = CallDecision.WERONIKA
        item.phase = CallPhase.ANSWERING
        item.updated_at = now
        self._notify(progress, f"Answering the {call_channel_display(item.channel)} call from {item.caller or 'an unknown number'}…")
        try:
            adapter.answer(item.call)
        except Exception as exc:
            item.phase = CallPhase.FAILED
            item.last_error = str(exc)
            item.updated_at = self._clock()
            raise CallWatchError(f"Weronika could not answer the call: {exc}") from exc

        answered_at = self._clock()
        item.answered_at = answered_at
        item.updated_at = answered_at
        item.phase = CallPhase.LIVE
        item.route = self._current_route()
        # An audio pipeline that can hear more than one channel is told which call is live,
        # so a WhatsApp call is heard from the page and a SIM call from the microphone.
        bind = getattr(self._audio, "bind", None)
        if callable(bind):
            try:
                bind(item.channel)
                item.route = self._current_route()
            except Exception:
                pass
        try:
            adapter.set_speaker(item.call, True)
        except Exception:
            # Speakerphone is a convenience, not a requirement; keep going without it.
            pass

        disclosure = fill(DISCLOSURE_TEMPLATE, self._owner)
        self._speak(item, disclosure, source="disclosure", progress=progress)
        item.disclosed = True
        self._notify(progress, "Weronika told the caller she is an AI assistant.")
        prompt = (
            f"Weronika answered and said: “{disclosure}”{audio_note}\n"
            "She is listening now. Say “give me the call” to take over, “end the call” to hang up, "
            "or “say: …” to have her speak your exact words."
        )
        if self._audio is not None and self._audio.automatic:
            self._start_live_loop(item)
        else:
            self._notify(
                progress,
                "No speech engine is installed, so this call runs in typed mode: tell Weronika what the caller said.",
            )
        return CallResult(item, prompt)

    # ---------------------------------------------------------------- live call

    def hear(
        self,
        item_id: str,
        text: str,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> CallResult:
        """Feed the caller's words in typed mode and get Weronika's spoken answer.

        This is also how a misheard line is corrected: the text you type replaces
        what the speech engine thought it heard for this turn.
        """
        item = self._item(item_id)
        if item.phase not in {CallPhase.LIVE, CallPhase.ANSWERING}:
            raise CallWatchError("That call is not live, so there is nothing to answer.")
        spoken = " ".join(str(text or "").split())
        if not spoken:
            raise CallWatchError("Type what the caller said, or say “end the call”.")
        return self._take_caller_turn(item, spoken, source="typed", progress=progress)

    def dictate(
        self,
        item_id: str,
        text: str,
        *,
        read_secret: bool = False,
        progress: Callable[[str], None] | None = None,
    ) -> CallResult:
        """Speak your exact words on the call. Your text is the approval — she adds nothing."""
        item = self._item(item_id)
        if item.phase not in {CallPhase.LIVE, CallPhase.ANSWERING, CallPhase.HANDOVER}:
            raise CallWatchError("That call is not live, so Weronika cannot speak on it.")
        words = " ".join(str(text or "").split())
        if not words:
            raise CallWatchError("Give Weronika the exact words to say.")
        secret = detect_secret(words)
        if secret and not read_secret:
            _flag(item, f"You tried to have a {secret} read aloud; it was not spoken")
            with self._lock:
                self._pending_secret = (item.id, words)
            return CallResult(
                item,
                f"Weronika will not read a {secret} out on a call. If you really mean to, "
                "say “read it out anyway”.",
            )
        if secret and read_secret:
            _flag(item, f"A {secret} was read aloud at your explicit request")
        with self._lock:
            self._pending_secret = None
        self._speak(item, words, source="you", speaker="you", progress=progress)
        return CallResult(item, f"Weronika said your words: “{words}”")

    def retry_secret(self, *, progress: Callable[[str], None] | None = None) -> CallResult:
        """Speak the line that was withheld, after you insisted.

        Reading a code aloud on a phone call is how accounts get stolen, so it takes two
        steps: she refuses first, and only your explicit "read it out anyway" releases it.
        """
        with self._lock:
            pending = self._pending_secret
        if not pending:
            raise CallWatchError("There is nothing Weronika is holding back to read out.")
        item_id, words = pending
        return self.dictate(item_id, words, read_secret=True, progress=progress)

    def handover(self, item_id: str, *, progress: Callable[[str], None] | None = None) -> CallResult:
        """You arrived: she says so, stops talking, and leaves the line to you."""
        item = self._item(item_id)
        if item.phase not in {CallPhase.LIVE, CallPhase.ANSWERING, CallPhase.HANDOVER}:
            raise CallWatchError("That call is not live.")
        line = fill(GOODBYE_HANDED_BACK, self._owner)
        self._speak(item, line, source="handover", progress=progress)
        item.phase = CallPhase.HANDOVER
        item.outcome = "Handed back to you while the call stayed connected."
        item.updated_at = self._clock()
        item.stop()
        return CallResult(item, f"Weronika said “{line}” and stopped talking. The call is yours.")

    def end(
        self,
        item_id: str,
        reason: str = "",
        *,
        goodbye: bool = True,
        progress: Callable[[str], None] | None = None,
    ) -> CallResult:
        """Hang up. A live call gets a polite goodbye first, unless you say not to."""
        item = self._item(item_id)
        adapter = self._adapter_for(item)
        was_live = item.phase in {CallPhase.LIVE, CallPhase.ANSWERING, CallPhase.HANDOVER}
        if was_live and goodbye and item.disclosed:
            self._speak(item, fill(GOODBYE, self._owner), source="goodbye", progress=progress)
        if adapter is not None and item.call is not None:
            try:
                adapter.hang_up(item.call)
            except Exception as exc:
                item.last_error = str(exc)
                self._notify(progress, f"Weronika could not hang up: {exc}")
        now = self._clock()
        item.phase = CallPhase.ENDED
        item.ended_at = now
        item.updated_at = now
        item.outcome = " ".join(str(reason or "").split()) or (
            "Weronika ended the call after taking the message." if was_live else "The call ended."
        )
        item.summary = self.build_summary(item)
        item.stop()
        return CallResult(item, self._end_prompt(item))

    def _end_prompt(self, item: CallItem) -> str:
        base = f"The call with {item.caller or 'that number'} ended. {item.outcome}"
        if item.summary:
            base += f"\n\n{item.summary}"
        base += (
            "\n\nSay “send the summary on WhatsApp to <name>” and Weronika will prepare it "
            "for your confirmation."
        )
        return base

    def build_summary(self, item: CallItem) -> str:
        flags = list(dict.fromkeys(item.flags))
        return summary_lines(
            owner=self._owner,
            channel=call_channel_display(item.channel),
            caller=item.caller or "Unknown caller",
            number=item.number,
            seconds=item.seconds,
            transcript=item.transcript,
            flags=flags,
            outcome=item.outcome,
        )

    def prepare_summary_message(
        self, item_id: str, platform: str, recipient: str, *, progress: Callable[[str], None] | None = None
    ) -> dict[str, object]:
        """Hand the summary to the existing messaging flow — prepared, never sent."""
        item = self._item(item_id)
        if self._messaging is None:
            raise CallWatchError("Messaging is not available in this worker, so the summary cannot be prepared.")
        if not item.summary:
            item.summary = self.build_summary(item)
        from .models import Platform  # local import: keeps call code free of messaging setup

        target = Platform.parse(platform)
        draft = self._messaging.prepare(target, recipient, item.summary)  # type: ignore[attr-defined]
        self._notify(progress, f"Prepared the call summary for {recipient} on {target.value}; it is not sent yet.")
        return draft.to_dict()

    # ------------------------------------------------------------------ internals

    def _take_caller_turn(
        self,
        item: CallItem,
        text: str,
        *,
        source: str,
        progress: Callable[[str], None] | None = None,
    ) -> CallResult:
        """Record what the caller said, then decide and speak Weronika's answer.

        Speaking is deliberately outside the service lock: TTS can take seconds, and
        holding the lock that long would freeze ``/api/call/status`` for the orb.
        """
        with item.turn_lock:
            return self._turn(item, text, source=source, progress=progress)

    def _turn(
        self,
        item: CallItem,
        text: str,
        *,
        source: str,
        progress: Callable[[str], None] | None = None,
    ) -> CallResult:
        now = self._clock()
        secret = detect_secret(text)
        stored = redact_secrets(text) if secret else text
        item.turns.append(CallTurn("caller", stored, now, source, withheld=bool(secret)))
        item.silence_in_a_row = 0
        item.updated_at = now
        if secret:
            _flag(item, f"The caller spoke a {secret}; it was not repeated or stored")
            line = fill(SECRET_REFUSAL, self._owner)
            self._speak(item, line, source="safety", progress=progress)
            return CallResult(item, f"The caller mentioned a {secret}. Weronika refused to repeat it and told them so.")

        if RE_DISCLOSURE_QUESTION.search(text):
            _flag(item, "The caller asked whether this is an AI; she confirmed it")
            line = fill(DISCLOSURE_CONFIRMATION, self._owner)
            self._speak(item, line, source="disclosure", progress=progress)
            return CallResult(item, f"The caller asked who they were talking to. Weronika said: “{line}”")

        if caller_asks_for_human(text):
            _flag(item, "The caller asked for you personally")
        if caller_is_done(text):
            return self.end(item.id, "The caller had nothing more to add.", progress=progress)

        context = {
            "owner": self._owner,
            "channel": call_channel_display(item.channel),
            "caller": item.caller or item.number or "unknown",
            "seconds": item.seconds,
            # How many times she has already had to ask, so the wording can change
            # instead of repeating the same question three times.
            "misheard": item.silence_in_a_row,
            "language": self._language,
            "flags": list(item.flags),
        }
        try:
            line = self._responder(context, item.transcript)
        except Exception as exc:
            item.last_error = str(exc)
            line = SpokenLine(fallback_line(item.transcript, owner=self._owner), confirmed=False)
        if not isinstance(line, SpokenLine):
            line = SpokenLine(str(line or ""), confirmed=False)
        if not str(line).strip():
            line = SpokenLine(fallback_line(item.transcript, owner=self._owner), confirmed=False)
        if not line.confirmed:
            _flag(item, "Worded on this device — the hosted brain did not confirm this line")
        self._speak(item, str(line), source="brain" if line.confirmed else "local", progress=progress)
        return CallResult(item, f"Weronika answered: “{line}”")

    def _speak(
        self,
        item: CallItem,
        text: str,
        *,
        source: str,
        speaker: str = "weronika",
        progress: Callable[[str], None] | None = None,
    ) -> None:
        line = " ".join(str(text or "").split())
        if not line:
            return
        item.turns.append(CallTurn(speaker, line, self._clock(), source))
        item.last_spoken = line
        item.updated_at = self._clock()
        if self._audio is not None:
            try:
                self._audio.say(line)
            except Exception as exc:
                item.last_error = f"could not be heard on this call: {exc}"
                self._notify(progress, f"Weronika could not speak that line aloud: {exc}")
        self._notify(progress, f"Weronika said: “{line}”")
        if len(item.turns) > MAX_TURNS:
            del item.turns[: len(item.turns) - MAX_TURNS]

    def _start_live_loop(self, item: CallItem) -> None:
        with self._lock:
            thread = self._threads.get(item.id)
            if thread is not None and thread.is_alive():
                return
            worker = threading.Thread(target=self._live_loop, args=(item,), daemon=True)
            self._threads[item.id] = worker
            worker.start()

    def _live_loop(self, item: CallItem) -> None:
        """Listen → understand → answer, until the caller is done or time runs out."""
        assert self._audio is not None
        deadline = self._clock() + self._max_call_seconds
        while not item.stopped and self._clock() < deadline:
            with self._lock:
                if item.phase not in {CallPhase.LIVE, CallPhase.ANSWERING}:
                    return
            try:
                heard = self._audio.hear(self._listen_seconds)
            except Exception as exc:
                item.last_error = f"stopped listening: {exc}"
                self.end(item.id, "Weronika could not hear the caller any more.", goodbye=False)
                return
            if item.stopped:
                return
            text = " ".join(str(heard or "").split())
            if not text:
                item.silence_in_a_row += 1
                if item.silence_in_a_row == 2:
                    self._speak(item, fill(SILENCE_NUDGE, self._owner), source="silence")
                elif item.silence_in_a_row >= MAX_SILENCE_IN_A_ROW:
                    # Say something useful before hanging up, so the caller is not left
                    # talking to a line that simply went dead.
                    self._speak(item, fill(MISHEARD_TWICE, self._owner), source="silence")
                    self.end(item.id, "Weronika could not hear the caller.", goodbye=False)
                    return
                continue
            if self._audio is not None:
                try:
                    self._audio.interrupt()
                except Exception:
                    pass
            result = self._take_caller_turn(item, text, source="stt")
            if result.item.phase == CallPhase.ENDED:
                return
        if not item.stopped and item.phase in {CallPhase.LIVE, CallPhase.ANSWERING}:
            self.end(item.id, f"The call reached its {self._max_call_seconds // 60} minute limit.")

    # -------------------------------------------------------------------- state

    def list_state(self) -> dict[str, object]:
        now = self._clock()
        with self._lock:
            self._prune(now)
            items = sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)
            active = [item for item in items if item.phase in ACTIVE_CALL_PHASES]
            awaiting = [item for item in active if item.phase == CallPhase.AWAITING_USER]
            live = [item for item in active if item.phase in {CallPhase.LIVE, CallPhase.HANDOVER}]
            due = self._due_reminders(now)
        return {
            "items": [self._payload(item) for item in items[:MAX_ITEMS]],
            "active": [self._payload(item) for item in active],
            "awaiting": [self._payload(item) for item in awaiting],
            "live": [self._payload(item) for item in live],
            "reminders": due,
            "busy": bool(live),
            "audio": (self._audio.capabilities() if self._audio is not None else {"available": False}),
            "settings": self.settings(),
        }

    def _due_reminders(self, now: float) -> list[dict[str, object]]:
        """Re-ask once about a call that is still ringing and still undecided."""
        due: list[dict[str, object]] = []
        for item in self._items.values():
            if item.phase is not CallPhase.AWAITING_USER or item.reminder_sent:
                continue
            if item.reminder_at and now >= item.reminder_at:
                item.reminder_sent = True
                item.updated_at = now
                due.append({"item_id": item.id, "prompt": self.prompt(item)})
        return due

    def _prune(self, now: float) -> None:
        for item_id in list(self._items):
            item = self._items[item_id]
            if now - item.updated_at > ITEM_TTL_SECONDS and item.phase not in ACTIVE_CALL_PHASES:
                call = item.call
                del self._items[item_id]
                if call is not None and self._by_call.get(call.key) == item_id:
                    del self._by_call[call.key]

    def _item(self, item_id: str) -> CallItem:
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                # Fall back to the most recent call so "end the call" works with no id.
                if not item_id:
                    candidates = sorted(self._items.values(), key=lambda entry: entry.created_at, reverse=True)
                    live = [entry for entry in candidates if entry.phase in ACTIVE_CALL_PHASES]
                    if live:
                        return live[0]
                raise CallWatchError("That call is no longer being tracked. Say “scan calls” to look again.")
            return item

    def current(self) -> CallItem | None:
        with self._lock:
            candidates = sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)
            for item in candidates:
                if item.phase in ACTIVE_CALL_PHASES:
                    return item
        return None

    def _adapter_for(self, item: CallItem) -> CallAdapter | None:
        adapter = item.adapter
        if adapter is not None:
            return adapter  # type: ignore[return-value]
        for candidate in self._adapters:
            if candidate.channel is item.channel:
                return candidate
        return None

    def stop_all(self, reason: str = "Call handling was switched off.") -> None:
        """Hang up anything live, then stop watching. Used on shutdown and on 'stop'."""
        with self._lock:
            live = [item for item in self._items.values() if item.phase in ACTIVE_CALL_PHASES]
        for item in live:
            try:
                self.end(item.id, reason, goodbye=False)
            except CallWatchError:
                pass

    @staticmethod
    def _notify(progress: Callable[[str], None] | None, message: str) -> None:
        if progress is not None and message:
            progress(message)


def _flag(item: CallItem, note: str) -> None:
    """Add a note about the call once. Repeating it every turn would bury the summary."""
    if note not in item.flags:
        item.flags.append(note)


def _clamp_int(value: object, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(float(str(value)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
