"""Small, serializable models shared by Weronika's local messaging automation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Platform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    X = "x"

    @classmethod
    def parse(cls, value: str) -> "Platform":
        normalized = value.strip().casefold().replace("twitter", "x").replace("messenger", "facebook")
        if normalized == "instagram dm":
            normalized = "instagram"
        try:
            return cls(normalized)
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ValueError(f"Unsupported platform. Choose one of: {supported}.") from exc


PLATFORM_DISPLAY: dict["Platform", str] = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "instagram": "Instagram",
    "facebook": "Messenger",
    "x": "X",
}


def platform_display(platform: "Platform") -> str:
    return PLATFORM_DISPLAY.get(platform.value, platform.value.title())


class CallChannel(str, Enum):
    """Where an incoming call rings.

    ``sim`` is an ordinary cellular call on a phone linked to this computer;
    ``whatsapp`` is a call in the signed-in WhatsApp Web window. Telegram is
    listed so the worker can say plainly that it cannot handle Telegram calls
    instead of leaving the user guessing.
    """

    SIM = "sim"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"

    @classmethod
    def parse(cls, value: str) -> "CallChannel":
        normalized = value.strip().casefold().replace("wa", "whatsapp").replace("tg", "telegram")
        if normalized in {"phone", "cell", "cellular", "mobile", "carrier", "adb", "android"}:
            normalized = "sim"
        if normalized in {"telegram call", "telegram calls"}:
            normalized = "telegram"
        try:
            return cls(normalized)
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise ValueError(f"Unsupported call channel. Choose one of: {supported}.") from exc


CALL_CHANNEL_DISPLAY: dict["CallChannel", str] = {
    "sim": "phone (SIM)",
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
}


def call_channel_display(channel: "CallChannel") -> str:
    return CALL_CHANNEL_DISPLAY.get(channel.value, channel.value.title())


class CallPhase(str, Enum):
    """The life of one incoming call.

    ``awaiting_user`` is the state the feature exists for: the call is ringing and
    Weronika has asked "Are you able to handle the call, or should I?" Nothing is
    answered while a call sits in this phase.
    """

    RINGING = "ringing"
    AWAITING_USER = "awaiting_user"
    ANSWERING = "answering"
    LIVE = "live"
    HANDOVER = "handover"
    ENDED = "ended"
    DECLINED = "declined"
    MISSED = "missed"
    FAILED = "failed"


ACTIVE_CALL_PHASES = {CallPhase.RINGING, CallPhase.AWAITING_USER, CallPhase.ANSWERING, CallPhase.LIVE}


class CallDecision(str, Enum):
    """Your answer to "Are you able to handle the call?" — for that one call."""

    WERONIKA = "weronika"
    USER = "user"
    IGNORE = "ignore"

    @classmethod
    def parse(cls, value: str) -> "CallDecision":
        """Understand the answer however it was said, in English or Hinglish.

        The order matters: refusals are checked before "take it" phrasings (so
        "don't answer" is never read as an instruction to answer), and "I'll take
        it" is checked before the bare "take it" that means Weronika should.
        """
        text = (
            " ".join(str(value or "").replace(",", " ").split()).casefold().strip(" .!?")
        )
        if not text:
            raise ValueError("Choose who takes the call: weronika, user, or ignore.")
        if text in {item.value for item in cls}:
            return cls(text)

        # An explicit first-person claim beats everything: "don't answer, I'll take
        # it" means you take it, not that the call should be ignored.
        claims_the_call = re.compile(
            r"\b(?:i'?ll|i will|i am|i'?m|let me|main|mai)\b[\s\w,'-]*"
            r"\b(?:tak\w*|handl\w*|answer\w*|pick\w*|attend\w*|talk\w*|speak\w*|get|got|"
            r"utha\w*|le\s+lo|baat\w*|on it)\b"
        )
        keeps_the_call = re.compile(
            r"^(?:me|myself|i|leave it to me|hand it over|give (?:it|the phone|the call) to me|"
            r"pass (?:it|the phone)|i'?m on it|mine|apna)\b"
        )
        if claims_the_call.search(text) or keeps_the_call.match(text):
            return cls.USER

        ignore = re.compile(
            # A refusal runs to the end of the sentence ("do not pick up the call"),
            # and the first-person check above already caught "don't …, I'll take it".
            r"^(?:no\s+)?(?:please\s+)?(?:just\s+)?"
            r"(?:ignore|skip|reject|decline|cancel|drop|don'?t|do not|never|no need to)"
            r"[\w\s'!,.]*"
            r"|^(?:let it (?:ring|go)|leave it(?: ringing| alone)?|no need|nahi uthao|mat uthao|"
            r"mat uthana|chhod do|rehne do|cut kar do|उठाना मत|छोड़ दो)[\w\s'!,.]*"
            r"|^(?:no|nope|nahi|nahin)\s*$"
        )
        if ignore.match(text):
            return cls.IGNORE

        user = re.compile(
            r"^(?:i(?:'ll|'?ll| will| am|'?m| can| shall)?|me|myself)\s*"
            r"(?:tak\w*|handl\w*|answer\w*|pick\w*|attend\w*|get|got|talk\w*|speak\w*|do|see|on it)\b.*"
            r"|^(?:me|myself|i|let me|leave it to me)\s*$"
            r"|^(?:main|mai|hum)\s+\w+"
            r"|\b(?:let me|give it to me|hand it over|pass (?:it|the phone)|i'?m on (?:it|the call)|"
            r"main uthaunga|main uthaungi|main le leta|main baat kar)\b"
        )
        if user.match(text):
            return cls.USER

        weronika = re.compile(
            # Any order of acknowledgement, addressee, and modal before the verb:
            # "take it", "you take it", "can you take the call", "please do answer".
            r"^(?:\b(?:yes|yeah|yep|haan|ji|ok|okay|sure|please|kindly|go ahead|do it)\b[\s,]*)*"
            r"(?:\b(?:you|weronika|veronica|she|her|bot|ai|assistant|can|could|should|would|"
            r"will|shall|please|kindly|just|go ahead and|ji)\b[\s,]*){0,4}"
            r"\b(?:handle|take|answer|pick|attend|talk|speak|deal)\w*\b.*"
            r"|^(?:you|her|she|bot|ai|veronica|weronika|yes|yeah|haan|ji|ok|okay|sure|go ahead|please|"
            r"handle it|take it|answer it|pick it up|attend it|yes please|you first|do it|assistant|"
            r"tum utha lo?|aap utha(?:o|iye)|aap baat karo|weronika (?:uthao|se baat)|"
            r"उठा लो|बात करो)\s*$"
            r"|\b(?:go ahead|you (?:handle|take|answer|pick)|weronika (?:handles|takes|answers)|"
            r"let (?:her|weronika) \w+|she (?:can |will )?(?:handle|take|answer)|"
            r"handle (?:it|the call)|answer (?:it|the call)|pick (?:it|the call) up|"
            r"tum utha lo|aap utha lo)\b"
        )
        if weronika.match(text):
            return cls.WERONIKA

        raise ValueError(
            "Weronika did not catch who should take the call. Say “you handle it”, "
            "“I'll take it”, or “ignore it”."
        )


class CallRoute(str, Enum):
    """How call audio reaches this computer, and Weronika's voice reaches the call."""

    SPEAKER_MIC = "speaker_mic"
    BLUETOOTH = "bluetooth"
    AUX = "aux"
    BROWSER = "browser"
    NONE = "none"

    @classmethod
    def parse(cls, value: str) -> "CallRoute":
        normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
        aliases = {
            "speaker": cls.SPEAKER_MIC,
            "speakerphone": cls.SPEAKER_MIC,
            "mic": cls.SPEAKER_MIC,
            "bt": cls.BLUETOOTH,
            "handsfree": cls.BLUETOOTH,
            "hands_free": cls.BLUETOOTH,
            "headset": cls.BLUETOOTH,
            "cable": cls.AUX,
            "line_in": cls.AUX,
            "linein": cls.AUX,
            "aux_cable": cls.AUX,
            "web": cls.BROWSER,
            "browser_tap": cls.BROWSER,
        }
        if normalized in {item.value for item in cls}:
            return cls(normalized)
        if normalized in aliases:
            return aliases[normalized]
        raise ValueError("Choose an audio route: speaker_mic, bluetooth, aux, browser, or none.")


