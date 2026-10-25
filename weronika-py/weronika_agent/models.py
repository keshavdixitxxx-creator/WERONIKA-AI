"""Small, serializable models shared by Weronika's local messaging automation."""

from __future__ import annotations

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
