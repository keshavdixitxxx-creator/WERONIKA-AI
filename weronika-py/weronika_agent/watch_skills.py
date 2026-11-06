"""A small, honest capability catalog for Weronika's local worker.

The catalog is what the orb shows in the SKILLS panel. It lists only what the local
worker can actually do on this device, so a skill never promises more than the code
behind it performs. Each entry names the confirmation step its actions require.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    summary: str
    platforms: tuple[str, ...]
    commands: tuple[str, ...]
    needs: tuple[str, ...]
    safety: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "platforms": list(self.platforms),
            "commands": list(self.commands),
            "needs": list(self.needs),
            "safety": self.safety,
        }


CATALOG: tuple[Skill, ...] = (
    Skill(
        id="send-message",
        name="Send a message",
        summary=(
            "Finds a chat or contact, opens it, types your exact text and sends it only "
            "after you reply ‘confirm send’."
        ),
        platforms=("WhatsApp", "Telegram", "Instagram", "Messenger", "X"),
        commands=(
            "Send a WhatsApp message to Boss saying I’m on leave tomorrow",
            "Telegram Rahul that I’ll call after lunch",
        ),
        needs=("The local worker running (start.bat)", "Signed in to that app in its Weronika browser window"),
        safety="Two steps: Weronika shows the resolved chat and exact text; sending needs your separate confirmation.",
    ),
    Skill(
        id="reply-watch-ask",
        name="Watch · ask me first",
        summary=(
            "Reads the chats you name every few seconds. When someone messages you and you have "
            "not replied, Weronika tells you and asks what to say — she does not write it herself."
        ),
        platforms=("WhatsApp", "Telegram"),
        commands=(
            "Watch my WhatsApp chat with Boss",
            "Keep an eye on Telegram chat with Rahul, ask me if I don’t reply in 10 minutes",
        ),
        needs=("The Weronika browser window stays open on that app",),
        safety="No message is typed or sent until you give the exact reply and confirm it.",
    ),
    Skill(
        id="reply-watch-propose",
        name="Watch · propose a reply",
        summary=(
            "Same watch, but Weronika also drafts a suggested reply in your language so you can "
            "approve it with ‘send it’ or rewrite it."
        ),
        platforms=("WhatsApp", "Telegram"),
        commands=(
            "Watch Telegram chat with Boss and reply for me if I can’t",
            "Watch the Family group on WhatsApp and you can suggest a reply",
        ),
        needs=("The Weronika browser window stays open on that app",),
        safety="A suggestion is text in the orb, not a send. The exact text is prepared in the chat and sent only after ‘confirm send’.",
    ),
    Skill(
        id="reply-watch-urgent",
        name="Watch · urgent only",
        summary=(
            "Stays quiet for small talk and only interrupts you for messages that look urgent: "
            "questions, deadlines, today/ASAP wording, or your own keywords."
        ),
        platforms=("WhatsApp", "Telegram"),
        commands=("Watch WhatsApp chats and only interrupt me if it’s urgent",),
        needs=("The Weronika browser window stays open on that app",),
        safety="Same two-step confirmation before anything is typed in the chat.",
    ),
    Skill(
        id="browse",
        name="Search and open",
        summary=(
            "Breaks a spoken request into steps: search the web for what you said, open the result "
            "you named, and read the page back to you. Lists the steps before it runs them."
        ),
        platforms=("Web", "DuckDuckGo"),
        commands=(
            "Search for today’s weather in Ghaziabad and open the first result",
            "Open the first result and summarize it",
            "Open github in chrome",
        ),
        needs=("The Weronika browser window (Chromium), or Edge/Chrome/Firefox for “in chrome”",),
        safety="Read-only browsing. Only public http(s) addresses; your own browser is launched only when you name it.",
    ),
    Skill(
        id="play_video",
        name="Play a video or song",
        summary=(
            "Opens YouTube, searches with the exact words you described, starts the first result it "
            "finds, and skips a pre-roll ad when a skip button appears."
        ),
        platforms=("YouTube",),
        commands=(
            "Play Kesariya on YouTube",
            "Put on lofi study music",
            "Play this video",
        ),
        needs=("The Weronika browser window stays open",),
        safety="Plays what YouTube itself returns for your words; it does not invent a link.",
    ),
    Skill(
        id="post_action",
        name="Comment, like, or subscribe",
        summary=(
            "Types the exact comment you dictate on the page that is already open, then waits for your "
            "confirmation before pressing Submit. Like and Subscribe also wait for that confirmation."
        ),
        platforms=("YouTube", "Instagram", "Facebook", "X", "LinkedIn"),
        commands=(
            "Comment on this video: great explanation",
            "Like this video",
        ),
        needs=("Signed in to the site in the Weronika browser window",),
        safety="The text is typed but never submitted until you reply ‘confirm’. If the text does not match exactly, it stops.",
    ),
    Skill(
        id="watch-status",
        name="Who’s waiting",
        summary="Lists every watched chat, what the other person said and how long it has been waiting.",
        platforms=("WhatsApp", "Telegram"),
        commands=("Who is waiting for a reply?", "Reply watch status"),
        needs=(),
        safety="Read-only.",
    ),
    Skill(
        id="documents",
        name="Read a document and answer",
        summary=(
            "Opens a text, Markdown or JSON file from this device, answers questions about it, "
            "and can reply in the chat with the point it found."
        ),
        platforms=("Local files", "WhatsApp", "Telegram"),
        commands=("Read the file leave-policy.md and tell Boss my leave days",),
        needs=("The file inside ~/.weronika/workspace",),
        safety="Only files inside the Weronika workspace are opened; sending still needs confirmation.",
    ),
    Skill(
        id="codes",
        name="Two-factor codes",
        summary="Watches for a one-time code, shows it to you, and offers to forward it only if you name the chat.",
        platforms=("WhatsApp", "Telegram"),
        commands=("Tell me the code when the bank sends the OTP",),
        needs=("The Weronika browser window stays open on that app",),
        safety="A code is never forwarded to a chat automatically; you name the chat and confirm.",
    ),
)

UNAVAILABLE: tuple[dict[str, str], ...] = (
    {
        "id": "instant-messaging-apis",
        "name": "Reading chats without the browser",
        "why": (
            "WhatsApp has no official personal-account chat API, and Telegram user accounts are "
            "only meant to be automated through the official Bot API. Weronika reads the visible "
            "browser session you sign in to, on this device only."
        ),
    },
    {
        "id": "instagram-read",
        "name": "Reading Instagram DMs",
        "why": (
            "Instagram's web app does not expose a dependable message list, so the worker refuses "
            "to guess there. Sending a prepared draft still works."
        ),
    },
    {
        "id": "calls",
        "name": "Calls",
        "why": "Incoming-call detection, answering, live call audio and call summaries are not implemented.",
    },
    {
        "id": "auto-send",
        "name": "Sending without you",
        "why": "Every send needs your explicit confirmation of the chat and the exact text.",
    },
)


class SkillRegistry:
    """In-memory skill catalog with usage counters and the honest gaps list."""

    def __init__(self) -> None:
        self._usage: dict[str, int] = {}
        self._last_used: dict[str, float] = {}
        self._installed_at = time.time()

    def mark_used(self, skill_id: str) -> None:
        if skill_id not in {skill.id for skill in CATALOG}:
            return
        self._usage[skill_id] = self._usage.get(skill_id, 0) + 1
        self._last_used[skill_id] = time.time()

    def catalog(self) -> dict[str, object]:
        return {
            "installed_at": self._installed_at,
            "skills": [
                {**skill.to_dict(), "used": self._usage.get(skill.id, 0)} for skill in CATALOG
            ],
            "unavailable": [dict(entry) for entry in UNAVAILABLE],
        }