class WatchMode(str, Enum):
    """What Weronika does with an incoming message she is watching."""

    ASK = "ask"
    PROPOSE = "propose"


class WatchRule(str, Enum):
    """Which incoming messages count as waiting for the user's reply."""

    UNANSWERED = "unanswered"
    URGENT = "urgent"


class WatchState(str, Enum):
    NEW = "new"
    AWAITING_REVIEW = "awaiting_review"
    AWAITING_USER = "awaiting_user"
    HELD = "held"
    SENT = "sent"
    SENT_UNVERIFIED = "sent_unverified"
    DECLINED = "declined"
    EXPIRED = "expired"
    FAILED = "failed"


def parse_watch_mode(value: str) -> WatchMode:
    try:
        return WatchMode(value.strip().casefold())
    except ValueError as exc:
        raise ValueError("Reply watch has two modes: ask or propose.") from exc


def parse_watch_rule(value: str) -> WatchRule:
    try:
        return WatchRule(value.strip().casefold())
    except ValueError as exc:
        raise ValueError("Reply watch can watch for unanswered or urgent messages.") from exc


class WorkflowStage(str, Enum):
    NEEDS_RECIPIENT = "needs_recipient"
    AWAITING_RECIPIENT_CHOICE = "awaiting_recipient_choice"
    PREPARING = "preparing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SENDING = "sending"
    SENT = "sent"
    SENT_UNVERIFIED = "sent_unverified"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class VisibleContact:
    """A result currently visible in the target app's chat/contact list."""

    source_id: str
    display_name: str


@dataclass(frozen=True)
class RecipientCandidate:
    id: str
    display_name: str
    confidence: float
    exact: bool = False
    context: str = ""
    source_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MessageDraft:
    id: str
    platform: Platform
    requested_recipient: str
    message: str
    candidates: list[RecipientCandidate] = field(default_factory=list)
    selected_recipient: str | None = None
    stage: WorkflowStage = WorkflowStage.NEEDS_RECIPIENT
    created_at: float = 0.0
    updated_at: float = 0.0
    result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_id": self.id,
            "platform": self.platform.value,
            "requested_recipient": self.requested_recipient,
            "message": self.message,
            "selected_recipient": self.selected_recipient,
            "stage": self.stage.value,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "result": self.result,
        }


@dataclass(frozen=True)
class IntentParseResult:
    handled: bool
    platform: Platform | None = None
    recipient: str = ""
    message: str = ""
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "handled": self.handled,
            "platform": self.platform.value if self.platform else None,
            "recipient": self.recipient,
            "message": self.message,
            "prompt": self.prompt,
        }
