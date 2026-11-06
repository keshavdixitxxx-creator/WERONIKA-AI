"""Deliberately narrow parsing for reply-watch requests.

Only an explicit "watch / keep an eye on / if I don't reply" request turns the watch
on, and only an explicit "leave it" or "I replied" turns it off. Everything else
stays ordinary chat with the cloud brain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import Platform

PLATFORM_PATTERNS: tuple[tuple[Platform, re.Pattern[str]], ...] = (
    (Platform.WHATSAPP, re.compile(r"\b(?:whats\s?app|wa)\b", re.I)),
    (Platform.TELEGRAM, re.compile(r"\b(?:telegram|tg)\b", re.I)),
    (Platform.INSTAGRAM, re.compile(r"\b(?:instagram|insta|ig)\b", re.I)),
    (Platform.FACEBOOK, re.compile(r"\b(?:facebook|messenger)\b", re.I)),
    (Platform.X, re.compile(r"\b(?:twitter|x\.com|on\s+x)\b", re.I)),
)

WATCH_VERB_RE = re.compile(
    r"\b(?:watch|watching|keep an eye on|keep a watch on|monitor|track|check on|look after)\b"
    r"|\b(?:if|when)\s+i\s+(?:don't|do not|dont|can't|cannot|am not|ain't|am unable to)\s+"
    r"(?:reply|respond|answer|be able to reply|be able to respond)\b"
    r"|\b(?:whenever|if)\s+(?:someone|anyone|he|she|they|koi|kisi)\s+(?:message|messages|text|texts|dm|dms|ping|pings)\b"
    r"|\bif\s+someone\s+messages?\b",
    re.I,
)

STOP_WATCH_RE = re.compile(
    r"\b(?:stop watching|stop the watch|stop reply watch|close the watch|watch off|stop monitoring)\b",
    re.I,
)

ADD_RESET_RE = re.compile(
    r"^\s*(?:please\s+)?(?:weronika[,\s]+)?(?:watch|keep an eye on|keep a watch on|monitor|track|check on|look after)\b",
    re.I,
)

# Words that mean the assistant proposed a reply but must change the wording.
EDIT_RE = re.compile(
    r"^(?:no,?\s*)?(?:make it|say|change it to|instead say|reply:|reply with|tell them|tell him|tell her|"
    r"message them|write|send this|prepare)\s*[:\-]?\s*(.+)$",
    re.I,
)

LEAVE_IT_RE = re.compile(
    r"^(?:leave it|leave that|never mind|nevermind|skip it|skip|no reply|don'?t reply|do not reply|"
    r"i replied|i have replied|i already replied|i answered|i have answered|i'll reply myself|"
    r"i will reply myself|let it be|chhod do|mat bhejo|main reply kar dunga|main kar dunga|"
    r"छोड़ दो|मत भेजो)\b",
    re.I,
)

HOLD_RE = re.compile(
    r"^(?:hold on|wait|one moment|tell them (?:i'?m busy|wait)|say i'?m busy|i'?ll reply later|"
    r"busy right now|ruko|abhi busy hoon)\b",
    re.I,
)

STATUS_RE = re.compile(
    r"\b(?:who(?:'s| is| has)?\s+(?:waiting|pending)|any (?:waiting|pending|new) (?:messages|replies)|"
    r"reply watch status|watch status|what(?:'s| is) waiting|pending replies|any replies)\b",
    re.I,
)

SCAN_RE = re.compile(r"\bcheck (?:my )?(?:messages|chats|replies)(?: now)?\b|\bscan (?:my )?(?:chats|messages)\b", re.I)

PROPOSE_MODE_RE = re.compile(
    r"\b(?:you (?:can |could |should |to )?(?:reply|answer|send|message|respond)|you reply|"
    r"draft (?:a |the )?reply|reply (?:on my behalf|for me|yourself|if|when|in case)|"
    r"respond for me|propose|suggest(?: a)? reply|suggest)\b",
    re.I,
)

URGENT_RULE_RE = re.compile(
    r"\b(?:urgent|important|asap|only if (?:it'?s|it is) (?:urgent|important)|emergency|priority)\b", re.I
)

GROUP_ALLOW_RE = re.compile(r"\b(?:group|groups|gc)\b", re.I)

_ABSENCE_CONTEXT_RE = re.compile(
    r"\b(?:not coming|can'?t come|cannot come|won'?t come|not able to come|on leave|sick|busy|"
    r"running late|will be late|can'?t make it)\b",
    re.I,
)

MINUTES_RE = re.compile(r"\b(\d{1,3}|\d{1,2}\s*-\s*\d{1,2})\s*(?:min|mins|minute|minutes)\b", re.I)
HOURS_RE = re.compile(r"\b(\d{1,2})\s*(?:h|hr|hrs|hour|hours)\b", re.I)

_WATCH_WORD_RE = re.compile(r"\bwatch\b", re.I)


@dataclass(frozen=True)
class WatchIntent:
    action: Literal[
        "add_watch",
        "stop_watch",
        "status",
        "scan",
        "reply",
        "leave_it",
        "hold",
        "unhandled",
    ]
    platform: Platform | None = None
    chat: str = ""
    reply: str = ""
    all_chats: bool = False
    mode: Literal["ask", "propose"] = "ask"
    rule: Literal["unanswered", "urgent"] = "unanswered"
    delay_seconds: int = 0
    reminder_seconds: int = 0
    unanswered_after_seconds: int = 600
    prompt: str = ""
    wants_group: bool = False


def has_watch_intent(text: str) -> bool:
    """Cheap gate used before heavier parsing (and mirrored in the orb UI)."""
    value = str(text or "")
    if not value.strip():
        return False
    return bool(WATCH_VERB_RE.search(value) or STOP_WATCH_RE.search(value) or STATUS_RE.search(value))


def _first_platform(text: str) -> tuple[Platform | None, re.Pattern[str] | None]:
    for platform, pattern in PLATFORM_PATTERNS:
        if pattern.search(text):
            return platform, pattern
    return None, None


def _clamp_delay(match: re.Match[str] | None, unit: int, default: int = 0) -> int:
    if not match:
        return default
    raw = match.group(1).replace(" ", "")
    if "-" in raw:
        low, high = raw.split("-", 1)
        raw = high if high.isdigit() else low
    if not raw.isdigit():
        return default
    return min(86_400, int(raw) * unit)


def _strip_platform_words(value: str) -> str:
    return re.sub(
        r"\b(?:on|via|through|in)\s+(?:whats\s?app|wa|telegram|tg|instagram|insta|ig|facebook|messenger|"
        r"twitter|x\.com|x)\b.*$",
        "",
        value,
        flags=re.I,
    ).strip(" .,;:-")


_CLAUSE_TAIL_RE = re.compile(
    r"\s+(?:,|and|then|so|but)?\s*\b(?:if|when|whenever|so that|in case|and you|and tell|and ask|"
    r"and message|and reply|and send|please|because)\b.*$",
    re.I,
)
_LEADING_NOISE_RE = re.compile(
    r"^(?:my|our|the|a|an|this|that|his|her|their|mrs|mr|dr)\s+", re.I
)
_CHAT_PREFIX_RE = re.compile(
    r"^(?:whats\s?app|wa|telegram|tg|instagram|insta|ig|facebook|messenger|twitter|x)\s+(?:chat|dm|group)?\s*",
    re.I,
)
_NOT_A_NAME = {
    "",
    "me",
    "my",
    "myself",
    "i",
    "you",
    "him",
    "her",
    "them",
    "group",
    "chat",
    "the group",
    "someone",
    "anyone",
}


def _clean_chat_candidate(value: str) -> str:
    candidate = _strip_platform_words(value)
    candidate = _CLAUSE_TAIL_RE.sub("", candidate).strip(" .,;:-")
    candidate = _CHAT_PREFIX_RE.sub("", candidate).strip()
    candidate = _LEADING_NOISE_RE.sub("", candidate).strip()
    candidate = re.sub(r"\b(?:group|gc|chat|conversation)\b", "", candidate, flags=re.I).strip(" .,;:-")
    candidate = " ".join(candidate.split())
    return candidate


def _extract_chat(text: str) -> str:
    """Find the chat/person the user named.

    "watch my Telegram chat with Boss"        -> "Boss"
    "keep an eye on the Family group on WhatsApp" -> "Family"
    "watch WhatsApp messages from Rahul"      -> "Rahul"
    """
    patterns = (
        r"\b(?:the\s+)?(.+?)\s+(?:group|gc)\b",
        r"\b(?:chat|conversation)\s+(?:with|from|of)\s+(.+)$",
        r"\b(?:messages?|chats?|dms?|texts?)\s+from\s+(.+)$",
        r"\bfrom\s+(.+)$",
        r"\bwith\s+(.+)$",
        r"\b(?:for|to)\s+(.+)$",
        r"\bin\s+(.+)$",
        r"\b(?:chat|conversation|group)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        candidate = _clean_chat_candidate(match.group(1))
        if candidate.casefold() in _NOT_A_NAME or len(candidate) > 80:
            continue
        return candidate
    return ""


def _unescape(value: str) -> str:
    return " ".join(str(value or "").split()).strip(' "\'“”‘’')


def parse_watch_request(text: str) -> WatchIntent:
    raw = " ".join(str(text or "").split())
    if not raw:
        return WatchIntent(action="unhandled")

    # --- pausing / stopping the watch -------------------------------------------------
    if STOP_WATCH_RE.search(raw):
        platform, _ = _first_platform(raw)
        return WatchIntent(
            action="stop_watch",
            platform=platform,
            chat=_extract_chat(raw) if platform else "",
        )

    if STATUS_RE.search(raw):
        return WatchIntent(action="status")
    if SCAN_RE.search(raw):
        return WatchIntent(action="scan")

    # --- deciding about an item Weronika already flagged -------------------------------
    if LEAVE_IT_RE.match(raw):
        return WatchIntent(action="leave_it", reply=raw)
    if HOLD_RE.match(raw):
        return WatchIntent(action="hold", reply=raw)
    edit = EDIT_RE.match(raw)
    if edit and not WATCH_VERB_RE.search(raw):
        return WatchIntent(action="reply", reply=_unescape(edit.group(1))[:2000])

    # --- turning a watch on ------------------------------------------------------------
    platform, pattern = _first_platform(raw)
    if platform is None or not WATCH_VERB_RE.search(raw):
        return WatchIntent(action="unhandled")

    header = raw
    if ADD_RESET_RE.match(raw):
        header = ADD_RESET_RE.sub("", raw, count=1)
    chat = _extract_chat(header)
    if not chat and re.search(r"\b(?:any|all|every|someone|anyone)\b", header, re.I):
        return WatchIntent(
            action="add_watch",
            platform=platform,
            all_chats=True,
        )
    if not chat:
        return WatchIntent(
            action="add_watch",
            platform=platform,
            prompt=(
                f"Which {platform.value.title()} chat should I watch? "
                "For example: “Watch my Telegram chat with Boss.”"
            ),
        )
    if len(chat) > 80:
        return WatchIntent(
            action="add_watch",
            platform=platform,
            prompt="That chat name is too long. Give me the contact or group name only.",
        )

    propose = bool(PROPOSE_MODE_RE.search(raw)) or bool(
        re.search(r"\b(?:i can'?t|cannot|can not|won'?t be able to|i am not able to|i'?m not able to)\s+"
                  r"(?:reply|respond|answer)\b", raw, re.I)
    )
    mode: Literal["ask", "propose"] = "propose" if propose else "ask"
    rule: Literal["unanswered", "urgent"] = "urgent" if URGENT_RULE_RE.search(raw) else "unanswered"

    delay = _clamp_delay(MINUTES_RE.search(raw), 60)
    if not delay:
        delay = _clamp_delay(HOURS_RE.search(raw), 3600)
    reminder = 0
    reminder_match = re.search(r"\bremind me(?:\s+(?:again|every))?\s+(?:in|after)?\s*(\d{1,3})\s*(?:min|mins|minutes|m)\b", raw, re.I)
    if reminder_match:
        reminder = min(86_400, int(reminder_match.group(1)) * 60)

    unanswered_after = 600
    if re.search(r"\b(?:immediately|at once|right away|as soon as|the moment)\b", raw, re.I):
        unanswered_after = 0
    if re.search(r"\b(?:an hour|one hour|1 hour)\b", raw, re.I):
        unanswered_after = 3600

    return WatchIntent(
        action="add_watch",
        platform=platform,
        chat=chat,
        mode=mode,
        rule=rule,
        delay_seconds=delay,
        reminder_seconds=reminder,
        unanswered_after_seconds=unanswered_after,
        wants_group=bool(GROUP_ALLOW_RE.search(chat)) or bool(_WATCH_WORD_RE.search(raw)),
    )


def looks_like_absence_request(text: str) -> bool:
    return bool(_ABSENCE_CONTEXT_RE.search(str(text or "")))
