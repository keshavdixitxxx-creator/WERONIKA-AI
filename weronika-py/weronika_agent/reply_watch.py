"""Reply watch: read incoming chats and step in only when the user has not replied.

Two modes, both confirmation-first:

* ``ask``     — Weronika tells the user a chat is waiting and asks what to reply.
* ``propose`` — Weronika reads the message, proposes an exact reply, and waits for
  the user's explicit "confirm send" before anything is typed.

Nothing is ever sent automatically. The reading side only inspects chats the user
named, in the visible browser session the user signed in to.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Protocol

from .contacts import normalize_name
from .models import (
    MessageDraft,
    Platform,
    RecipientCandidate,
    WatchMode,
    WatchRule,
    WatchState,
    parse_watch_mode,
    parse_watch_rule,
    platform_display,
)

MAX_CHAT_FILTER_CHARS = 80
MAX_REPLY_CHARS = 2000
MAX_TRACKED_TEXT_KEYS = 60
MAX_ITEMS = 25
MAX_WATCHES = 10
ALL_CHATS_LIMIT = 5
ITEM_TTL_SECONDS = 6 * 60 * 60
TIMEOUT_SECONDS = 15 * 60
MAX_REMINDER_SECONDS = 24 * 60 * 60
MAX_DELAY_SECONDS = 24 * 60 * 60
MAX_UNANSWERED_SECONDS = 7 * 24 * 60 * 60

ACTIVE_WATCH_STATES = {WatchState.NEW, WatchState.AWAITING_USER, WatchState.HELD}

_WORD_RE = re.compile(r"\w+", re.UNICODE)
_QUESTION_START_RE = re.compile(
    r"^(?:what|when|where|who|whom|why|how|which|can|could|will|would|are|is|am|do|does|did|shall|may|"
    r"kya|kab|kahan|kaun|kyun|kaise|kar|kro|kr|hogi|hoga|aayega|aayegi|hai|ho)\b",
    re.IGNORECASE,
)
_URGENT_WORDS = {
    "urgent", "asap", "immediately", "emergency", "now", "today", "tonight", "soon",
    "deadline", "important", "quick", "quickly", "hurry", "waiting", "please call",
    "call me", "ring me", "confirm", "approval", "last chance", "final",
    # Romanized Hindi / Hinglish
    "abhi", "turant", "jaldi", "zaroori", "zarurat", "aaj", "aaj hi", "fauran", "batao",
    # Devanagari
    "आज", "अभी", "जल्दी", "ज़रूरी", "जरूरी", "तुरंत", "फौरन", "बताओ",
}
# Phrases that usually mean "I cannot come / cannot make it" in everyday chats.
_ABSENCE_HINTS = (
    "not coming", "can't come", "cannot come", "won't come", "wont be able", "not able to come",
    "won't be able", "cant make it", "can't make it", "cannot make it", "not well", "sick",
    "on leave", "leave today", "taking leave", "nahi aa", "nahi aaunga", "nahi aaungi",
    "नहीं आ", "छुट्टी", "बीमार",
)


# --------------------------------------------------------------------------- models


@dataclass(frozen=True)
class IncomingMessage:
    """One message bubble that is visible in a chat and was not authored by the user."""

    platform: Platform
    chat_name: str
    message_id: str
    text: str
    is_group: bool = False
    sender: str = ""
    seen_at: float = 0.0


@dataclass(frozen=True)
class ChatSnapshot:
    """One row in a platform's visible chat/inbox list."""

    platform: Platform
    chat_name: str
    is_group: bool = False
    message_id: str = ""
    preview: str = ""

    @property
    def key(self) -> str:
        return f"{self.platform.value}:{normalize_name(self.chat_name)}"


@dataclass(frozen=True)
class ChatReading:
    """What the visible app currently shows for one chat."""

    chat_name: str
    is_group: bool = False
    messages: tuple[IncomingMessage, ...] = ()
    # True when the newest visible bubble is incoming, False when the user replied
    # last, None when the site's UI does not make the direction clear.
    last_is_incoming: bool | None = None


@dataclass(frozen=True)
class Detection:
    reason: str
    message: IncomingMessage


