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
            "not replied, Weronika tells you and asks whether she should reply or you will."
        ),
        platforms=("WhatsApp", "Telegram"),
        commands=(
            "Watch my WhatsApp chat with Boss",
            "Keep an eye on Telegram chat with Rahul, ask me if I don’t reply in 10 minutes",
        ),
        needs=("The Weronika browser window stays open on that app",),
        safety="No message is typed or sent until you give the exact reply and confirm it, or tell her ‘you reply’ for that one message.",
    ),
    Skill(
        id="reply-watch-delegate",
        name="Watch · Weronika replies",
        summary=(
            "When a watched message is waiting, answer ‘you reply’. Weronika reads the chat again, "
            "writes a short reply in your voice, opens the chat, sends it and shows you the exact text."
        ),
        platforms=("WhatsApp", "Telegram"),
        commands=("You reply", "Weronika, you answer it", "I’ll reply"),
        needs=(
            "The Weronika browser window stays open on that app",
            "The cloud brain, which writes the reply and confirms that it wrote it in your name",
        ),
        safety=(
            "Your answer covers that one message only. Nothing is sent when you answered meanwhile, "
            "when no wording could be written, or when several chats match the name. Wording from "
            "an older cloud brain, which cannot confirm it wrote a message in your name, is shown "
            "to you first and waits for ‘confirm send’."
        ),
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
        id="open-apps",
        name="Open apps and sites",
        summary=(
            "Opens desktop apps and sites by name straight from this computer, without asking the "
            "cloud brain: system tools, anything in your Start menu, and the sites of the site list."
        ),
        platforms=("Windows", "macOS", "Linux"),
        commands=(
            "Open Notepad",
            "Open Chrome and the calculator",
            "Open the calendar app",
            "Play Tum Hi Ho on Spotify",
        ),
        needs=("The local worker running (start.bat)",),
        safety=(
            "A name can only pick a fixed system tool, an app already in your Start menu, or a listed "
            "site. Your words are never run as a command, and an unknown name opens nothing."
        ),
    ),
    Skill(
        id="news",
        name="Headlines",
        summary="Fetches today’s headlines, or headlines about a topic you name, and reads them out.",
        platforms=("Google News",),
        commands=("Tell me the news", "News about cricket"),
        needs=("An internet connection",),
        safety="Read-only. Only the public news feed is requested.",
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
        id="call-watch-ask",
        name="Calls · ask me first",
        summary=(
            "Watches for an incoming call every couple of seconds. When one rings she tells you who "
            "it is and asks “Are you able to handle the call, or should I take it?” — for every call, "
            "never from a remembered preference."
        ),
        platforms=("Phone (SIM over cable)", "WhatsApp"),
        commands=(
            "Handle my calls",
            "Scan calls",
            "Is anyone calling?",
        ),
        needs=(
            "The local worker running (start.bat)",
            "For a SIM call: the phone on a cable with USB debugging allowed, and adb installed",
            "For a WhatsApp call: the Weronika browser window signed in to WhatsApp",
        ),
        safety=(
            "She only watches and asks. Nothing is answered, declined or said until you answer her "
            "question for that one call."
        ),
    ),
    Skill(
        id="call-handle",
        name="Calls · Weronika takes it",
        summary=(
            "Answer ‘you handle it’ and Weronika picks up, tells the caller she is your AI assistant "
            "and that you cannot come to the phone, listens, takes the message in her own words, and "
            "hangs up. Answer ‘I’ll take it’ and she leaves the phone completely alone."
        ),
        platforms=("Phone (SIM over cable)", "WhatsApp"),
        commands=(
            "You handle it",
            "I’ll take it",
            "Ignore it",
            "He said the papers are ready",
            "Kaat do",
        ),
        needs=(
            "Call audio support for hearing and speaking (setup-calls.bat) — without it she runs the "
            "same call in typed mode and says so",
            "The cloud brain for her wording; she falls back to local wording and flags the line",
        ),
        safety=(
            "The caller is always told they are speaking with an AI. A one-time code, password, card "
            "number or UPI handle is never repeated, stored or read out. She takes messages; she never "
            "agrees, pays, promises or confirms anything on your behalf. Call audio is never written "
            "to disk."
        ),
    ),
    Skill(
        id="call-setup",
        name="Calls · what is connected",
        summary=(
            "Scans the cable and the audio devices and reports honestly what this computer can do: "
            "which phone is linked, whether its SIM calls can be handled, and which sound route is live."
        ),
        platforms=("Phone (SIM over cable)", "WhatsApp"),
        commands=(
            "Which phone is connected?",
            "Check my call setup",
            "What audio route for calls?",
            "Handle my calls on bluetooth",
        ),
        needs=("adb for an Android phone; nothing at all for the WhatsApp route",),
        safety=(
            "Read-only. An iPhone is reported as connected but unable to have its SIM calls handled, "
            "because iOS exposes no telephony over a cable — she says that instead of pretending."
        ),
    ),
    Skill(
        id="call-example",
        name="Calls · run an example",
        summary=(
            "Runs one scripted example call end to end so you can see the whole behaviour — the "
            "question, the disclosure, a message taken, a code refused, the hang-up and the summary — "
            "without a phone, a browser session or a microphone."
        ),
        platforms=("Example only",),
        commands=(
            "Show me an example call",
            "Give me an example of a WhatsApp call",
            "Simulate a call",
        ),
        needs=(),
        safety="Nothing is dialled, answered or recorded. The report says so in its first line.",
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
        "id": "telegram-calls",
        "name": "Telegram calls",
        "why": (
            "Telegram calling is not possible on any surface Weronika can reach: Telegram Web has no "
            "calling feature, and the Bot API cannot make or receive calls. Telegram stays text-only, "
            "so a Telegram call is neither detected nor answered. Phone (SIM) and WhatsApp calls are."
        ),
    },
    {
        "id": "outgoing-calls",
        "name": "Placing a call",
        "why": (
            "Weronika answers incoming calls after asking you about each one; she does not dial out. "
            "Placing a call in someone’s name is a commitment she should not make on her own, so the "
            "worker has no dialler. She can prepare a message asking you to call back instead."
        ),
    },
    {
        "id": "iphone-sim-calls",
        "name": "SIM calls on an iPhone",
        "why": (
            "iOS exposes no equivalent of adb for telephony, so a laptop cannot see a ringing cellular "
            "call on an iPhone, answer it, or hear it through the cable. An iPhone owner gets WhatsApp "
            "call handling in the signed-in browser window, and Weronika says so in the setup panel "
            "rather than showing a button that silently does nothing."
        ),
    },
    {
        "id": "smart-home",
        "name": "Home devices (AC, lights, TV)",
        "why": (
            "There is no smart-home connection yet, so nothing is switched. A device that listens "
            "only to an infrared remote also needs a Wi-Fi infrared blaster in the room before any "
            "program can reach it."
        ),
    },
    {
        "id": "hotmail-read",
        "name": "Reading Hotmail / Outlook.com",
        "why": (
            "Weronika writes a mail and opens it in a Hotmail compose window for you to send. "
            "She does not read that inbox: no Microsoft sign-in is built into this app."
        ),
    },
    {
        "id": "auto-send",
        "name": "Sending without you",
        "why": (
            "Weronika never sends on her own. A message goes out only after you confirm the exact "
            "text, or after you answer ‘you reply’ for that one waiting message."
        ),
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
