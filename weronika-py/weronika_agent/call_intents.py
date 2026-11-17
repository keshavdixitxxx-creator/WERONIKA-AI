"""Deliberately narrow parsing for call-handling requests.

Like :mod:`watch_intents`, only an explicit call request is understood here; anything
else stays ordinary chat with the cloud brain. The narrowness is the safety feature —
a sentence that merely contains the word "call" ("call me a cab", "I'll call you back",
"what do you call this?") must never be read as an instruction to answer a phone.

Two rules shape the grammar:

* Turning call handling **on** needs an explicit request, and it never means "answer
  everything". It means "ask me about each call".
* Handing a call over ("you handle it") is understood only as an answer to the question
  Weronika just asked; the service, not this parser, decides which call it applies to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .call_dialogue import telegram_unsupported_note
from .models import CallChannel, CallDecision, CallRoute

MAX_SPOKEN_CHARS = 600

# "handle my calls" / "answer my calls for me" / "meri calls uthao" — turning it on.
ENABLE_RE = re.compile(
    r"\b(?:(?:can |could |please |now |from now on )?"
    r"(?:handle|take|attend|answer|pick up|screen|manage|look after)\s+"
    r"(?:my |the )?(?:phone )?(?:calls?|rings?)\b"
    r"|(?:calls?|phone)\s+(?:handle|sambhal|sambhalo|uthao|uthaao|attend|manage)\s*(?:kar(?:o| do| diya)?|liya)?\b"
    r"|(?:meri|mere|humari)\s+(?:calls?|phone)\s+(?:uthao|sambhalo|handle|attend)"
    r"|(?:be|act as)\s+(?:my\s+)?(?:call\s+)?(?:screener|receptionist|assistant on calls)"
    r"|(?:watch|monitor|keep an eye on)\s+(?:my\s+)?(?:incoming\s+)?calls?\b"
    r"|call (?:handling|screening|watch)\s+(?:on|start|shuru|enable)"
    r"|start (?:handling|answering|taking) (?:my )?calls?\b"
    r"|कॉल (?:उठाओ|संभालो)|फ़ोन (?:उठाओ|संभालो))",
    re.IGNORECASE,
)

DISABLE_RE = re.compile(
    # Both the -ing and the plain verb form: "stop handling my calls" and
    # "don't answer my calls" mean the same thing, and the second one must never be
    # read as a request to answer.
    r"\b(?:stop|don'?t|do not|no more|turn off|switch off|disable|quit|never)\s+"
    r"(?:you\s+)?(?:handling|taking|answering|attending|screening|watching|"
    r"handle|take|answer|pick up|attend|screen|watch)\s+"
    r"(?:my |the )?(?:phone )?calls?\b"
    r"|(?:turn|switch)\s+(?:off|out)\s+(?:the\s+)?call\s+(?:handling|screening|watch)\b"
    r"|call (?:handling|screening|watch)\s+(?:off|stop|band)"
    r"|(?:calls?|phone)\s+(?:uthana|handle karna)\s+band"
    r"|कॉल (?:उठाना|संभालना) बंद",
    re.IGNORECASE,
)

SCAN_RE = re.compile(
    r"\b(?:scan|check|look at|see)\s+(?:my\s+)?(?:the\s+)?(?:calls?|phone)\b"
    r"|(?:is|are)\s+(?:someone|anyone|anybody|koi)\s+(?:calling|ringing|on the (?:phone|line))"
    r"|(?:who|kaun)\s+(?:is calling|calling|call kar (?:raha|rahi)|kar raha hai)"
    r"|(?:any|koi)\s+(?:new\s+|missed\s+|incoming\s+)?calls?\??\s*$"
    r"|(?:is the phone|phone)\s+ringing"
    r"|कौन कॉल कर रहा",
    re.IGNORECASE,
)

STATUS_RE = re.compile(
    r"\b(?:call|calls)\s+(?:status|watch status|setup|settings)\b"
    r"|what calls (?:did you|have you) (?:handle|handled|answered|taken)"
    r"|(?:which|what) calls (?:are|were) (?:you )?(?:handling|handled|watching)"
    r"|(?:show|give)\s+(?:me\s+)?(?:the\s+)?call (?:summary|summaries|log|history)"
    r"|(?:kaun si|kitni)\s+calls?\b",
    re.IGNORECASE,
)

LINKS_RE = re.compile(
    r"\b(?:is|are|which|what)\s+(?:my\s+)?(?:phone|device|android|iphone)\s*(?:is\s+|are\s+)?"
    r"(?:connected|linked|there|detected|plug(?:ged)? in)\b"
    r"|(?:check|test|show)\s+(?:my\s+)?call\s+(?:setup|link|connection|audio|route)"
    r"|(?:which|what)\s+(?:audio\s+)?route\b.*\bcalls?\b|\bcalls?\b.*\b(?:audio\s+)?route\b"
    r"|(?:can you|is it possible to)\s+(?:hear|answer|handle)\s+(?:the\s+)?calls?\s+(?:on|from|through)\s+"
    r"(?:my\s+)?(?:phone|whatsapp|telegram|sim)"
    r"|phone (?:connect|link) (?:hai|hai kya|check)",
    re.IGNORECASE,
)

HANDOVER_RE = re.compile(
    # Either the object is named ("give me the call"), or the whole sentence is one of a
    # short list of exact phrases. Without that, "give me the summary" would be read as
    # "hand the phone over".
    r"^\s*(?:please\s+)?(?:weronika[,\s]+|veronica[,\s]+)?"
    r"(?:(?:give|hand|pass)\s+(?:me\s+|back\s+)?(?:the\s+)?(?:call|phone|line)\s*$"
    r"|(?:give|hand|pass)\s+(?:it\s+over|it\s+to\s+me)\s*$"
    r"|(?:i'?m|i am)\s+here(?:\s+now)?\s*$"
    r"|main\s+(?:hoon|aa gaya|aa gayi|aaya|aayi)\s*$"
    r"|le lo\s*$|phone\s+(?:mujhe\s+)?do\s*$|mujhe\s+(?:phone|call)\s+do\s*$|de do\s*$"
    r"|i'?ll talk now\s*$|main baat kar(?:ta|ti|unga|ungi) hoon\s*$)",
    re.IGNORECASE,
)

END_RE = re.compile(
    r"^\s*(?:please\s+)?(?:weronika[, ]+|veronica[, ]+)?"
    r"(?:end|hang up|hangup|cut|close|drop|disconnect)\s+"
    r"(?:the\s+|this\s+|up\s+)?(?:call|phone|line)\b"
    r"|^\s*(?:hang up|call (?:end|cut|kaat)|kaat do|band kar do|cut kar do|फ़ोन काट दो|कॉल काटो)\s*$",
    re.IGNORECASE,
)

DICTATE_PREFIX_RE = re.compile(
    r"^\s*(?:say|tell them|tell him|tell her|speak|bol|bolo|bol do|kaho|keh do)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)

DICTATE_RE = re.compile(
    r"^\s*(?:say|tell them|tell him|tell her|speak|bol|bolo|bol do|kaho|keh do)\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)

HEARD_RE = re.compile(
    r"^\s*(?:he said|she said|they said|caller said|the caller said|he'?s saying|she'?s saying|"
    r"they'?re saying|usne kaha|unhone kaha|woh (?:bol|keh) (?:raha|rahi) (?:hai|tha)|"
    r"उसने कहा|वो बोल रहा है)\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)

READ_SECRET_RE = re.compile(
    r"^\s*(?:read|say|speak)\s+(?:it|that|the code)\s+(?:out\s+)?(?:anyway|regardless|please)\s*$",
    re.IGNORECASE,
)

SUMMARY_SEND_RE = re.compile(
    r"\b(?:send|share|forward)\s+(?:the\s+|that\s+)?(?:call\s+)?summary\s+"
    r"(?:on|to|via|through)\s+(.+)$",
    re.IGNORECASE,
)

# Words that may sit between "example" and "call": a channel, or a qualifier that makes
# clear this is a rehearsal rather than a real call.
_EXAMPLE_QUALIFIER = r"(?:(?:incoming|outgoing|phone|whats\s?app|wa|telegram|tg|sim|video|fake|dummy|scripted|sample|scam|otp)\s+)*"

SIMULATE_RE = re.compile(
    r"\b(?:give|show|run|do|play)\s+(?:me\s+)?(?:an?\s+)?(?:example|demo|sample|test)\s+"
    r"(?:of\s+(?:an?\s+)?|on\s+|with\s+|about\s+)?"
    + _EXAMPLE_QUALIFIER + r"call\b"
    r"|\b(?:simulate|demo|example|test|run|rehearse)\s+(?:a\s+|an\s+|the\s+)?"
    + _EXAMPLE_QUALIFIER + r"call\s*(?:example|demo|simulation)?\b"
    r"|\b(?:whats\s?app|telegram|phone|sim)\s+call\s+(?:example|demo)\b"
    r"|\b(?:scan|check)\s+(?:an?\s+)?example\b"
    r"|\bexample call\b|\bdemo call\b|\bcall\s+(?:example|demo)\b",
    re.IGNORECASE,
)

CHANNEL_PATTERNS: tuple[tuple[CallChannel, re.Pattern[str]], ...] = (
    (CallChannel.WHATSAPP, re.compile(r"\b(?:whats\s?app|wa|whatsapp web)\b", re.IGNORECASE)),
    (CallChannel.TELEGRAM, re.compile(r"\b(?:telegram|tg)\b", re.IGNORECASE)),
    (CallChannel.SIM, re.compile(r"\b(?:sim|phone|mobile|cell|carrier|cable|usb|adb|android)\b", re.IGNORECASE)),
)

ROUTE_PATTERNS: tuple[tuple[CallRoute, re.Pattern[str]], ...] = (
    (CallRoute.BLUETOOTH, re.compile(r"\b(?:bluetooth|bt|hands[- ]?free|headset|earbuds|buds)\b", re.IGNORECASE)),
    (CallRoute.AUX, re.compile(r"\b(?:aux|line[- ]?in|3\.?5\s?mm|cable|wired)\b", re.IGNORECASE)),
    (CallRoute.SPEAKER_MIC, re.compile(r"\b(?:speaker|mic|mike|loudspeaker|on speaker)\b", re.IGNORECASE)),
)

DECISION_RE = re.compile(
    r"^\s*(?:please\s+)?(?:weronika[, ]+|veronica[, ]+)?"
    r"(?:you\s+(?:handle|take|answer|pick|attend)|"
    r"(?:handle|take|answer|attend)\s+(?:it|the\s+call|the\s+phone)|pick\s+(?:it|the\s+call)\s+up|"
    r"i'?ll\s+take\s+it|i\s+will\s+(?:take|handle|answer)|let\s+me\s+(?:take|handle|answer)|"
    r"ignore\s+it|ignore|skip\s+it|let\s+it\s+ring|decline\s+it|reject\s+it|main\s+uthaunga|"
    r"tum\s+utha\s+lo|aap\s+uthao|mat\s+uthao)\s*(?:it|the\s+call|please)?\s*[.!]*\s*$",
    re.IGNORECASE,
)

# Phrases where "call" is ordinary conversation, never an instruction.
NOT_A_CALL_REQUEST_RE = re.compile(
    r"\b(?:call me (?:a |an )?(?:cab|taxi|uber|ola|doctor|plumber)|i'?ll call you|"
    r"i will call (?:you|him|her|them)|call (?:you|him|her|them) (?:back|later|tomorrow)|"
    r"what do you call|we call it|they call (?:it|him|her)|a call (?:for|to) (?:help|action)|"
    r"call of duty|cold call|call the shots|wake[- ]up call|phone a friend)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CallIntent:
    """One understood call request, or ``action == "unhandled"``."""

    action: str = "unhandled"
    decision: str = ""
    text: str = ""
    reason: str = ""
    channel: CallChannel | None = None
    route: CallRoute | None = None
    recipient: str = ""
    platform: str = ""
    read_secret: bool = False
    prompt: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "decision": self.decision,
            "text": self.text,
            "reason": self.reason,
            "channel": self.channel.value if self.channel else "",
            "route": self.route.value if self.route else "",
            "recipient": self.recipient,
            "platform": self.platform,
            "read_secret": self.read_secret,
            "prompt": self.prompt,
        }


def has_call_intent(text: str) -> bool:
    """True when the sentence is about handling calls at all.

    Used to decide whether the local worker answers directly or the request goes to the
    cloud brain, so it is deliberately broad while ``parse_call_request`` stays narrow.
    """
    value = str(text or "").strip()
    if not value or len(value) > 400:
        return False
    if DICTATE_PREFIX_RE.match(value):
        return True
    if NOT_A_CALL_REQUEST_RE.search(value):
        return False
    if not re.search(r"\b(?:call|calls|calling|phone|ring|ringing|handset|sim)\b", value, re.IGNORECASE):
        return False
    return bool(
        ENABLE_RE.search(value)
        or DISABLE_RE.search(value)
        or SCAN_RE.search(value)
        or STATUS_RE.search(value)
        or LINKS_RE.search(value)
        or HANDOVER_RE.match(value)
        or END_RE.match(value)
        or READ_SECRET_RE.match(value)
        or SUMMARY_SEND_RE.search(value)
        or SIMULATE_RE.search(value)
        or DECISION_RE.match(value)
    )


def parse_channel(text: str) -> CallChannel | None:
    for channel, pattern in CHANNEL_PATTERNS:
        if pattern.search(text):
            return channel
    return None


def parse_route(text: str) -> CallRoute | None:
    for route, pattern in ROUTE_PATTERNS:
        if pattern.search(text):
            return route
    return None


def parse_call_request(text: str) -> CallIntent:
    """Turn one sentence into a call action. Anything unclear stays unhandled."""
    value = " ".join(str(text or "").split())
    if not value or len(value) > 400:
        return CallIntent()
    dictated = DICTATE_PREFIX_RE.match(value)
    if dictated:
        # "say: I will call you back" is your wording for her to speak, so the words after
        # the colon are content and must not be re-read as an instruction.
        return CallIntent(action="dictate", text=_clean_spoken(dictated.group(1)))
    if NOT_A_CALL_REQUEST_RE.search(value):
        return CallIntent()

    # A live-call instruction beats a settings request: "end the call" during a call is
    # about that call, not about turning the feature off.
    if READ_SECRET_RE.match(value):
        return CallIntent(action="read_secret")
    if HANDOVER_RE.match(value):
        return CallIntent(action="handover")
    if END_RE.match(value):
        return CallIntent(action="end")

    decision = _parse_decision(value)
    if decision:
        return CallIntent(action="decide", decision=decision.value)

    heard = HEARD_RE.match(value)
    if heard:
        return CallIntent(action="hear", text=_clean_spoken(heard.group(1)))

    dictated = DICTATE_RE.match(value)
    if dictated and re.search(r"\b(?:call|them|him|her|phone|caller)\b", value, re.IGNORECASE):
        # "Say: I'll be there" during a call is your wording for her to speak. Requiring a
        # call-related word keeps "say hello to mom" as ordinary chat.
        return CallIntent(action="dictate", text=_clean_spoken(dictated.group(1)))

    summary = SUMMARY_SEND_RE.search(value)
    if summary:
        target = summary.group(1).strip()
        platform = ""
        for name, pattern in (
            ("whatsapp", re.compile(r"\bwhats\s?app\b|\bon wa\b", re.IGNORECASE)),
            ("telegram", re.compile(r"\btelegram\b|\btg\b", re.IGNORECASE)),
        ):
            if pattern.search(target):
                platform = name
                break
        recipient = re.sub(
            r"\b(?:on|via|through|to)\s+(?:whats\s?app|wa|telegram|tg)\b", " ", target, flags=re.IGNORECASE
        )
        recipient = re.sub(r"^(?:whats\s?app|wa|telegram|tg)\s*", "", recipient.strip(), flags=re.IGNORECASE)
        recipient = re.sub(r"^(?:on|via|through|to)\s+", "", recipient.strip(), flags=re.IGNORECASE)
        recipient = recipient.strip(" .,!").strip()
        return CallIntent(action="summary_send", platform=platform, recipient=recipient[:60])

    if SIMULATE_RE.search(value):
        return CallIntent(action="simulate", channel=parse_channel(value))

    if DISABLE_RE.search(value):
        return CallIntent(action="disable", channel=parse_channel(value))

    if ENABLE_RE.search(value):
        return CallIntent(action="enable", channel=parse_channel(value), route=parse_route(value))

    if LINKS_RE.search(value):
        return CallIntent(action="links", channel=parse_channel(value))

    if STATUS_RE.search(value):
        return CallIntent(action="status")

    if SCAN_RE.search(value):
        return CallIntent(action="scan", channel=parse_channel(value))

    return CallIntent()


def _parse_decision(value: str) -> CallDecision | None:
    """Read an answer to "Are you able to handle the call?" from a short reply."""
    match = DECISION_RE.match(value)
    if not match:
        return None
    try:
        return CallDecision.parse(value)
    except ValueError:
        return None


def _clean_spoken(text: str) -> str:
    cleaned = re.sub(r"^[:\-\s]+|[\s]+$", "", str(text or ""))
    return " ".join(cleaned.split())[:MAX_SPOKEN_CHARS]


def telegram_note() -> str:
    """The honest answer about Telegram calls, used wherever the orb offers channels."""
    return telegram_unsupported_note()