class ActivityAdapter(Protocol):
    """Read-only view of the messaging apps, plus chat opening for a prepared reply."""

    def list_chats(self, platform: Platform) -> list[ChatSnapshot]: ...

    def read_latest(self, platform: Platform, chat_name: str) -> ChatReading: ...

    def read_current_chat_draft(self, platform: Platform, chat_name: str) -> tuple[bool, str]: ...

    def open_chat(self, platform: Platform, candidate: RecipientCandidate) -> None: ...

    def verify_active_chat(self, platform: Platform, chat_name: str) -> bool: ...


class ReplyWatchError(RuntimeError):
    """An expected, user-actionable reply-watch error."""


@dataclass
class WatchItem:
    id: str
    platform: Platform
    chat_name: str
    chat_filter: str
    is_group: bool
    mode: WatchMode
    rule: WatchRule
    watch_id: str = ""
    keywords: list[str] = field(default_factory=list)
    delay_seconds: int = 0
    reminder_seconds: int = 0
    unanswered_after_seconds: int = 600
    state: WatchState = WatchState.NEW
    reason: str = ""
    message: IncomingMessage | None = None
    seen_at: float = 0.0
    created_at: float = 0.0
    updated_at: float = 0.0
    user_notified_at: float = 0.0
    reminder_at: float = 0.0
    reminder_sent: bool = False
    suggestion: str = ""
    draft: MessageDraft | None = None
    last_error: str = ""

    @property
    def chat_key(self) -> str:
        return f"{self.platform.value}:{normalize_name(self.chat_name)}"

    def to_dict(self) -> dict[str, object]:
        message = self.message
        return {
            "item_id": self.id,
            "platform": self.platform.value,
            "chat_name": self.chat_name,
            "chat_filter": self.chat_filter,
            "is_group": self.is_group,
            "mode": self.mode.value,
            "rule": self.rule.value,
            "keywords": list(self.keywords),
            "delay_seconds": self.delay_seconds,
            "reminder_seconds": self.reminder_seconds,
            "unanswered_after_seconds": self.unanswered_after_seconds,
            "state": self.state.value,
            "reason": self.reason,
            "suggestion": self.suggestion,
            "draft_id": self.draft.id if self.draft else "",
            "draft_stage": self.draft.stage.value if self.draft else "",
            "candidates": [candidate.to_dict() for candidate in self.draft.candidates]
            if self.draft
            else [],
            "reminder_sent": self.reminder_sent,
            "last_error": self.last_error,
            "message": (
                {
                    "from": message.sender or message.chat_name,
                    "text": message.text,
                    "is_group": message.is_group,
                    "age_seconds": max(0, int((self.updated_at or time.time()) - message.seen_at))
                    if message.seen_at
                    else 0,
                }
                if message
                else None
            ),
        }


@dataclass(frozen=True)
class WatchResult:
    item: WatchItem
    prompt: str

    def to_dict(self) -> dict[str, object]:
        payload = self.item.to_dict()
        payload["prompt"] = self.prompt
        return payload


# ------------------------------------------------------------------ text helpers


def word_list(value: str) -> list[str]:
    return _WORD_RE.findall(str(value or "").casefold())


def looks_like_question(text: str) -> bool:
    value = " ".join(str(text or "").split())
    if not value:
        return False
    if "?" in value or "¿" in value or "؟" in value:
        return True
    if value.endswith((".", "!", "।")):
        return bool(_QUESTION_START_RE.match(value))
    return bool(_QUESTION_START_RE.match(value))


