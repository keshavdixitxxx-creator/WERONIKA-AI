"""What Weronika says on a call she is handling for you.

Three rules shape every line in this module:

* **The other person is always told.** The first words after answering disclose that
  this is an AI assistant and not a human, and a caller who asks again gets the same
  honest answer. There is no setting that turns the disclosure off.
* **She speaks for you, not as you.** Weronika says what she knows — that you cannot
  come to the phone, that she will pass the message on. She does not invent promises,
  prices, dates, or decisions, because she does not know your plans.
* **Nothing secret leaves the phone.** One-time codes, card numbers, passwords and
  similar strings are never read aloud; they are flagged for you instead.

The wording here is the offline fallback. When the hosted brain answers the
``call-reply`` task it writes the line, in the caller's own language; these phrases
stand in when the brain is unreachable, and unlike a drafted message they are spoken
because they promise nothing on your behalf.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Callable, Iterable, Sequence

MAX_REPLY_CHARS = 400
MAX_TRANSCRIPT_TURNS = 12
CALL_REPLY_TIMEOUT_SECONDS = 12

# A caller's own words are quoted back to the brain only; they never reach a file.
_WORD_RE = re.compile(r"\w+", re.UNICODE)

# --------------------------------------------------------------------------- disclosure

DISCLOSURE_TEMPLATE = (
    "Hello, you have reached {owner_possessive} phone. I am Weronika, {owner_possessive} AI assistant. "
    "I am an AI, not a human, so please bear with me. {owner_name} cannot come to the phone "
    "right now, but I am listening. Tell me who is calling and what it is about, and I will "
    "make sure the message reaches {owner_object}."
)

DISCLOSURE_SHORT = (
    "Just so you know, I am Weronika, an AI assistant answering this phone. "
    "I am not a human. {owner_name} is not available right now, but I will pass on your message."
)

RE_DISCLOSURE_QUESTION = re.compile(
    r"\b(?:are you (?:an? )?(?:robot|bot|ai|a\.i\.|machine|computer|real|human|automated|recording)|"
    r"is this (?:an? )?(?:robot|bot|ai|a\.i\.|machine|computer|recording|automated|real (?:person|human))|"
    r"who (?:is|am) (?:this|talking)|"
    r"am i (?:talking|speaking) to (?:an? )?(?:robot|bot|ai|machine|computer|real person|real human|human|person|live person)|"
    r"are you (?:talking|speaking) (?:to me )?(?:from )?(?:an? )?(?:robot|bot|ai|machine)|"
    r"is (?:this|that) (?:an? )?(?:real )?(?:person|human|man|woman) (?:speaking|talking)?|"
    r"you (?:are|re) (?:an? )?(?:robot|bot|ai|machine|computer)|"
    r"tum (?:robot|ai|bot|machine) ho|kya (?:tum|aap) (?:insaan|human) ho|"
    r"robot ho|ai ho|bot ho|kaun bol raha|kon bol raha|"
    r"तुम (?:रोबोट|एआई|बॉट|मशीन) हो|कौन बोल रहा|रोबोट हो|एआई हो)\b",
    re.IGNORECASE,
)

DISCLOSURE_CONFIRMATION = (
    "Yes, I am an AI assistant. I am not a human being. I am answering because {owner_name} "
    "cannot come to the phone. I can take your message, or I can ask {owner_object} to call you back."
)

# --------------------------------------------------------------------------- safe phrases

GREETING_VARIANTS = (
    "Hello, I am listening.",
    "Yes, go ahead, I am listening.",
    "Hello? I can hear you, please go ahead.",
)

SILENCE_NUDGE = (
    "I am still here. If you can hear me, please tell me your name and what the call is about."
)

MISHEARD = (
    "Sorry, the line is not clear to me. Could you say that again, a little more slowly?"
)

MISHEARD_TWICE = (
    "I am having trouble hearing you clearly. I will tell {owner_name} that you called, "
    "and ask {owner_object} to call you back on this number."
)

ESCALATE_HUMAN = (
    "I understand you want to speak to {owner_name} directly. I am an AI and I cannot hand this "
    "phone over while {owner_name} is away, so I will tell {owner_object} that you called and "
    "that it is important. Please tell me your name so the message is not lost."
)

TAKE_MESSAGE_VARIANTS = (
    "Thank you. I have written that down and I will give {owner_name} your message as soon as "
    "{owner_name} is back. Is there anything else you want me to pass on?",
    "Thank you, that is written down too. {owner_name} will see it as soon as {owner_name} is "
    "back. Please go on if there is more you want me to take.",
    "Understood, I have noted that down as well, exactly as you said it. I will pass all of it "
    "on to {owner_name} together. Anything else?",
)
# The first wording is the one callers hear first and the one the tests pin.
TAKE_MESSAGE = TAKE_MESSAGE_VARIANTS[0]

CALLBACK_PROMPT = (
    "Should I ask {owner_name} to call you back? If yes, please confirm the number you are calling from."
)

NOTHING_TO_ADD = (
    "I have everything I need. I will pass your message on to {owner_name}."
)

GOODBYE = (
    "Thank you for calling. I will tell {owner_name} about this conversation. Goodbye."
)

GOODBYE_HANDED_BACK = (
    "{owner_name} is here now and will take the call. One moment, please."
)

BUSY_SIGNAL = (
    "I am sorry, I could not understand that well enough to answer. I will not guess. "
    "I will tell {owner_name} that you called."
)

UNSUPPORTED_REQUEST = (
    "I am only taking a message on this phone. I cannot make decisions, payments, or changes "
    "for {owner_name}. I will write down what you need and pass it on."
)

SECRET_REFUSAL = (
    "I am not allowed to read out any code, password, card number, or account detail over the "
    "phone, and I will not ask {owner_name} for one either. If this is about a verification code, "
    "please call {owner_object} back when {owner_name} is free."
)

SUSPECTED_SPAM = (
    "I am an AI assistant taking a message. If this call is about a payment, a prize, a loan, "
    "or an account being blocked, I will only record it and let {owner_name} decide."
)

# Phrases that suggest the caller wants something the user must decide personally.
_DECISION_WORDS = {
    "approve", "approval", "sign", "signature", "payment", "pay", "transfer", "money", "cash",
    "loan", "emi", "installment", "cheque", "deal", "offer", "price", "quote", "negotiate",
    "salary", "hike", "resign", "fire", "hire", "marry", "engagement", "doctor", "medicine",
    "prescription", "police", "court", "lawyer", "consent", "confirm booking", "cancel booking",
    "manzur", "haan bolo", "paisa", "paise", "loan", "approve karo", "sign karo",
}

_SPAM_WORDS = {
    "lottery", "prize", "winner", "won", "jackpot", "blocked", "suspended", "kyc", "refund",
    "double your", "investment", "crypto", "bitcoin", "insurance policy", "credit card offer",
    "pre-approved", "courier stuck", "customs", "legal notice", "arrest warrant", "cyber cell",
    "आपका अकाउंट", "केवाईसी", "लॉटरी", "इनाम",
}

# Anything shaped like a one-time code, card, UPI id, or password must never be spoken.
_SECRET_PATTERNS = (
    re.compile(r"\b(?:otp|o\.t\.p|one time password|verification code|code)\b[^.\n]{0,40}\b\d{4,8}\b", re.I),
    re.compile(r"\b\d{4,8}\b[^.\n]{0,20}\b(?:otp|code|password)\b", re.I),
    re.compile(r"\b(?:password|passwd|pin|cvv|upi pin|secret)\b\s*[:\-]?\s*\S+", re.I),
    re.compile(r"\b(?:\d[ -]?){12,19}\b"),
    re.compile(r"\b[\w.\-]{2,}@(?:okaxis|okicici|okhdfcbank|ybl|apl|axl|ibl|barodampay|kotak|sbi|paytm|upi)\b", re.I),
)

_HINGLISH_RE = re.compile(
    r"\b(?:kya|kyun|kaise|kab|kahan|kaun|nahi|nahin|hai|hoon|ho|karo|karna|batao|bolo|sun"
    r"|aap|tum|main|mera|meri|theek|thik|accha|acha|haan|ji|zaroori|jaldi|abhi|baad me|phone)\b",
    re.IGNORECASE,
)
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


# --------------------------------------------------------------------------- helpers


def telegram_unsupported_note() -> str:
    """The honest answer about Telegram calls, wherever the orb offers channels.

    Telegram Web has no calling and Telegram's Bot API cannot make or receive calls, so
    there is nothing to automate. Saying that beats a switch that silently does nothing.
    """
    return (
        "Telegram calls cannot be handled: Telegram Web has no calling, and Telegram's Bot API "
        "cannot make or receive calls. Weronika can read and answer your Telegram messages "
        "(reply watch), and she handles calls on your SIM through the cable and on WhatsApp Web."
    )


def owner_words(owner: str) -> dict[str, str]:
    """Fill the disclosure and phrase templates without inventing a gender.

    The name comes from the orb's own address for you ("Commander" by default), so
    every line reads naturally and nothing is guessed about you.
    """
    name = (owner or "").strip() or "the owner of this phone"
    possessive = f"{name}'s" if not name.lower().endswith("s") else f"{name}'"
    return {
        "owner": name,
        "owner_name": name,
        "owner_possessive": possessive,
        "owner_object": name,
    }


def fill(template: str, owner: str) -> str:
    try:
        return template.format(**owner_words(owner)).strip()
    except (KeyError, IndexError):
        return template.strip()


def looks_like_hinglish(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text) or _HINGLISH_RE.search(text))


def detect_secret(text: str) -> str:
    """Return a label for the first secret-shaped string in ``text``, else "".

    The match itself is not returned and not stored: the transcript keeps the label
    only, so a code that was spoken at the phone never lands in a summary.
    """
    lowered = text.lower()
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            if "otp" in lowered or "code" in lowered or "verification" in lowered:
                return "one-time code"
            if "password" in lowered or "pin" in lowered or "cvv" in lowered:
                return "password or PIN"
            if "upi" in lowered or "@" in text:
                return "UPI handle"
            return "card or account number"
    return ""


def redact_secrets(text: str) -> str:
    """Replace secret-shaped strings with a marker before the text is stored."""
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[withheld]", redacted)
    return redacted


def mentions_decision(text: str) -> bool:
    words = {item.lower() for item in _WORD_RE.findall(text)}
    return bool(words & _DECISION_WORDS)


def mentions_spam(text: str) -> bool:
    lowered = text.lower()
    if any(word in lowered for word in _SPAM_WORDS):
        return True
    words = {item.lower() for item in _WORD_RE.findall(text)}
    return bool(words & _SPAM_WORDS)


def caller_asks_for_human(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:i (?:want|need) to (?:speak|talk) to|let me (?:speak|talk) to|put (?:him|her|them) on|"
            r"is (?:he|she|keshav|sir|madam) (?:there|available)|give (?:me|him|her) (?:the )?phone|"
            r"real person|human please|keshav se (?:baat|bat) (?:karni|karao)|phone do|unhe (?:do|bulaao)|"
            r"बोलने दो|फ़ोन दो|उन्हें बुलाओ)\b",
            text,
            re.IGNORECASE,
        )
    )


# Closing a call is usually a handful of polite words and nothing else. Every token has
# to belong to the closing vocabulary, and one of them has to actually mean "we are
# finished", so "tell him the payment is done" is a message and not a goodbye.
_DONE_TOKENS = {
    "ok", "okay", "okk", "accha", "acha", "achha", "theek", "thik", "fine", "alright", "right",
    "good", "great", "thanks", "thank", "you", "bye", "goodbye", "see", "later", "that's",
    "thats", "that", "is", "all", "nothing", "else", "more", "bas", "itna", "hi", "chalo",
    "cut", "done", "shukriya", "dhanyavad", "ji", "haan", "yes", "no", "tata", "alvida", "tc",
    "phir", "milte", "milenge", "bye bye", "theek hai", "thik hai", "जी", "हाँ", "ठीक", "बस",
    "शुक्रिया", "धन्यवाद", "अलविदा", "चलो", "ठीक है", "बस इतना",
}
_DONE_REQUIRED = {
    "bye", "goodbye", "thanks", "thank", "shukriya", "dhanyavad", "done", "all", "tata",
    "alvida", "tc", "cut", "chalo", "bas", "alvida", "more", "else",
}
_DONE_WORD_RE = re.compile(r"[a-z'’]+|[\u0900-\u097F]+")


def caller_is_done(text: str) -> bool:
    """True when the caller's line is a goodbye rather than a message."""
    tokens = _DONE_WORD_RE.findall(str(text or "").casefold())
    if not tokens or len(tokens) > 8:
        return False
    if not any(token in _DONE_REQUIRED for token in tokens):
        return False
    return all(token in _DONE_TOKENS for token in tokens)


