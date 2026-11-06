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

from .tasks import MAX_TASK_STEPS, Step, clean_query, clean_text

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
OPEN_RESULT_RE = re.compile(
    r"^(?:open|click|view|show)\s+(?:the\s+)?(?:first|top|1st|number one|the top)\s+"
    r"(?:result|link|match|one|hit)\b",
    re.I,
)
PRONOUN_OPEN_RE = re.compile(
    r"^(?:open|click|view)\s+(?:it|this|that|the\s+(?:site|page|link|result|website))\b",
    re.I,
)
READ_PAGE_RE = re.compile(
    r"^(?:read|summari[sz]e|explain)\s+"
    r"(?:this|that|it|the\s+(?:page|article|result|site|website)|the\s+(?:first|top)\s+result)\b",
    re.I,
)
_CLAUSE_SEPARATOR_RE = re.compile(r"\s*(?:,|;|\bthen\b|\bafter that\b|\band\b)\s*", re.I)
_CLAUSE_VERB_START_RE = re.compile(
    r"^(?:please\s+|now\s+)?(?:search|google|look up|look for|browse|find|open|launch|visit|"
    r"go to|play|put on|start playing|comment|write a comment|post a comment|like|subscribe|"
    r"follow|read|summari[sz]e|click|show)\b",
    re.I,
)
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


def _clean_search_target(value: str) -> str:
    """Strip the words people wrap around the thing they actually want searched."""
    text = " ".join(str(value or "").split())
    text = re.sub(
        r"^(?:for|about|on the web|the web|online|this|that)\s+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"^(?:website|site|page|question|statement|topic|thing)\s+(?:called\s+|named\s+)?", "", text, flags=re.I
    )
    text = re.sub(r"^(?:about\s+|for\s+)", "", text, flags=re.I)
    return _strip_suffixes(text).strip(" .,;:!?")


def _split_clauses(text: str) -> list[str]:
    """Split on “and / then / ,” only when a new command verb follows.

    “search for salt and pepper” stays one search, while “search for X and open the
    first result” becomes two commands. That is the difference between an honest
    one-step plan and a plan the user did not ask for.
    """
    parts: list[str] = []
    remaining = text.strip()
    while remaining:
        cut = None
        for match in _CLAUSE_SEPARATOR_RE.finditer(remaining):
            tail = remaining[match.end():]
            if _CLAUSE_VERB_START_RE.match(tail):
                cut = match
                break
        if cut is None:
            parts.append(remaining)
            break
        head = remaining[: cut.start()].strip(" .,;:")
        if head:
            parts.append(head)
        remaining = remaining[cut.end():].strip()
    return [part for part in (p.strip(" .,;:") for p in parts) if part]


_OPEN_TARGET_BLOCK = re.compile(
    r"\b(?:browser|edge|chrome|firefox|brave|opera|tab|window|app|application|settings|folder|file)\b",
    re.I,
)


def _plan_clause(clause: str) -> tuple[list[Step], str, str] | None:
    """Plan one clause. Returns (steps, context, question) or None when unsure."""
    text = " ".join(str(clause or "").split())
    if not text:
        return None
    stripped = _without_leading_site(text)

    comment = COMMENT_RE.search(stripped)
    if comment:
        body = clean_text(comment.group(1))
        if body:
            return [Step("comment", body)], "", ""
        return [Step("read_page")], "", "What exactly should the comment say?"

    if LIKE_RE.search(stripped) and (
        _VIDEO_CONTEXT_RE.search(stripped)
        or re.search(r"\bthis (?:video|post|page)\b", stripped, re.I)
    ):
        action = "like" if re.search(r"\blike\b", stripped, re.I) else "subscribe"
        return [Step(action, "")], "", ""

    play = PLAY_RE.search(stripped)
    if play:
        target = _strip_suffixes(play.group(1))
        target = re.sub(r"^(?:me|the|a|an)\s+", "", target, flags=re.I).strip()
        target = _MEDIA_NOUN_STOP.sub("", target).strip()
        if target and not _looks_like_question(target):
            query = clean_query(target)
            return [Step("play_video", query)], query, ""
        return None

    youtube_search = re.search(r"\b(?:search|find)\s+youtube\s+(?:for\s+)?(.+)$", stripped, re.I)
    if youtube_search:
        query = clean_query(youtube_search.group(1))
        if query:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            return [Step("open_url", url)], query, ""

    search = SEARCH_RE.search(stripped)
    if search:
        query = clean_query(_clean_search_target(search.group(1)))
        if query and not _looks_like_question(query):
            return [Step("search", query)], query, ""

    if OPEN_RESULT_RE.match(stripped) or PRONOUN_OPEN_RE.match(stripped):
        return [Step("open_result")], "", ""

    if READ_PAGE_RE.match(stripped):
        return [Step("read_page")], "", ""

    go_to = re.search(r"\bgo to\s+(.+)$", stripped, re.I)
    if go_to:
        target = _strip_suffixes(go_to.group(1))
        url = _site_url(target)
        if url:
            return [Step("open_url", url)], url, ""

    opened = OPEN_RE.match(stripped)
    if opened:
        target = _strip_suffixes(opened.group(1))
        url = _site_url(target)
        if url:
            return [Step("open_url", url)], url, ""
        if target and _URL_RE.match(target):
            return [Step("open_url", target)], target, ""
        if (
            target
            and len(target.split()) <= 4
            and not _OPEN_TARGET_BLOCK.search(target)
            and not _looks_like_question(target)
        ):
            # “open droid” offline: search for it and let the results page decide,
            # rather than claiming a site was opened.
            query = clean_query(target)
            return [Step("search", query)], query, ""

    if _looks_like_question(stripped):
        query = clean_query(stripped)
        return [Step("search", query)], query, ""
    return None


def plan_local(text: str) -> LocalPlan | None:
    raw = " ".join(str(text or "").split())
    if not raw:
        return None
    body = _without_leading_site(raw)
    clauses = _split_clauses(body) or [body]

    steps: list[Step] = []
    context = ""
    question = ""
    for clause in clauses:
        planned = _plan_clause(clause)
        if planned is None:
            continue
        clause_steps, clause_context, clause_question = planned
        steps.extend(clause_steps)
        context = clause_context or context
        question = question or clause_question

    # “open youtube and play X” should play, not open an empty YouTube first.
    pruned: list[Step] = []
    for index, step in enumerate(steps):
        follows_with_play = index + 1 < len(steps) and steps[index + 1].action == "play_video"
        if step.action == "open_url" and follows_with_play and step.target in _SITE_WORDS.values():
            continue
        pruned.append(step)
    steps = pruned[:MAX_TASK_STEPS]

    if not steps:
        return None
    return LocalPlan(raw, steps, context=context, reply=question)


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