def match_score(query: str, candidate: str) -> float:
    """Lenient chat-name match used only to *resolve a chat the user named*."""
    q = normalize_name(query)
    c = normalize_name(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if len(q) < 3:
        return 0.0
    if c.startswith(q) or q in c:
        return 0.92
    return SequenceMatcher(None, q, c).ratio()


def find_chat(snapshot: list[ChatSnapshot], query: str, *, minimum: float = 0.84) -> ChatSnapshot | None:
    """Return the single best visible chat, or None when it is missing/ambiguous."""
    scored = sorted(
        ((match_score(query, item.chat_name), item) for item in snapshot),
        key=lambda row: row[0],
        reverse=True,
    )
    if not scored or scored[0][0] < minimum:
        return None
    if len(scored) > 1 and scored[1][0] >= scored[0][0] - 0.02:
        return None  # two equally good chats: never guess
    return scored[0][1]


def message_key(message: IncomingMessage) -> str:
    if message.message_id:
        return f"id:{message.message_id}"
    return f"tx:{normalize_name(message.sender)}|{normalize_name(message.text)[:120]}"


def is_urgent(message: IncomingMessage, keywords: list[str]) -> bool:
    text = message.text
    folded = text.casefold()
    tokens = set(word_list(text))
    for keyword in keywords:
        cleaned = " ".join(str(keyword or "").split()).casefold()
        if cleaned and cleaned in folded:
            return True
    for phrase in _URGENT_WORDS:
        if phrase in folded:
            return True
    if tokens & {"urgent", "asap", "now", "today", "aaj", "abhi", "jaldi", "turant"}:
        return True
    if re.search(r"\d{1,2}[:.]\d{2}\s*(?:am|pm|baje|बजे)?", folded) and looks_like_question(text):
        return True
    letters = [char for char in text if char.isalpha()]
    if len(letters) >= 8 and all(char.isupper() for char in letters):
        return True
    if text.count("!") >= 2:
        return True
    return looks_like_question(text)


def _message_age(moment: float, now: float) -> str:
    seconds = max(0, int(now - moment)) if moment else 0
    if seconds < 90:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} h ago"
    return f"{hours // 24} d ago"


def fallback_suggestion(text: str) -> str:
    """A tiny local fallback so the flow still helps when the cloud brain is offline."""
    folded = str(text or "").casefold()
    if any(hint in folded for hint in _ABSENCE_HINTS):
        return "I won’t be able to come today, sorry. I’ll keep you posted."
    if any(word in folded for word in ("late", "delay", "ruk", "ruka", "der")):
        return "I’ll be a little late — please start without me."
    if any(word in folded for word in ("call", "phone", "baat")):
        return "Can’t talk right now — I’ll call you back as soon as I can."
    return ""


# ---------------------------------------------------------------------- service