# --------------------------------------------------------------------------- responder


class SpokenLine(str):
    """A line Weronika will speak.

    ``confirmed`` is True only when the hosted brain named the ``call-reply`` task,
    meaning it really wrote a short spoken answer rather than replying as chat.
    Unconfirmed wording is allowed on a call only because these fallback lines make
    no promise for you; a line the brain did not confirm is still shown in the orb
    and written into the transcript.
    """

    confirmed: bool = False

    def __new__(cls, text: object = "", confirmed: bool = False) -> "SpokenLine":
        instance = super().__new__(cls, str(text or ""))
        instance.confirmed = bool(confirmed)
        return instance


def fallback_line(transcript: Sequence[tuple[str, str]], *, owner: str, misheard: int = 0) -> str:
    """A neutral, promise-free answer when the brain cannot write one.

    The rules are deliberately boring: acknowledge, ask for the point, take the
    message, offer a callback. Anything that would decide something for you ends up
    in ``UNSUPPORTED_REQUEST`` instead of being invented.
    """
    caller_turns = [text for speaker, text in transcript if speaker == "caller"]
    last = caller_turns[-1] if caller_turns else ""
    words = fill(
        MISHEARD if misheard == 1 else MISHEARD_TWICE if misheard >= 2 else "",
        owner,
    ) if misheard else ""
    if words:
        return words
    if not last:
        return fill(GREETING_VARIANTS[len(caller_turns) % len(GREETING_VARIANTS)], owner)
    if caller_is_done(last):
        return fill(NOTHING_TO_ADD, owner)
    if caller_asks_for_human(last):
        return fill(ESCALATE_HUMAN, owner)
    if mentions_decision(last) or mentions_spam(last):
        return fill(UNSUPPORTED_REQUEST, owner)
    # Rotate the wording by how many messages she has already taken on this call, so a
    # caller who explains three things does not hear the same sentence three times.
    taken = {fill(variant, owner) for variant in TAKE_MESSAGE_VARIANTS}
    used = sum(1 for speaker, text in transcript if speaker != "caller" and text in taken)
    return fill(TAKE_MESSAGE_VARIANTS[used % len(TAKE_MESSAGE_VARIANTS)], owner)


