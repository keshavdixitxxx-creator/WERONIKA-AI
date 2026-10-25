"""A deliberately narrow parser for explicit, single-recipient message commands."""

from __future__ import annotations

import re

from .models import IntentParseResult, Platform

PLATFORM_PATTERNS: tuple[tuple[Platform, re.Pattern[str]], ...] = (
    (Platform.WHATSAPP, re.compile(r"\b(?:whats\s?app|wa)\b", re.I)),
    (Platform.TELEGRAM, re.compile(r"\b(?:telegram|tg)\b", re.I)),
    (Platform.INSTAGRAM, re.compile(r"\b(?:instagram|insta|ig)\b", re.I)),
    (Platform.FACEBOOK, re.compile(r"\b(?:facebook|messenger)\b", re.I)),
    (Platform.X, re.compile(r"\b(?:twitter|x\.com|on\s+x)\b", re.I)),
)

MESSAGE_VERB = re.compile(r"\b(?:send|message|text|dm)\b", re.I)
BODY_MARKER = re.compile(r"\b(?:saying|that)\b\s+|:\s+", re.I)


def _trim_quotes(value: str) -> str:
    value = value.strip()
    pairs = {'"': '"', "'": "'", "“": "”", "‘": "’"}
    if len(value) >= 2 and pairs.get(value[0]) == value[-1]:
        value = value[1:-1].strip()
    return value


def _find_body(text: str) -> tuple[str, str]:
    match = BODY_MARKER.search(text)
    if not match:
        return text.strip(), ""
    header = text[: match.start()].strip(" ,;\t")
    body = text[match.end() :].strip()
    return header, _trim_quotes(body)


def _find_recipient(header: str, platform_pattern: re.Pattern[str] | None) -> str:
    platform_suffix = r"\s+(?:on|via|through)\s+(?:whats\s?app|wa|telegram|tg|instagram|insta|ig|facebook|messenger|twitter|x\.com|x)\b.*$"
    suffix = re.compile(platform_suffix, re.I)

    # Preferred form: "... to Boss on WhatsApp" or "... to Boss".
    to_match = re.search(r"\b(?:to|for)\s+(.+)$", header, re.I)
    if to_match:
        recipient = suffix.sub("", to_match.group(1)).strip(" .,;:")
        recipient = re.sub(r"^(?:contact|chat)\s+", "", recipient, flags=re.I)
        return recipient

    # Also accept "message Boss on Telegram" / "DM @user on Instagram".
    if platform_pattern:
        platform_match = platform_pattern.search(header)
        if platform_match:
            before = header[: platform_match.start()].strip(" .,;:")
            candidate = re.sub(r"^(?:please\s+)?(?:send|message|text|dm)\s+", "", before, flags=re.I)
            candidate = re.sub(r"^(?:a\s+)?message\s+", "", candidate, flags=re.I).strip()
            candidate = re.sub(r"\s+(?:on|via|through)$", "", candidate, flags=re.I).strip()
            if candidate and candidate.casefold() not in {"a", "the"}:
                return candidate.strip(" .,;:")
    return ""


def parse_message_request(text: str) -> IntentParseResult:
    """Parse only explicit send/message requests; everything else stays brain chat."""
    raw = " ".join(str(text or "").split())
    if not raw or not MESSAGE_VERB.search(raw):
        return IntentParseResult(handled=False)

    platform_match: tuple[Platform, re.Pattern[str]] | None = next(
        ((platform, pattern) for platform, pattern in PLATFORM_PATTERNS if pattern.search(raw)),
        None,
    )
    # Do not hijack ordinary chat like "send me a joke". A platform is required
    # before Weronika offers to create a local messaging draft.
    if platform_match is None:
        return IntentParseResult(handled=False)

    platform, pattern = platform_match
    header, body = _find_body(raw)
    if not body:
        return IntentParseResult(
            handled=True,
            platform=platform,
            prompt="What exact message should I prepare? Say, for example, ‘Send a WhatsApp message to Boss saying I’ll be on leave.’",
        )

    recipient = _find_recipient(header, pattern)
    if not recipient:
        return IntentParseResult(
            handled=True,
            platform=platform,
            message=body,
            prompt=f"Who should I message on {platform.value.title()}? Please give the chat or account name.",
        )
    if len(recipient) > 120:
        return IntentParseResult(
            handled=True,
            platform=platform,
            prompt="That recipient name is too long. Please give me the contact or chat name only.",
        )
    if len(body) > 2000:
        return IntentParseResult(
            handled=True,
            platform=platform,
            recipient=recipient,
            prompt="That message is over the 2,000-character limit for this first version. Please shorten it.",
        )

    return IntentParseResult(
        handled=True,
        platform=platform,
        recipient=recipient,
        message=body,
    )
