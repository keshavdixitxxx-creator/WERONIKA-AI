"""Read-only visible-browser inspection for Weronika's reply watch.

Only the rendered chat UI is used: no private APIs, no message export, no history
download, no password handling. A chat list or transcript that cannot be read with
confidence is reported as an error instead of guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from .models import Platform, platform_display
from .reply_watch import ChatReading, ChatSnapshot, IncomingMessage, ReplyWatchError
from .workflow import LoginRequired, MessagingError

MAX_MESSAGES_PER_CHAT = 12
_MAX_BUBBLE_CHARS = 1500
_GROUP_LABEL_RE = re.compile(
    r"^(?:\d+\s*(?:messages?|unread)?\s*)$|^(?:typing…?|online|last seen.*|click here for.*)$",
    re.IGNORECASE,
)
# Lines inside a WhatsApp bubble/preview that are metadata, not the message.
_WHATSAPP_META_RE = re.compile(
    r"^(?:forwarded|you|me|edited|deleted message|this message was deleted)$", re.IGNORECASE
)


@dataclass(frozen=True)
class ActivitySpec:
    messages_ready: str
    rooms: str
    bubbles: str
    message_list: str
    outgoing_classes: tuple[str, ...] = ()
    # Chat names that clearly identify a group chat.
    group_markers: tuple[str, ...] = ()
    # Sites that do not render a dependable message list for automation.
    read_supported: bool = True


ACTIVITY_SPECS: dict[Platform, ActivitySpec] = {
    Platform.WHATSAPP: ActivitySpec(
        messages_ready="#pane-side, [aria-label='Chat list']",
        rooms="#pane-side [role='listitem'], #pane-side [role='row']",
        bubbles="#main .message-in, #main .message-out",
        message_list="#main div[role='application'], #main [data-testid='conversation-panel-messages']",
        outgoing_classes=("message-out",),
    ),
    Platform.TELEGRAM: ActivitySpec(
        messages_ready="#column-left, #column-center, .chatlist",
        rooms="#column-left .ListItem, .chatlist .ListItem, #column-left [role='listitem']",
        bubbles="#column-center .bubble, .bubbles .bubble",
        message_list="#column-center .bubbles, #column-center .scrollable-y-bordered",
        outgoing_classes=("is-out", "own"),
        group_markers=("#", "group", "channel"),
    ),
    Platform.INSTAGRAM: ActivitySpec(
        messages_ready="[role='main'], main",
        rooms="[role='main'] [role='listitem'], [role='main'] a[href*='/direct/t/']",
        bubbles="[role='main'] div[dir='auto']",
        message_list="[role='main']",
        read_supported=False,
    ),
}


class PlaywrightActivityAdapter:
    """Read chats in the user's already-open, signed-in browser profile."""

    def __init__(self, browser, *, max_rows: int = 40) -> None:
        self.browser = browser
        self.max_rows = max_rows

    # ------------------------------------------------------------------ pages

    def _page(self, platform: Platform):
        spec = ACTIVITY_SPECS.get(platform)
        if spec is None or not spec.read_supported:
            raise ReplyWatchError(
                "Reply watch reads incoming chats on WhatsApp Web and Telegram Web today. "
                f"{platform_display(platform)} does not expose a dependable message list to automation, "
                "so Weronika will not guess there."
            )
        page = self.browser.page_for(platform)
        try:
            if page.url in {"", "about:blank"}:
                page.goto(_home_url(platform), wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_selector(spec.messages_ready, timeout=20_000)
        except MessagingError:
            raise
        except Exception as exc:
            if _login_visible(page):
                raise LoginRequired(
                    f"Please sign in to {platform_display(platform)} in its open browser window, then retry. "
                    "Weronika never asks you to share your password."
                ) from exc
            raise ReplyWatchError(
                f"Weronika could not read the {platform_display(platform)} chat list. "
                "Finish signing in and keep that browser window open."
            ) from exc
        return page

    # ------------------------------------------------------------------ reads

    def list_chats(self, platform: Platform) -> list[ChatSnapshot]:
        page = self._page(platform)
        spec = ACTIVITY_SPECS[platform]
        chats: list[ChatSnapshot] = []
        seen: set[str] = set()
        locator = page.locator(spec.rooms)
        try:
            count = min(locator.count(), self.max_rows)
        except Exception as exc:
            raise ReplyWatchError(f"The {platform_display(platform)} chat list could not be read.") from exc
        for index in range(count):
            row = locator.nth(index)
            try:
                if not row.is_visible():
                    continue
                text = row.inner_text(timeout=1_000)
            except Exception:
                continue
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            name = _chat_name(platform, lines, ("unread", "pinned", "muted", "you:"))
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            rest = [
                line
                for line in lines
                if line != name
                and not _GROUP_LABEL_RE.match(line)
                and not _WHATSAPP_META_RE.match(line)
            ]
            chats.append(
                ChatSnapshot(
                    platform=platform,
                    chat_name=name[:120],
                    is_group=_looks_like_group(name, spec),
                    preview=(rest[0] if rest else "")[:200],
                )
            )
        if not chats:
            if _login_visible(page):
                raise LoginRequired(f"Please sign in to {platform_display(platform)} and retry.")
            return []
        return chats

    def read_latest(self, platform: Platform, chat_name: str) -> ChatReading:
        page = self._page(platform)
        spec = ACTIVITY_SPECS[platform]
        row = self._row(page, spec, chat_name)
        if row is None:
            raise ReplyWatchError(
                f"“{chat_name}” is not visible in the {platform_display(platform)} chat list."
            )
        try:
            row.click(timeout=5_000)
            page.wait_for_selector(spec.message_list, timeout=10_000)
            page.wait_for_timeout(400)
        except Exception as exc:
            raise ReplyWatchError(
                f"Weronika could not open the {platform_display(platform)} chat “{chat_name}”."
            ) from exc

        reading = self._read_bubbles(page, spec, platform, chat_name)
        if reading is None:
            raise ReplyWatchError(
                f"The {platform_display(platform)} transcript does not show a dependable message list, "
                "so Weronika will not guess who wrote last."
            )
        messages, last_is_incoming = reading
        return ChatReading(
            chat_name=chat_name,
            is_group=_looks_like_group(chat_name, spec),
            messages=tuple(messages[-MAX_MESSAGES_PER_CHAT:]),
            last_is_incoming=last_is_incoming,
        )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _row(page, spec: ActivitySpec, chat_name: str):
        wanted = _name_key(chat_name)
        locator = page.locator(spec.rooms)
        try:
            count = min(locator.count(), 80)
        except Exception:
            return None
        for index in range(count):
            row = locator.nth(index)
            try:
                if not row.is_visible():
                    continue
                text = row.inner_text(timeout=800)
            except Exception:
                continue
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            name = _chat_name(_platform_from_spec(spec), lines, ("unread", "pinned", "muted", "you:"))
            if name and _name_key(name) == wanted:
                return row
        return None

    @staticmethod
    def _read_bubbles(page, spec: ActivitySpec, platform: Platform, chat_name: str):
        locator = page.locator(spec.bubbles)
        try:
            count = min(locator.count(), 400)
        except Exception:
            return None
        if count < 1:
            return None
        found: list[dict[str, object]] = []
        for index in range(count):
            bubble = locator.nth(index)
            try:
                if not bubble.is_visible():
                    continue
                text = bubble.inner_text(timeout=800)
            except Exception:
                continue
            cleaned = _bubble_text(text)
            if not cleaned:
                continue
            classes = _class_tokens(bubble)
            outgoing = any(marker in classes for marker in spec.outgoing_classes)
            sender = "" if outgoing else _bubble_sender(bubble)
            found.append({"text": cleaned, "outgoing": outgoing, "sender": sender[:80]})
        if not found:
            return None
        messages = [
            IncomingMessage(
                platform=platform,
                chat_name=chat_name,
                message_id=_stable_id(str(item["text"]), str(item["sender"])),
                text=str(item["text"]),
                sender=str(item["sender"]),
            )
            for item in found
            if not item["outgoing"]
        ]
        return messages, not bool(found[-1]["outgoing"])


# ------------------------------------------------------------------ module helpers


def _home_url(platform: Platform) -> str:
    return {
        Platform.WHATSAPP: "https://web.whatsapp.com/",
        Platform.TELEGRAM: "https://web.telegram.org/k/",
        Platform.INSTAGRAM: "https://www.instagram.com/direct/inbox/",
        Platform.FACEBOOK: "https://www.messenger.com/",
        Platform.X: "https://x.com/messages",
    }[platform]


def _platform_from_spec(spec: ActivitySpec) -> Platform:
    for platform, candidate in ACTIVITY_SPECS.items():
        if candidate is spec:
            return platform
    return Platform.WHATSAPP


def _chat_name(platform: Platform, lines: list[str], skip: Sequence[str]) -> str:
    """Pick the title line from a chat row and drop badge/status text."""
    for line in lines:
        normalized = " ".join(line.split()).casefold()
        if not normalized or _GROUP_LABEL_RE.match(normalized):
            continue
        if normalized in {"you:", "you"}:
            continue
        if any(normalized == marker for marker in skip):
            continue
        if re.fullmatch(r"[\d,\s]+", normalized):
            continue  # unread count or timestamp
        if re.fullmatch(r"\d{1,2}:\d{2}(?:\s*[ap]m)?", normalized):
            continue
        return line
    return ""


def _bubble_text(text: str) -> str:
    lines = []
    for line in str(text or "").splitlines():
        cleaned = line.strip()
        if not cleaned or _WHATSAPP_META_RE.match(cleaned):
            continue
        lines.append(cleaned)
    joined = " ".join(" ".join(lines).split())
    if not joined or len(joined) > _MAX_BUBBLE_CHARS:
        return ""
    return joined


def _header_selectors(platform: Platform) -> Sequence[str]:
    if platform is Platform.TELEGRAM:
        return ("#column-center header", "#column-center .chat-info", "#column-center .topbar")
    return ("#main header", "[data-testid='conversation-info-header']", "header")


def _bubble_sender(bubble) -> str:
    try:
        author = bubble.locator(
            "[data-pre-plain-text], .copyable-text[data-pre-plain-text], .name, .peer-title"
        ).first
        pre = author.get_attribute("data-pre-plain-text", timeout=500)
        if pre:
            return _sender_from_pre_plain(pre)
        return " ".join(author.inner_text(timeout=500).split())
    except Exception:
        return ""


def _class_tokens(locator) -> str:
    try:
        return " ".join(str(locator.evaluate("element => element.className || ''")).split()).lower()
    except Exception:
        return ""


def _first_visible(page, selectors: Iterable[str]):
    for selector in selectors:
        locator = page.locator(selector)
        try:
            count = min(locator.count(), 20)
        except Exception:
            continue
        for index in range(count):
            candidate = locator.nth(index)
            try:
                if candidate.is_visible():
                    return candidate
            except Exception:
                continue
    return None


def _login_visible(page) -> bool:
    try:
        password = page.locator("input[type='password']")
        if password.count() and password.first.is_visible():
            return True
    except Exception:
        pass
    for text in (
        "Scan the QR code",
        "Use WhatsApp on your computer",
        "Log in to Telegram",
        "Your Phone Number",
        "Log in",
    ):
        try:
            if page.get_by_text(text, exact=False).first.is_visible():
                return True
        except Exception:
            continue
    return False


def _name_key(value: str) -> str:
    return " ".join(re.sub(r"[^\w@]+", " ", str(value).casefold(), flags=re.UNICODE).split())


def _looks_like_group(name: str, spec: ActivitySpec) -> bool:
    if re.search(r"\b(group|team|family|friends|batch|class|office|members)\b", name, re.I):
        return True
    stripped = name.strip()
    return any(stripped.startswith(marker) for marker in spec.group_markers)


def _sender_from_pre_plain(value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    match = re.search(r"\]\s*([^:]{1,80})\s*:", text)
    if match:
        return match.group(1).strip()
    return ""


def _stable_id(text: str, sender: str) -> str:
    """A short, non-reversible fingerprint so the same bubble is not reported twice."""
    seed = f"{sender}\u241f{text}".encode("utf-8", errors="ignore")
    total = 0xA5A5
    for byte in seed:
        total = ((total << 5) - total + byte) & 0xFFFFFFFF
    return f"h{total:08x}"
