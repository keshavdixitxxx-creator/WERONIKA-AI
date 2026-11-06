"""Task planning primitives for Weronika's visible-browser automation.

A complex request ("search for X, open the top result, then play Y on YouTube")
is broken into ordered steps. Every step is visible in the orb, and steps that act
on an account — comments, posts, likes, purchases — pause for the user's approval
before anything is typed or submitted.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

MAX_TASK_STEPS = 8
MAX_QUERY_CHARS = 300
MAX_TEXT_CHARS = 2000


class TaskError(RuntimeError):
    """An expected, user-actionable task error."""


@dataclass(frozen=True)
class ActionSpec:
    kind: str
    label: str
    # Acting on the user's own account or posting in public.
    needs_approval: bool
    # Ways this action could be abused or fail loudly; used for the honest notes.
    caution: str = ""


ACTIONS: dict[str, ActionSpec] = {
    "search": ActionSpec(
        "search",
        "search the web",
        False,
        "Opens a search results page in the Weronika browser; it does not silently adopt the answer.",
    ),
    "open_result": ActionSpec(
        "open_result",
        "open a search result",
        False,
        "Only a result link that is visible in the results list is opened.",
    ),
    "open_url": ActionSpec(
        "open_url",
        "open a website",
        False,
        "Only public http(s) addresses are opened.",
    ),
    "play_video": ActionSpec(
        "play_video",
        "play a video or song",
        False,
        "Picks the first result the site itself shows for the exact words you gave.",
    ),
    "read_page": ActionSpec(
        "read_page",
        "read the open page",
        False,
        "Visible text only; the page is never interacted with.",
    ),
    "comment": ActionSpec(
        "comment",
        "post a comment",
        True,
        "The exact comment text is shown for your approval and is submitted only after you confirm.",
    ),
    "reply": ActionSpec(
        "reply",
        "post a reply",
        True,
        "The exact reply text is shown for your approval and submitted only after you confirm.",
    ),
    "like": ActionSpec(
        "like",
        "like a video or post",
        True,
        "Liking is an account action, so it waits for your approval.",
    ),
    "subscribe": ActionSpec(
        "subscribe",
        "subscribe or follow",
        True,
        "Subscribing is an account action, so it waits for your approval.",
    ),
}

_CONTEXT_STOPWORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "it",
    "open",
    "opens",
    "opened",
    "play",
    "playing",
    "video",
    "song",
    "clip",
    "page",
    "site",
    "website",
    "result",
    "results",
    "first",
    "second",
    "third",
    "top",
    "then",
    "and",
    "now",
    "please",
    "on",
    "in",
    "from",
    "for",
    "of",
    "to",
    "search",
    "find",
}
_CONTEXT_PRONOUN_RE = re.compile(
    r"^(?:this|that|it|the (?:same|first|top) (?:one|result|video)|"
    r"(?:this|that|the|same|first|top)\s+(?:video|song|track|clip|page|site|website|result|one|post))$",
    re.I,
)


@dataclass
class Step:
    action: str
    target: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise TaskError(f"Unsupported automation step “{self.action}”.")
        target = " ".join(str(self.target or "").split())
        limit = MAX_QUERY_CHARS if self.action in {"search", "play_video", "open_url"} else MAX_TEXT_CHARS
        if len(target) > limit:
            raise TaskError(f"That step is longer than the {limit}-character limit. Please shorten it.")
        self.target = target

    @property
    def needs_approval(self) -> bool:
        return ACTIONS[self.action].needs_approval

    def to_dict(self) -> dict[str, Any]:
        spec = ACTIONS[self.action]
        return {
            "action": self.action,
            "label": spec.label,
            "target": self.target,
            "note": self.note,
            "needs_approval": spec.needs_approval,
            "caution": spec.caution,
        }


@dataclass(frozen=True)
class PageReading:
    url: str
    title: str
    text: str
    links: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"url": self.url, "title": self.title, "text": self.text}


@dataclass(frozen=True)
class StepOutcome:
    index: int
    action: str
    status: str  # done | awaiting_approval | failed | skipped
    detail: str
    url: str = ""
    page: PageReading | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "index": self.index,
            "action": self.action,
            "status": self.status,
            "detail": self.detail,
            "url": self.url,
        }
        if self.page is not None:
            payload["page"] = self.page.to_dict()
        return payload


@dataclass
class AutomationTask:
    id: str
    message: str
    steps: list[Step]
    created_at: float
    stage: str = "planning"
    cursor: int = 0
    outcomes: list[StepOutcome] = field(default_factory=list)
    context: str = ""
    page: PageReading | None = None
    pending_index: int | None = None
    result: str = ""

    def to_dict(self) -> dict[str, Any]:
        pending = None
        if self.pending_index is not None and 0 <= self.pending_index < len(self.steps):
            step = self.steps[self.pending_index]
            pending = {"index": self.pending_index, **step.to_dict()}
        return {
            "task_id": self.id,
            "message": self.message,
            "stage": self.stage,
            "steps": [step.to_dict() for step in self.steps],
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "pending": pending,
            "context": self.context,
            "result": self.result,
        }


def clean_query(value: str) -> str:
    text = " ".join(str(value or "").split())
    text = re.sub(r"^(?:for|about|on|the|a|an)\s+", "", text, flags=re.I)
    text = text.strip(" \"'“”‘’?.!,;:")
    return text[:MAX_QUERY_CHARS]


def clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip(' "\'“”‘’')[:MAX_TEXT_CHARS]


def search_url(query: str) -> str:
    return f"https://duckduckgo.com/?q={quote_plus(clean_query(query))}&ia=web"


def youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(clean_query(query))}"


def _tokens(value: str) -> list[str]:
    return [
        word
        for word in re.findall(r"\w+", str(value or "").casefold())
        if word not in _CONTEXT_STOPWORDS and len(word) > 1
    ]


def resolve_target(step: Step, context: str) -> str:
    """Turn “this video”, “it”, or “that” into the thing the user just named."""
    if step.action in {"comment", "reply"}:
        return step.target
    if not step.target or _CONTEXT_PRONOUN_RE.match(step.target.strip()):
        return clean_query(context)
    if step.action == "play_video" and len(_tokens(step.target)) == 1 and not context:
        return step.target
    return step.target


def resolve_context(steps: list[Step], requested_context: str = "") -> str:
    """The subject a follow-up step means when it says “it” or “this”."""
    if str(requested_context or "").strip():
        return clean_query(requested_context)
    for step in steps:
        if step.action in {"search", "play_video"} and step.target.strip():
            return clean_query(step.target)
    return ""


def plan_from_payload(payload: dict[str, Any]) -> tuple[list[Step], str]:
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise TaskError("The cloud brain did not return any automation steps. Nothing was run.")
    if len(raw_steps) > MAX_TASK_STEPS:
        raise TaskError(f"That plan has more than {MAX_TASK_STEPS} steps. Please split it into smaller requests.")
    steps: list[Step] = []
    for entry in raw_steps:
        if not isinstance(entry, dict):
            raise TaskError("The cloud brain returned a malformed automation step. Nothing was run.")
        action = str(entry.get("action") or "").strip().casefold()
        steps.append(
            Step(
                action=action,
                target=str(entry.get("target") or ""),
                note=str(entry.get("note") or "")[:300],
            )
        )
    context = resolve_context(steps, str(payload.get("context") or ""))
    return steps, context


def new_task(message: str, steps: list[Step], context: str, now: float) -> AutomationTask:
    return AutomationTask(
        id=uuid.uuid4().hex[:12],
        message=str(message or "")[:MAX_TEXT_CHARS],
        steps=steps,
        created_at=now,
        context=context,
    )
