"""Today's headlines for "tell me the news".

The worker reads the public Google News feed and hands the orb a short list of
headlines to read out. Only the feed's fixed address is ever requested; the topic
the user names travels as a search term in that address and nowhere else.
"""

from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import quote_plus

FEED_ROOT = "https://news.google.com/rss"
MAX_FEED_BYTES = 1_500_000
MAX_HEADLINES = 10
MAX_TOPIC_CHARS = 80
FETCH_TIMEOUT_SECONDS = 8

_ITEM_RE = re.compile(r"<item\b[^>]*>(.*?)</item>", re.IGNORECASE | re.DOTALL)
_LANG_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


class NewsError(RuntimeError):
    """The headlines could not be fetched."""


def _field(block: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    value = match.group(1).strip()
    cdata = re.match(r"^<!\[CDATA\[(.*?)\]\]>$", value, re.DOTALL)
    if cdata:
        value = cdata.group(1)
    value = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(value)))
    return " ".join(value.split())


def parse_feed(text: str, limit: int = MAX_HEADLINES) -> list[dict[str, str]]:
    """Headlines of an RSS document. Anything that is not a headline is ignored."""
    headlines: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _ITEM_RE.finditer(str(text or "")[:MAX_FEED_BYTES]):
        block = match.group(1)
        title = _field(block, "title")
        source = _field(block, "source")
        # Google News writes "Headline - Source"; say the source separately.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()
        title = title[:240]
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        link = _field(block, "link")
        headlines.append(
            {
                "title": title,
                "source": source[:80],
                "published": _field(block, "pubDate")[:40],
                "link": link if link.startswith("https://") else "",
            }
        )
        if len(headlines) >= max(1, min(limit, MAX_HEADLINES)):
            break
    return headlines


def feed_url(topic: str = "", lang: str = "en", country: str = "IN") -> str:
    lang = lang if _LANG_RE.match(lang or "") else "en"
    country = country if _COUNTRY_RE.match(country or "") else "IN"
    base = lang.split("-")[0]
    query = f"hl={lang}&gl={country}&ceid={country}:{base}"
    topic = " ".join(str(topic or "").split())[:MAX_TOPIC_CHARS]
    if topic:
        return f"{FEED_ROOT}/search?q={quote_plus(topic)}&{query}"
    return f"{FEED_ROOT}?{query}"


def _download(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Weronika local worker)", "Accept": "application/rss+xml, text/xml"},
    )
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https host
        return response.read(MAX_FEED_BYTES).decode("utf-8", errors="replace")


def fetch_news(
    topic: str = "",
    lang: str = "en",
    country: str = "IN",
    *,
    limit: int = 6,
    download: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    topic = " ".join(str(topic or "").split())[:MAX_TOPIC_CHARS]
    url = feed_url(topic, lang, country)
    try:
        text = (download or _download)(url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NewsError("Weronika could not reach the news feed. Check the internet connection.") from exc
    headlines = parse_feed(text, limit)
    if not headlines:
        about = f" about “{topic}”" if topic else ""
        raise NewsError(f"The news feed had no headlines{about} just now.")
    return {"topic": topic, "source": "Google News", "headlines": headlines}
