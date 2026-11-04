"""Adapter pool and application services for messaging, reply watch, and skills."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .activity import PlaywrightActivityAdapter
from .models import Platform
from .playwright_adapter import BrowserManager, PlaywrightMessagingAdapter
from .reply_watch import ReplyWatchService
from .watch_skills import SkillRegistry
from .workflow import MessagingService

# The local worker may plan through the same hosted brain the orb uses. When no
# endpoint is configured it stays offline and reply-watch suggestions fall back to
# a small built-in phrase set instead of sending anything to the network.
DEFAULT_BRAIN_ENDPOINT = "https://weronika-ai.lovable.app/api/public/brain"
SUGGESTION_TIMEOUT_SECONDS = 12


class AdapterPool:
    def __init__(self, profile_root: Path | None = None) -> None:
        self.browser = BrowserManager(profile_root)
        self._adapters: dict[Platform, PlaywrightMessagingAdapter] = {}
        self._activity = PlaywrightActivityAdapter(self.browser)

    def __call__(self, platform: Platform) -> PlaywrightMessagingAdapter:
        if platform not in self._adapters:
            self._adapters[platform] = PlaywrightMessagingAdapter(platform, self.browser)
        return self._adapters[platform]

    def activity(self, platform: Platform) -> PlaywrightActivityAdapter:
        return self._activity

    def close(self) -> None:
        self.browser.close()


def create_messaging_service(
    profile_root: Path | None = None,
    *,
    brain_endpoint: str | None = None,
    suggestion: Callable[[str, str], str] | None = None,
) -> tuple[MessagingService, AdapterPool, ReplyWatchService, SkillRegistry]:
    adapters = AdapterPool(profile_root)
    messaging = MessagingService(adapters)
    suggester = suggestion or build_brain_suggester(
        brain_endpoint if brain_endpoint is not None else default_brain_endpoint()
    )
    watch = ReplyWatchService(adapters.activity, messaging, suggester=suggester)
    skills = SkillRegistry()
    return messaging, adapters, watch, skills


def default_brain_endpoint() -> str:
    """Resolve the brain URL without exposing anything to browser code."""
    configured = os.environ.get("WERONIKA_BRAIN_ENDPOINT")
    if configured is None:
        return DEFAULT_BRAIN_ENDPOINT
    cleaned = configured.strip()
    return "" if cleaned.casefold() in {"", "off", "none", "local"} else cleaned


def build_brain_suggester(endpoint: str) -> Callable[[str, str], str]:
    def suggest(chat_name: str, message_text: str) -> str:
        if not endpoint:
            return ""
        question = (
            "Write the short, natural reply I should send in this chat.\n"
            f"Chat: {chat_name}\n"
            f"Their message: {message_text}\n"
            "Reply in the same language they used. Reply with the message text only."
        )
        payload = json.dumps(
            {"message": question, "history": [], "lang": "", "addressName": "Commander"}
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=SUGGESTION_TIMEOUT_SECONDS) as response:
                raw = response.read(200_000).decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            return ""
        except Exception:
            return ""
        text = _sse_text(raw)
        return " ".join(text.split())[:2000]

    return suggest


def _sse_text(raw: str) -> str:
    """The hosted brain answers with SSE text deltas; tolerate plain JSON too."""
    if not raw:
        return ""
    if not raw.lstrip().startswith("data:"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw.strip()
        if isinstance(data, dict):
            for key in ("text", "reply", "message", "content"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
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
    return "".join(pieces).strip()
