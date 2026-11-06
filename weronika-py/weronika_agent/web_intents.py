"""Deterministic, local plans for clear browser commands.

The cloud brain handles free-form requests; this module guarantees that the plain,
predictable phrasings still work when the brain is unreachable or offline. It only
recognises shapes it can honour exactly and otherwise returns nothing, so the brain
keeps control of anything ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from .tasks import Step, clean_query, clean_text

BROWSER_RE = re.compile(r"\b(edge|chrome|firefox|brave|opera)\b", re.I)
LEADING_BROWSER_RE = re.compile(
    r"^(?:please\s+)?(?:open|launch|start|use)\s+(?:the\s+)?(edge|chrome|firefox|brave|opera)\b"
    r"\s*(?:and\s+)?",
    re.I,
)
SYSTEM_RE = re.compile(
    r"\b(?:in|with|using|on|via|through)\s+(?:my\s+)?(?:own\s+)?(?:browser|edge|chrome|firefox|brave|opera)\b"
    r"|\bmy (?:own )?browser\b"
    r"|^(?:please\s+)?(?:open|launch|start|use)\s+(?:the\s+)?(?:edge|chrome|firefox|brave|opera)\b"
    r"|\b(?:with|using|via|through)\s+(?:edge|chrome|firefox)\b",
    re.I,
)
SEARCH_RE = re.compile(
    r"\b(?:search|google|look up|look for|browse|find out)\b(?:\s+(?:for|about|on the web|the web|online))?\s*(.+)$",
    re.I,
)
PLAY_RE = re.compile(
    r"\b(?:play|put on|start playing)\b\s*(.+)$",
    re.I,
)
OPEN_RE = re.compile(r"^(?:please\s+)?(?:open|launch|visit|go to|show)\b\s*(.+)$", re.I)
COMMENT_RE = re.compile(
    r"\b(?:comment|write a comment|post a comment)\b"
    r"(?:\s+(?:on|of|for)\s+(?:this|that|the)?\s*(?:video|post|page|song)?)?"
    r"(?:\s+(?:saying|that|with))?\s*[:\-]?\s*(.*)$",
    re.I,
)
LEADING_SITE_RE = re.compile(
    r"^(?:(?:open|launch|visit|go to)\s+)?(?:youtube|instagram|facebook|x|twitter|reddit|linkedin|spotify)\s+"
    r"(?:and\s+)?",
    re.I,
)
LIKE_RE = re.compile(r"\b(?:like|subscribe to|subscribe|follow)\b", re.I)
QUESTION_RE = re.compile(
    r"^(?:what|when|where|who|why|how|which|is|are|was|were|do|does|did|can|could|should|will|"
    r"kya|kab|kahan|kaun|kyun|kaise)\b",
    re.I,
)
_URL_RE = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/[^\s]*)?", re.I)
_SITE_WORDS = {
    "youtube": "https://www.youtube.com/",
    "spotify": "https://open.spotify.com/",
    "wikipedia": "https://www.wikipedia.org/",
    "github": "https://github.com/",
    "gmail": "https://mail.google.com/",
    "google": "https://www.google.com/",
    "maps": "https://www.google.com/maps",
    "google maps": "https://www.google.com/maps",
    "instagram": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/",
    "telegram": "https://web.telegram.org/",
    "whatsapp": "https://web.whatsapp.com/",
    "x": "https://x.com/",
    "twitter": "https://x.com/",
    "linkedin": "https://www.linkedin.com/",
    "reddit": "https://www.reddit.com/",
    "amazon": "https://www.amazon.in/",
    "flipkart": "https://www.flipkart.com/",
    "netflix": "https://www.netflix.com/",
    "chatgpt": "https://chat.openai.com/",
    "stack overflow": "https://stackoverflow.com/",
    "stackoverflow": "https://stackoverflow.com/",
}
_VIDEO_CONTEXT_RE = re.compile(r"\b(?:video|song|music|clip|track|lyrics|movie|trailer|bhajan|gaana)\b", re.I)
_MEDIA_NOUN_STOP = re.compile(
    r"\b(?:video|song|music|clip|track|lyrics|movie|trailer|bhajan|gaana|on|in|from)\b\s*$", re.I
)


@dataclass(frozen=True)
class LocalPlan:
    message: str
    steps: list[Step]
    context: str = ""
    reply: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "message": self.message,
            "steps": [step.to_dict() for step in self.steps],
            "context": self.context,
        }


def _strip_suffixes(value: str) -> str:
    text = " ".join(str(value or "").split())
    return re.sub(
        r"\s+(?:on|in)\s+(?:youtube|spotify|google|edge|chrome|firefox|my browser)\b.*$", "", text, flags=re.I
    ).strip(" .,;:!?")


def _site_url(name: str) -> str:
    key = " ".join(str(name or "").split()).casefold().strip(" .,;:!?")
    if key in _SITE_WORDS:
        return _SITE_WORDS[key]
    if _URL_RE.match(key):
        return key if key.startswith("http") else f"https://{key}"
    return ""


def _looks_like_question(text: str) -> bool:
    value = str(text or "").strip()
    return value.endswith("?") or bool(QUESTION_RE.match(value))


def _without_leading_site(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    cleaned = LEADING_BROWSER_RE.sub("", cleaned, count=1)
    return LEADING_SITE_RE.sub("", cleaned, count=1)


def plan_local(text: str) -> LocalPlan | None:
    raw = " ".join(str(text or "").split())
    stripped = _without_leading_site(raw)
    if not raw:
        return None
    browser_pref = wants_system_browser(raw)

    comment = COMMENT_RE.search(stripped)
    if comment:
        body = clean_text(comment.group(1))
        steps: list[Step] = []
        if body:
            steps.append(Step("comment", body))
        else:
            steps.append(Step("read_page"))
        return LocalPlan(raw, steps, context="", reply="" if body else "What exactly should the comment say?")

    if LIKE_RE.search(raw) and (_VIDEO_CONTEXT_RE.search(raw) or re.search(r"\bthis (?:video|post|page)\b", raw, re.I)):
        action = "like" if "like" in raw.casefold() else "subscribe"
        return LocalPlan(raw, [Step(action, "")])

    play = PLAY_RE.search(stripped)
    if play:
        target = _strip_suffixes(play.group(1))
        target = re.sub(r"^(?:me|the|a|an)\s+", "", target, flags=re.I).strip()
        target = _MEDIA_NOUN_STOP.sub("", target).strip()
        if target and not _looks_like_question(target):
            return LocalPlan(raw, [Step("play_video", clean_query(target))], context=clean_query(target))

    youtube_search = re.search(r"\b(?:search|find)\s+youtube\s+(?:for\s+)?(.+)$", stripped, re.I)
    if youtube_search:
        query = clean_query(youtube_search.group(1))
        if query:
            return LocalPlan(
                raw,
                [Step("open_url", f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")],
                context=query,
            )

    search = SEARCH_RE.search(stripped)
    if search:
        query = clean_query(_strip_suffixes(search.group(1)))
        if query and not _looks_like_question(query):
            return LocalPlan(raw, [Step("search", query)], context=query)

    go_to = re.search(r"\bgo to\s+(.+)$", stripped, re.I)
    if go_to:
        target = _strip_suffixes(go_to.group(1))
        url = _site_url(target)
        if url:
            return LocalPlan(raw, [Step("open_url", url)], context=url)

    opened = OPEN_RE.match(stripped)
    if opened:
        target = _strip_suffixes(opened.group(1))
        url = _site_url(target)
        if url:
            return LocalPlan(raw, [Step("open_url", url)], context=url)
        if target and _URL_RE.match(target):
            return LocalPlan(raw, [Step("open_url", target)])

    if _looks_like_question(raw):
        return LocalPlan(raw, [Step("search", clean_query(raw))], context=clean_query(raw))
    return None


def _default_target(raw: str) -> str:
    site = re.search(r"\b(youtube|instagram|facebook|x|reddit|linkedin|spotify)\b", raw, re.I)
    if site:
        return _SITE_WORDS.get(site.group(1).casefold(), "")
    return ""


def wants_system_browser(raw: str) -> str:
    """Return the requested browser name when the user asked for their own browser."""
    match = BROWSER_RE.search(str(raw or ""))
    if not match or not SYSTEM_RE.search(str(raw or "")):
        return ""
    return match.group(1)


def url_for_system_open(raw: str) -> str:
    plan = plan_local(raw)
    if plan is None:
        return ""
    for step in plan.steps:
        if step.action == "open_url" and step.target:
            return step.target
    for step in plan.steps:
        if step.action == "search":
            return f"https://duckduckgo.com/?q={step.target.replace(' ', '+')}"
    return ""


def host_of(value: str) -> str:
    try:
        return urlparse(value).hostname or ""
    except ValueError:
        return ""