def build_brain_responder(
    endpoint: str,
    *,
    owner: str = "Commander",
) -> Callable[[dict[str, object], Sequence[tuple[str, str]]], SpokenLine]:
    """Ask the hosted brain for the next spoken line of a live call.

    The request carries the transcript and the disclosure state only — no contact
    list, no messages, no files. When the endpoint is empty (``--brain-endpoint off``)
    every line comes from this module instead, on this device.
    """

    def respond(context: dict[str, object], transcript: Sequence[tuple[str, str]]) -> SpokenLine:
        if not endpoint:
            return SpokenLine(
                fallback_line(transcript, owner=str(context.get("owner") or owner),
                              misheard=int(context.get("misheard") or 0)),
                confirmed=False,
            )
        tail: Iterable[tuple[str, str]] = list(transcript)[-MAX_TRANSCRIPT_TURNS:]
        lines = "\n".join(
            f"{'Caller' if speaker == 'caller' else 'Weronika'}: {text}" for speaker, text in tail
        )
        caller_language = "Hinglish (Hindi written in Latin script)" if any(
            looks_like_hinglish(text) for speaker, text in tail if speaker == "caller"
        ) else "the same language the caller used"
        question = (
            "You are Weronika, an AI assistant speaking on a live phone call for the phone's owner. "
            "You already told the caller that you are an AI and not a human.\n"
            f"Phone owner: {context.get('owner') or owner}\n"
            f"Channel: {context.get('channel')}\n"
            f"Caller: {context.get('caller') or 'unknown'}\n"
            f"Call duration so far: {context.get('seconds')} seconds\n"
            "Call transcript:\n"
            f"{lines or '(nothing said yet)'}\n\n"
            f"Write the ONE sentence Weronika says next, in {caller_language}.\n"
            "Hard rules: it is spoken aloud, so keep it under 40 words and free of markdown; "
            "never claim to be a human; never invent facts, dates, prices, approvals, or promises "
            "the owner has not made; never repeat a one-time code, password, card number, or UPI handle; "
            "if the caller needs a decision only the owner can make, say you will pass the message on "
            "and offer a callback; if you did not understand, ask them to repeat.\n"
            "Reply with the spoken sentence only."
        )
        payload = json.dumps(
            {
                "message": question,
                "history": [],
                "lang": "",
                "addressName": str(context.get("owner") or owner),
                "task": "call-reply",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=CALL_REPLY_TIMEOUT_SECONDS) as response:
                raw = response.read(200_000).decode("utf-8", errors="replace")
                applied = str(response.headers.get("X-Weronika-Task") or "").strip().casefold()
        except (urllib.error.URLError, TimeoutError, OSError):
            raw, applied = "", ""
        except Exception:
            raw, applied = "", ""
        text = _spoken_text(raw)
        if not text:
            return SpokenLine(
                fallback_line(
                    transcript,
                    owner=str(context.get("owner") or owner),
                    misheard=int(context.get("misheard") or 0),
                ),
                confirmed=False,
            )
        confirmed = applied == "call-reply"
        # A secret in the model's own output is never spoken — and not spoken redacted
        # either, because "your [withheld]" is nonsense on a phone call. The refusal line
        # replaces the whole answer, and the answer stops being trusted.
        if detect_secret(text):
            text = fill(SECRET_REFUSAL, str(context.get("owner") or owner))
            confirmed = False
        return SpokenLine(" ".join(text.split())[:MAX_REPLY_CHARS], confirmed=confirmed)

    return respond


def _spoken_text(raw: str) -> str:
    """The hosted brain answers with SSE text deltas; tolerate plain JSON too."""
    if not raw:
        return ""
    if not raw.lstrip().startswith("data:"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _clean_spoken(raw)
        if isinstance(data, dict):
            for key in ("text", "reply", "message", "content"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return _clean_spoken(value)
        return ""
    pieces: list[str] = []
    for block in raw.split("\n\n"):
        line = next((item for item in block.splitlines() if item.startswith("data:")), "")
        if not line:
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        piece = event.get("text") or event.get("delta") or ""
        if isinstance(piece, str):
            pieces.append(piece)
    return _clean_spoken("".join(pieces))


def _clean_spoken(text: str) -> str:
    """Spoken lines carry no markup, quotes, or stage directions."""
    cleaned = re.sub(r"\[[^\]]*\]", " ", text or "")
    cleaned = re.sub(r"[*_`#>]+", " ", cleaned)
    cleaned = re.sub(r"^[\s\"'“”]+|[\s\"'“”]+$", "", cleaned)
    return " ".join(cleaned.split()).strip()


def summary_lines(
    *,
    owner: str,
    channel: str,
    caller: str,
    number: str,
    seconds: int,
    transcript: Sequence[tuple[str, str]],
    flags: Sequence[str],
    outcome: str,
) -> str:
    """A short written summary of the call, for you — never spoken to the caller.

    Built from the transcript on this device so it works with no brain and no
    network; the wording is plain because it is a record, not a performance.
    """
    words = owner_words(owner)
    caller_turns = [text for speaker, text in transcript if speaker == "caller"]
    spoke = [text for speaker, text in transcript if speaker == "weronika"]
    lines = [
        f"Call handled by Weronika · {channel} · {caller or 'Unknown caller'}"
        + (f" ({number})" if number else ""),
        f"Length {seconds // 60}m {seconds % 60:02d}s · {len(caller_turns)} line(s) from the caller"
        f" · {len(spoke)} line(s) spoken by Weronika.",
    ]
    if caller_turns:
        first = caller_turns[0][:300]
        lines.append(f"They opened with: “{first}”")
        if len(caller_turns) > 1:
            last = caller_turns[-1][:300]
            lines.append(f"They ended with: “{last}”")
    else:
        lines.append("The caller said nothing Weronika could understand.")
    for flag in flags:
        lines.append(f"Flagged: {flag}.")
    if outcome:
        lines.append(f"How it ended: {str(outcome).rstrip('. ')}.")
    lines.append(
        f"Weronika told the caller she is an AI and that {words['owner_name']} would get the message."
    )
    return "\n".join(lines)