class ReplyWatchService:
    """Track the user's named chats and raise only genuine waiting-for-reply items."""

    BUSY_GRACE_SECONDS = 25

    def __init__(
        self,
        activity_for: Callable[[Platform], ActivityAdapter],
        drafts: object,
        *,
        clock: Callable[[], float] = time.time,
        suggester: Callable[[str, str], str] | None = None,
    ) -> None:
        self._activity_for = activity_for
        self._drafts = drafts
        self._clock = clock
        self._suggester = suggester
        self._watches: dict[str, WatchItem] = {}
        self._items: dict[str, WatchItem] = {}
        self._seen: dict[str, set[str]] = {}
        self._reported: dict[str, set[str]] = {}
        self._busy_since: float | None = None
        self._lock = threading.RLock()

    # ---------------------------------------------------------------- watches

    def add_watch(
        self, raw: dict[str, object], *, progress: Callable[[str], None] | None = None
    ) -> WatchResult:
        platform = Platform.parse(str(raw.get("platform") or ""))
        chat_filter = " ".join(str(raw.get("chat") or "").split())[:MAX_CHAT_FILTER_CHARS]
        all_chats = bool(raw.get("all_chats")) and not chat_filter
        if not chat_filter and not all_chats:
            raise ReplyWatchError("Name the chat or person Weronika should watch.")
        mode = parse_watch_mode(str(raw.get("mode") or WatchMode.ASK.value))
        rule = parse_watch_rule(str(raw.get("rule") or WatchRule.UNANSWERED.value))
        keywords = [str(word)[:40] for word in (raw.get("keywords") or []) if str(word).strip()][:10]
        delay = _clamp_int(raw.get("delay_seconds"), 0, MAX_DELAY_SECONDS, 0)
        reminder = _clamp_int(raw.get("reminder_seconds"), 0, MAX_REMINDER_SECONDS, 0)
        unanswered_after = _clamp_int(raw.get("unanswered_after_seconds"), 0, MAX_UNANSWERED_SECONDS, 600)

        self._notify(
            progress,
            f"Reading the visible {platform_display(platform)} chat list for “{chat_filter or 'any chat'}”.",
        )
        try:
            snapshot = self._activity_for(platform).list_chats(platform)
        except Exception as exc:
            raise ReplyWatchError(
                str(exc) or f"Weronika could not read the {platform_display(platform)} chat list."
            ) from exc

        if all_chats:
            selected = snapshot[:ALL_CHATS_LIMIT]
            if not selected:
                raise ReplyWatchError(
                    f"No visible {platform_display(platform)} chats were found to watch."
                )
        else:
            chat = find_chat(snapshot, chat_filter)
            if chat is None:
                visible = ", ".join(item.chat_name for item in snapshot[:8]) or "no chats"
                raise ReplyWatchError(
                    f"Weronika could not match “{chat_filter}” to exactly one visible "
                    f"{platform_display(platform)} chat. Visible chats: {visible}."
                )
            selected = [chat]

        now = self._clock()
        created: list[WatchItem] = []
        skipped: list[str] = []
        for chat in selected:
            key = chat.key
            with self._lock:
                watching = any(watch.chat_key == key for watch in self._watches.values())
            if watching:
                skipped.append(chat.chat_name)
                continue
            watch = WatchItem(
                id=uuid.uuid4().hex[:12],
                platform=platform,
                chat_name=chat.chat_name,
                chat_filter=chat_filter or chat.chat_name,
                is_group=chat.is_group,
                mode=mode,
                rule=rule,
                keywords=list(keywords),
                delay_seconds=delay,
                reminder_seconds=reminder,
                unanswered_after_seconds=unanswered_after,
                reason=_watch_reason(mode, rule),
                created_at=now,
                updated_at=now,
            )
            # The conversation that already exists is history, not a new request for a reply.
            try:
                reading = self._activity_for(platform).read_latest(platform, chat.chat_name)
                self._remember(watch.chat_key, [message_key(item) for item in reading.messages])
            except Exception:
                pass
            with self._lock:
                self._watches[watch.id] = watch
            created.append(watch)

        with self._lock:
            if not self._watches:
                raise ReplyWatchError("Reply watch supports at most 10 chats at the same time.")
            while len(self._watches) > MAX_WATCHES:
                self._watches.pop(next(iter(self._watches)))

        action = "ask you what to reply" if mode is WatchMode.ASK else "propose a reply for your approval"
        names = ", ".join(f"“{watch.chat_name}”" for watch in created) or "already-watched chats"
        note = f" (already watching {', '.join(skipped)})" if skipped else ""
        return WatchResult(
            created[0] if created else next(iter(self._watches.values())),
            f"Watching {platform_display(platform)} {names}{note}. Weronika will {action} "
            "when someone messages you there and you have not replied. "
            "Nothing sends without your confirmation.",
        )

    def has_watch_for(self, platform: Platform, chat_name: str) -> bool:
        key = f"{platform.value}:{normalize_name(chat_name)}"
        with self._lock:
            return any(watch.chat_key == key for watch in self._watches.values())

    def remove_watch(self, watch_id: str = "") -> WatchResult:
        with self._lock:
            if not self._watches:
                raise ReplyWatchError("No chats are being watched yet.")
            target = None
            if watch_id:
                target = self._watches.get(str(watch_id))
            elif len(self._watches) == 1:
                target = next(iter(self._watches.values()))
            if target is None:
                names = ", ".join(f"{platform_display(w.platform)} · {w.chat_name}" for w in self._watches.values())
                raise ReplyWatchError(f"Name which watched chat to stop. Watched: {names}.")
            del self._watches[target.id]
            for item_id, item in list(self._items.items()):
                if item.watch_id == target.id and item.state == WatchState.AWAITING_USER:
                    del self._items[item_id]
        return WatchResult(target, f"Stopped watching “{target.chat_name}”. No further messages will be read there.")

    # ------------------------------------------------------------------ state

    def list_state(self) -> dict[str, object]:
        with self._lock:
            self._prune()
            return {
                "watches": [watch.to_dict() for watch in self._watches.values()],
                "items": [item.to_dict() for item in self._items.values()],
                "busy": bool(self._busy_since is not None),
            }

    def _prune(self) -> None:
        now = self._clock()
        for item_id, item in list(self._items.items()):
            if now - item.updated_at <= ITEM_TTL_SECONDS:
                continue
            if item.state in {
                WatchState.SENT,
                WatchState.SENT_UNVERIFIED,
                WatchState.DECLINED,
                WatchState.EXPIRED,
                WatchState.FAILED,
            }:
                del self._items[item_id]

    # ------------------------------------------------------------------- scan

    def scan(self, *, progress: Callable[[str], None] | None = None) -> dict[str, object]:
        with self._lock:
            self._prune()
            watches = [
                watch for watch in self._watches.values() if watch.state is not WatchState.EXPIRED
            ]
        if not watches:
            return {"watched": 0, "detected": [], "notes": []}

        now = self._clock()
        if self._drafts_are_busy():
            with self._lock:
                if self._busy_since is None:
                    self._busy_since = now
                if now - self._busy_since < self.BUSY_GRACE_SECONDS:
                    return {
                        "watched": len(watches),
                        "detected": [],
                        "notes": ["Paused: a message draft is open in the orb."],
                    }
        else:
            with self._lock:
                self._busy_since = None

        detected: list[dict[str, object]] = []
        notes: list[str] = []
        for watch in watches:
            try:
                reading = self._activity_for(watch.platform).read_latest(watch.platform, watch.chat_name)
            except Exception as exc:
                watch.last_error = str(exc)[:300]
                notes.append(
                    f"{platform_display(watch.platform)} · {watch.chat_name}: {watch.last_error}"
                )
                continue
            watch.last_error = ""
            if reading.messages:
                watch.is_group = reading.is_group
            detection = self._evaluate(watch, reading, now)
            if detection is None:
                continue
            created = self._raise_item(watch, detection, now)
            if created is not None:
                detected.append(created.to_dict())
                self._notify(
                    progress,
                    f"Reply needed in {platform_display(watch.platform)} · {watch.chat_name}.",
                )

        reminders = self._due_reminders(now)
        with self._lock:
            stale = [item for item in self._items.values() if item.state is WatchState.AWAITING_USER]
        for item in stale:
            if now - item.user_notified_at > TIMEOUT_SECONDS and item.state is WatchState.AWAITING_USER:
                item.state = WatchState.EXPIRED
                item.updated_at = now
                item.reason = "No reply from you within 15 minutes, so Weronika stopped waiting."
        return {"watched": len(watches), "detected": detected, "reminders": reminders, "notes": notes}

    def _evaluate(self, watch: WatchItem, reading: ChatReading, now: float) -> Detection | None:
        key = watch.chat_key
        tokens = [message_key(item) for item in reading.messages]
        if reading.last_is_incoming is False:
            # The user already answered; nothing in this transcript is pending.
            self._mark_reported(key, tokens)
            return None
        handled = self._known(key) | self._reported_tokens(key)
        fresh: list[IncomingMessage] = []
        for message in reading.messages:
            token = message_key(message)
            if token in handled:
                continue
            if not str(message.text or "").strip():
                continue
            if reading.is_group and message.sender and _is_self_label(message.sender):
                continue
            fresh.append(message)
        if not fresh:
            return None
        newest = fresh[-1]
        matched = [item for item in fresh if self._matches_rule(watch, item, reading.is_group)]
        if not matched:
            return None
        target = matched[-1]
        if watch.rule is WatchRule.UNANSWERED:
            waiting = max(0, now - (target.seen_at or now))
            if waiting < watch.unanswered_after_seconds:
                return None
            reason = (
                f"“{target.sender or target.chat_name}” messaged {_message_age(target.seen_at, now)} on "
                f"{platform_display(watch.platform)} and nothing was answered yet"
            )
        else:
            reason = (
                f"New message on {platform_display(watch.platform)} looks urgent "
                f"({_message_age(target.seen_at, now)})"
            )
        if watch.delay_seconds and now - (newest.seen_at or now) < watch.delay_seconds:
            return None
        return Detection(reason=reason, message=target)

    @staticmethod
    def _matches_rule(watch: WatchItem, message: IncomingMessage, is_group: bool) -> bool:
        if watch.keywords:
            folded = message.text.casefold()
            if any(keyword.casefold() in folded for keyword in watch.keywords):
                return True
        if watch.rule is WatchRule.URGENT:
            return is_urgent(message, watch.keywords)
        if is_group:
            # Group chats are noisy: only a question that names the user counts as waiting.
            return looks_like_question(message.text) and "@" in message.text
        return True

    def _raise_item(self, watch: WatchItem, detection: Detection, now: float) -> WatchItem | None:
        with self._lock:
            for item in self._items.values():
                if item.watch_id == watch.id and item.state in {
                    WatchState.AWAITING_USER,
                    WatchState.AWAITING_REVIEW,
                    WatchState.HELD,
                }:
                    return None  # one open item per watched chat
            suggestion = ""
            if watch.mode is WatchMode.PROPOSE:
                suggestion = self._suggest(detection.message)
            item = WatchItem(
                id=uuid.uuid4().hex[:12],
                watch_id=watch.id,
                platform=watch.platform,
                chat_name=watch.chat_name,
                chat_filter=watch.chat_filter,
                is_group=watch.is_group,
                mode=watch.mode,
                rule=watch.rule,
                keywords=list(watch.keywords),
                reason=detection.reason,
                message=detection.message,
                seen_at=detection.message.seen_at or now,
                suggestion=suggestion,
                state=WatchState.AWAITING_USER,
                created_at=now,
                updated_at=now,
                user_notified_at=now,
                reminder_at=now + watch.reminder_seconds if watch.reminder_seconds else 0.0,
            )
            watch.state = WatchState.AWAITING_USER
            watch.updated_at = now
            self._items[item.id] = item
            self._mark_reported(watch.chat_key, [message_key(detection.message)])
            while len(self._items) > MAX_ITEMS:
                oldest = min(self._items.values(), key=lambda entry: entry.created_at)
                del self._items[oldest.id]
            return item

    def _due_reminders(self, now: float) -> list[dict[str, object]]:
        due: list[dict[str, object]] = []
        with self._lock:
            for item in self._items.values():
                if item.state is not WatchState.AWAITING_USER or item.reminder_sent or not item.reminder_at:
                    continue
                if now < item.reminder_at:
                    continue
                item.reminder_sent = True
                item.updated_at = now
                due.append({"item_id": item.id, "text": self._reminder_text(item)})
        return due

    @staticmethod
    def _reminder_text(item: WatchItem) -> str:
        who = item.message.sender if item.message and item.message.sender else item.chat_name
        return f"Still no reply to {who} on {platform_display(item.platform)} · {item.chat_name}."

    def _suggest(self, message: IncomingMessage) -> str:
        if self._suggester is not None:
            try:
                value = self._suggester(message.chat_name, message.text)
                if isinstance(value, str):
                    cleaned = " ".join(value.split())[:MAX_REPLY_CHARS]
                    if cleaned:
                        return cleaned
            except Exception:
                pass
        return fallback_suggestion(message.text)

    # ---------------------------------------------------------------- answers

    def hold(self, item_id: str) -> WatchResult:
        item = self._item(item_id)
        with self._lock:
            if item.state is not WatchState.AWAITING_USER:
                raise ReplyWatchError("This chat is not waiting for your answer.")
            item.state = WatchState.HELD
            item.updated_at = self._clock()
        return WatchResult(item, f"Holding “{item.chat_name}”. Weronika will say it is still unanswered.")

    def decline(self, item_id: str, reason: str = "") -> WatchResult:
        item = self._item(item_id)
        with self._lock:
            if item.state in {WatchState.SENT, WatchState.SENT_UNVERIFIED}:
                raise ReplyWatchError("This reply was already handled.")
            item.state = WatchState.DECLINED
            item.updated_at = self._clock()
            reason = " ".join(str(reason or "").split())[:200]
            item.reason = f"You chose not to reply. {reason}".strip()
            item.suggestion = ""
            if item.watch_id in self._watches:
                self._watches[item.watch_id].state = WatchState.NEW
        return WatchResult(item, f"Okay — nothing will be sent to “{item.chat_name}”. Weronika keeps watching for the next message.")

    def propose(self, item_id: str, message: str, *, progress: Callable[[str], None] | None = None) -> WatchResult:
        item = self._item(item_id)
        text = " ".join(str(message or "").split())
        if not text:
            raise ReplyWatchError("What should Weronika prepare to send?")
        if len(text) > MAX_REPLY_CHARS:
            raise ReplyWatchError("That reply is over the 2,000-character limit. Please shorten it.")
        with self._lock:
            if item.state not in {WatchState.AWAITING_USER, WatchState.HELD, WatchState.AWAITING_REVIEW}:
                raise ReplyWatchError("This chat already has a reply in progress. Check the chat first.")
            if item.draft is not None and item.draft.stage.value == "awaiting_confirmation":
                raise ReplyWatchError(
                    "A draft is already waiting in that chat. Reply ‘confirm send’ to send it or ‘cancel’ to clear it."
                )
            item.suggestion = text
            item.state = WatchState.AWAITING_REVIEW
            item.updated_at = self._clock()
            item.draft = None

        self._notify(progress, f"Preparing your exact reply for {platform_display(item.platform)} · {item.chat_name}.")
        try:
            workflow = self._drafts.prepare(
                item.platform,
                item.chat_name,
                text,
                progress=progress,
            )
        except Exception as exc:
            with self._lock:
                item.state = WatchState.AWAITING_USER
                item.last_error = str(exc)[:300]
            raise ReplyWatchError(str(exc) or "Weronika could not prepare that reply.") from exc

        with self._lock:
            item.draft = workflow.draft
            item.updated_at = self._clock()
            if workflow.draft.stage.value == "awaiting_confirmation":
                item.state = WatchState.AWAITING_REVIEW
            elif workflow.draft.stage.value == "awaiting_recipient_choice":
                item.state = WatchState.AWAITING_USER
            else:
                item.state = WatchState.FAILED
        return WatchResult(item, workflow.prompt)

    def choose(
        self,
        item_id: str,
        candidate_id: str,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> WatchResult:
        """Resolve an ambiguous chat name before the reply text is staged."""
        item = self._item(item_id)
        with self._lock:
            draft = item.draft
            if draft is None or draft.stage.value != "awaiting_recipient_choice":
                raise ReplyWatchError("This chat is not waiting for a contact choice.")
        try:
            workflow = self._drafts.select_recipient(draft.id, str(candidate_id), progress=progress)
        except Exception as exc:
            raise ReplyWatchError(str(exc) or "Weronika could not open that chat.") from exc
        with self._lock:
            item.draft = workflow.draft
            item.state = (
                WatchState.AWAITING_REVIEW
                if workflow.draft.stage.value == "awaiting_confirmation"
                else WatchState.FAILED
            )
            item.updated_at = self._clock()
        return WatchResult(item, workflow.prompt)

    def confirm(
        self,
        item_id: str,
        phrase: str,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> WatchResult:
        item = self._item(item_id)
        with self._lock:
            draft = item.draft
            if draft is None or draft.stage.value != "awaiting_confirmation":
                raise ReplyWatchError(
                    "There is no prepared reply waiting. Give Weronika the exact text first."
                )
            sent = self._drafts.confirm_send(draft.id, phrase, progress=progress)
            stage = sent.draft.stage.value
            item.state = WatchState.SENT if stage == "sent" else WatchState.SENT_UNVERIFIED
            item.updated_at = self._clock()
            item.reason = sent.draft.result
            if item.watch_id in self._watches:
                self._watches[item.watch_id].state = WatchState.NEW
            draft_result = sent.draft.result
        return WatchResult(item, draft_result)

    def review_hint(self, item_id: str) -> str:
        item = self._item(item_id)
        if item.state is WatchState.AWAITING_REVIEW and item.draft is not None:
            if item.draft.stage.value == "awaiting_confirmation":
                return self._confirmation_prompt(item)
        return self._prompt(item)

    # ---------------------------------------------------------------- helpers

    def _item(self, item_id: str) -> WatchItem:
        with self._lock:
            self._prune()
            item = self._items.get(str(item_id or ""))
        if item is None:
            raise ReplyWatchError("That reply-watch item expired or does not exist.")
        return item

    def _drafts_are_busy(self) -> bool:
        checker = getattr(self._drafts, "has_unsettled_draft", None)
        return bool(checker()) if callable(checker) else False

    def _known(self, key: str) -> set[str]:
        with self._lock:
            return set(self._seen.get(key, set()))

    def _reported_tokens(self, key: str) -> set[str]:
        with self._lock:
            return set(self._reported.get(key, set()))

    def _mark_reported(self, key: str, tokens: list[str]) -> None:
        with self._lock:
            bucket = self._reported.setdefault(key, set())
            bucket.update(token for token in tokens if token)
            while len(bucket) > MAX_TRACKED_TEXT_KEYS:
                bucket.pop()

    def _remember(self, key: str, tokens: list[str]) -> None:
        with self._lock:
            bucket = self._seen.setdefault(key, set())
            bucket.update(token for token in tokens if token)
            while len(bucket) > MAX_TRACKED_TEXT_KEYS:
                bucket.pop()

    @staticmethod
    def _notify(progress: Callable[[str], None] | None, message: str) -> None:
        if progress is None:
            return
        try:
            progress(message)
        except Exception:
            pass

    @classmethod
    def _prompt(cls, item: WatchItem) -> str:
        who = item.message.sender if item.message and item.message.sender else item.chat_name
        header = (
            f"Reply needed · {platform_display(item.platform)} · {item.chat_name}"
            + (" · group" if item.is_group else "")
        )
        body = ""
        if item.message is not None:
            body = f"\n{who}: “{item.message.text}”\n"
        if item.state is WatchState.AWAITING_USER:
            if item.suggestion:
                return (
                    f"{header}\n{item.reason}.{body}\n"
                    f"Suggested reply: “{item.suggestion}”\n"
                    "Say ‘send it’ to prepare that exact text, type your own reply, or say ‘leave it’ / ‘I replied’."
                )
            return (
                f"{header}\n{item.reason}.{body}\n"
                "What should I tell them? Say ‘reply: <your words>’, or say ‘leave it’ and I will not reply."
            )
        if (
            item.state is WatchState.AWAITING_USER
            and item.draft is not None
            and item.draft.stage.value == "awaiting_recipient_choice"
        ):
            options = "\n".join(
                f"{candidate.id}. {candidate.display_name}" for candidate in item.draft.candidates
            )
            return (
                f"{header}\nSeveral chats match “{item.chat_name}”. Choose one by number:\n{options}\n"
                "Nothing has been typed or sent."
            )
        if item.state is WatchState.HELD:
            return f"{header}\n{item.reason}. Still unanswered; say the reply text when you are ready."
        if item.state is WatchState.SENT:
            return f"{header}\nSent and verified."
        if item.state is WatchState.SENT_UNVERIFIED:
            return f"{header}\nThe send could not be verified. Check that chat before trying again."
        if item.state is WatchState.DECLINED:
            return f"{header}\nDeclined. Nothing was sent."
        return f"{header}\n{item.reason}"

    @staticmethod
    def _confirmation_prompt(item: WatchItem) -> str:
        draft = item.draft
        name = draft.selected_recipient if draft and draft.selected_recipient else item.chat_name
        text = draft.message if draft else item.suggestion
        return (
            f"I opened {platform_display(item.platform)} chat “{name}” and prepared this reply:\n\n"
            f"{text}\n\nIt has NOT been sent. Reply ‘confirm send’ or ‘send it’ to send, or ‘cancel’ to clear it."
        )


def _watch_reason(mode: WatchMode, rule: WatchRule) -> str:
    rule_text = "any message you have not answered" if rule is WatchRule.UNANSWERED else "urgent messages"
    return f"Watching for {rule_text}; Weronika will {'ask you' if mode is WatchMode.ASK else 'propose a reply'}."


def _clamp_int(value: object, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _is_self_label(value: str) -> bool:
    folded = " ".join(str(value or "").split()).casefold()
    return folded in {"you", "me", "aap", "main", "self"} or folded.endswith("(you)")
