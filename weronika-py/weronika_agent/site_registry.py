"""Curated website registry with open / close / switch control.

Weronika opens sites in her own visible Chromium window and can list, focus,
close, and operate the tabs she owns. The registry exists for two reasons:

1. People say "open tv garden", not "https://tv.garden/". A name table turns the
   spoken name into the real address.
2. Some requests are for sites whose only purpose is infringement, harassment,
   fraud, or doxxing. Weronika refuses those with a stated reason instead of
   pretending the site does not exist. The refusal is explicit, never silent.

Nothing here bypasses a paywall, a login, a region lock, or a site's terms.
Operating a tab means the same visible, approval-gated actions the rest of the
worker already performs: navigate, search, click, type, read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .tasks import TaskError, clean_query


@dataclass(frozen=True)
class Site:
    """One addressable destination."""

    id: str
    name: str
    url: str
    category: str
    aliases: tuple[str, ...] = ()
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "category": self.category,
            "aliases": list(self.aliases),
            "note": self.note,
        }


SITES: tuple[Site, ...] = (
    # ---------------------------------------------------------------- google
    Site("drive", "Google Drive", "https://drive.google.com/", "google",
         ("gdrive", "google drive", "my drive")),
    Site("docs", "Google Docs", "https://docs.google.com/", "google",
         ("gdocs", "google docs", "document")),
    Site("sheets", "Google Sheets", "https://docs.google.com/spreadsheets/", "google",
         ("gsheets", "google sheets", "spreadsheet")),
    Site("slides", "Google Slides", "https://docs.google.com/presentation/", "google",
         ("google slides", "slides", "presentation")),
    Site("gmail", "Gmail", "https://mail.google.com/", "google",
         ("google mail", "mail")),
    Site("maps", "Google Maps", "https://www.google.com/maps", "google",
         ("google maps", "maps")),
    Site("scholar", "Google Scholar", "https://scholar.google.com/", "google",
         ("scholar", "google scholar")),
    Site("translate", "Google Translate", "https://translate.google.com/", "google",
         ("translate", "google translate")),
    Site("keep", "Google Keep", "https://keep.google.com/", "google",
         ("keep", "google keep", "notes")),
    Site("calendar", "Google Calendar", "https://calendar.google.com/", "google",
         ("calendar", "google calendar", "agenda")),
    Site("photos", "Google Photos", "https://photos.google.com/", "google",
         ("google photos", "photos")),
    Site("meet", "Google Meet", "https://meet.google.com/", "google",
         ("meet", "google meet")),
    Site("classroom", "Google Classroom", "https://classroom.google.com/", "google",
         ("classroom", "google classroom")),
    Site("earth", "Google Earth", "https://earth.google.com/web/", "google",
         ("earth", "google earth")),
    # microsoft
    Site("outlook", "Outlook", "https://outlook.live.com/", "microsoft",
         ("outlook mail", "hotmail", "outlook")),
    Site("onedrive", "OneDrive", "https://onedrive.live.com/", "microsoft",
         ("onedrive", "microsoft drive")),
    Site("office", "Microsoft 365", "https://www.office.com/", "microsoft",
         ("office", "microsoft office", "word online", "excel online", "word", "excel")),
    Site("teams", "Microsoft Teams", "https://teams.microsoft.com/", "microsoft",
         ("teams", "microsoft teams")),
    Site("bing", "Bing", "https://www.bing.com/", "microsoft", ("bing", "bing search")),
    # ------------------------------------------------------------- reference
    Site("wikipedia", "Wikipedia", "https://www.wikipedia.org/", "reference",
         ("wiki", "wikipedia")),
    Site("openlibrary", "Open Library", "https://openlibrary.org/", "reference",
         ("open library", "openlibrary", "book library", "free books")),
    Site("archive", "Internet Archive", "https://archive.org/", "reference",
         ("archive", "internet archive", "wayback", "wayback machine")),
    Site("onelook", "OneLook", "https://www.onelook.com/", "reference",
         ("onelook", "one look", "dictionary")),
    Site("wolfram", "Wolfram Alpha", "https://www.wolframalpha.com/", "reference",
         ("wolfram", "wolfram alpha", "wolframalpha")),
    Site("unpaywall", "Unpaywall", "https://unpaywall.org/", "reference",
         ("unpaywall", "open access papers")),
    Site("semanticscholar", "Semantic Scholar", "https://www.semanticscholar.org/", "reference",
         ("semantic scholar", "papers")),
    Site("haveibeenpwned", "Have I Been Pwned", "https://haveibeenpwned.com/", "reference",
         ("haveibeenpwned", "been pwned", "pwned", "breach check")),
    # learning
    Site("mooc", "MOOC.org", "https://www.mooc.org/", "learning", ("mooc", "mooc org")),
    Site("tryhackme", "TryHackMe", "https://tryhackme.com/", "learning",
         ("try hack me", "tryhackme", "hacking practice")),
    Site("codingame", "CodinGame", "https://www.codingame.com/", "learning",
         ("coding game", "codingame", "code game")),
    Site("elevatorsaga", "Elevator Saga", "https://play.elevatorsaga.com/", "learning",
         ("elevator saga", "elevatorsaga", "elevator game")),
    Site("sqlisland", "SQL Island", "https://sql-island.informatik.uni-kl.de/", "learning",
         ("sql island", "sqlisland", "learn sql")),
    Site("blackbox", "Blackbox AI", "https://www.blackbox.ai/", "learning",
         ("blackbox", "black box ai")),
    Site("napkin", "Napkin AI", "https://www.napkin.ai/", "learning",
         ("napkin", "napkin ai", "diagrams from text")),
    Site("tinkercad", "Tinkercad", "https://www.tinkercad.com/", "learning",
         ("tinkercad", "3d design", "cad")),
    Site("drawcharts", "Draw Charts", "https://www.drawcharts.com/", "learning",
         ("draw charts", "drawcharts", "charts")),
    Site("humanbiodigital", "BioDigital Human", "https://human.biodigital.com/", "learning",
         ("biodigital", "human body", "anatomy")),
    Site("musclewiki", "MuscleWiki", "https://musclewiki.com/", "learning",
         ("muscle wiki", "musclewiki", "workout", "exercise")),
    Site("projecttunnel", "Project Tunnel", "https://projecttunnel.dev/", "learning",
         ("project tunnel", "projecttunnel")),
    Site("hacksplanning", "Hacks Planning", "https://hacksplanning.com/", "learning",
         ("hacks planning", "hacksplanning", "hackathon")),
    # tools
    Site("io10015", "10015.io", "https://10015.io/", "tools",
         ("10015", "one zero zero one five")),
    Site("toolfk", "ToolFK", "https://www.toolfk.com/", "tools", ("toolfk", "tool fk")),
    Site("localconvert", "LocalConvert", "https://localconvert.com/", "tools",
         ("local convert", "localconvert", "convert files")),
    Site("sejda", "Sejda", "https://www.sejda.com/", "tools",
         ("sejda", "pdf editor", "edit pdf")),
    Site("pdfescape", "PDFescape", "https://www.pdfescape.com/", "tools",
         ("pdf escape", "pdfescape", "fill pdf")),
    Site("myfonts", "MyFonts", "https://www.myfonts.com/", "tools",
         ("my fonts", "myfonts", "font finder")),
    Site("alternative", "AlternativeTo", "https://alternativeto.net/", "tools",
         ("alternative to", "alternativeto", "software alternatives")),
    Site("mixkit", "Mixkit", "https://mixkit.co/", "tools",
         ("mixkit", "stock video", "free stock")),
    Site("tunebat", "Tunebat", "https://tunebat.com/", "tools",
         ("tunebat", "song key", "bpm finder")),
    Site("vocalremover", "Vocal Remover", "https://vocalremover.org/", "tools",
         ("vocal remover", "vocalremover", "remove vocals", "karaoke maker")),
    Site("neal", "Neal.fun", "https://neal.fun/", "tools", ("neal fun", "neal.fun", "neal")),
    Site("mapgenie", "Map Genie", "https://mapgenie.io/", "tools",
         ("map genie", "mapgenie", "game maps")),
    Site("poe", "Poe", "https://poe.com/", "tools", ("poe", "poe ai", "poe com")),
    Site("uizard", "Uizard", "https://uizard.io/", "tools",
         ("uizard", "ui design", "mockup")),
    Site("recraft", "Recraft", "https://www.recraft.ai/", "tools",
         ("recraft", "vector images", "svg maker")),
    Site("meshy", "Meshy", "https://www.meshy.ai/", "tools",
         ("meshy", "meshy ai", "3d generator")),
    Site("suno", "Suno", "https://suno.com/", "tools", ("suno", "suno ai", "music maker")),
    Site("radio", "Radio Garden", "https://radio.garden/", "tools",
         ("radio garden", "radiogarden", "world radio")),
    Site("tempmail", "Temp Mail", "https://temp-mail.org/", "tools",
         ("temp mail", "tempmail", "throwaway email")),
    Site("yopmail", "YOPmail", "https://yopmail.com/", "tools",
         ("yop mail", "yopmail", "disposable inbox")),
    # --------------------------------------------------------------- safety
    Site("stopncii", "StopNCII", "https://stopncii.org/", "safety",
         ("stop ncii", "stopncii", "image abuse report"),
         "Report intimate images shared without consent; generates a hash others can match."),
    Site("cybercrime", "India Cyber Crime Portal", "https://cybercrime.gov.in/", "safety",
         ("cyber crime", "cybercrime", "report cyber crime", "file fir"),
         "Official Government of India portal for reporting cyber crime."),
    Site("cibil", "CIBIL", "https://www.cibil.com/", "safety",
         ("cibil", "credit score", "credit report"),
         "Check your own credit report and score."),
    Site("npci", "UPI Help (NPCI)", "https://upi.help.npci.org.in/", "safety",
         ("upi help", "npci", "upi complaint"),
         "Official NPCI help desk for UPI disputes."),
    Site("recoverit", "Recoverit", "https://recoverit.wondershare.com/", "safety",
         ("recoverit", "wondershare recoverit", "recover files"),
         "Local file recovery tool; this opens its product site only."),
    # --------------------------------------------------------- everyday sites
    Site("youtube", "YouTube", "https://www.youtube.com/", "media", ("youtube", "yt")),
    Site("spotify", "Spotify", "https://open.spotify.com/", "media", ("spotify", "music")),
    Site("netflix", "Netflix", "https://www.netflix.com/", "media", ("netflix",)),
    Site("primevideo", "Prime Video", "https://www.primevideo.com/", "media",
         ("prime video", "primevideo", "amazon prime")),
    Site("reddit", "Reddit", "https://www.reddit.com/", "social", ("reddit",)),
    Site("linkedin", "LinkedIn", "https://www.linkedin.com/", "social", ("linkedin",)),
    Site("instagram", "Instagram", "https://www.instagram.com/", "social",
         ("instagram", "insta")),
    Site("facebook", "Facebook", "https://www.facebook.com/", "social", ("facebook", "fb")),
    Site("x", "X", "https://x.com/", "social", ("x", "twitter")),
    Site("quora", "Quora", "https://www.quora.com/", "social", ("quora",)),
    Site("stackoverflow", "Stack Overflow", "https://stackoverflow.com/", "dev",
         ("stack overflow", "stackoverflow")),
    Site("chatgpt", "ChatGPT", "https://chat.openai.com/", "dev",
         ("chatgpt", "chat gpt", "openai chat")),
    Site("claude", "Claude", "https://claude.ai/", "dev", ("claude", "claude ai")),
    Site("github", "GitHub", "https://github.com/", "dev", ("github", "git hub")),
    Site("codewars", "Codewars", "https://www.codewars.com/", "dev",
         ("codewars", "code wars", "kata")),
    Site("leetcode", "LeetCode", "https://leetcode.com/", "dev",
         ("leetcode", "leet code", "dsa practice")),
    Site("npm", "npm", "https://www.npmjs.com/", "dev", ("npm", "npm registry")),
    Site("pypi", "PyPI", "https://pypi.org/", "dev", ("pypi", "pip packages")),
    Site("mdn", "MDN Web Docs", "https://developer.mozilla.org/", "dev",
         ("mdn", "mdn web docs", "web docs")),
    Site("amazon", "Amazon", "https://www.amazon.in/", "shopping",
         ("amazon", "amazon india")),
    Site("flipkart", "Flipkart", "https://www.flipkart.com/", "shopping", ("flipkart",)),
    Site("openstreetmap", "OpenStreetMap", "https://www.openstreetmap.org/", "maps",
         ("openstreetmap", "osm", "osm maps")),
    Site("weather", "Weather", "https://wttr.in/", "reference", ("weather", "forecast")),
    Site("gnews", "Google News", "https://news.google.com/", "news",
         ("news", "google news")),
    Site("bbc", "BBC", "https://www.bbc.com/", "news", ("bbc", "bbc news")),
)

# Domains whose whole purpose is infringement, harassment, fraud, or doxxing.
# Weronika states the reason; she does not silently fail.
REFUSED_DOMAINS: tuple[tuple[str, str], ...] = (
    ("vegamovies", "Piracy: distributes copyrighted films without a licence."),
    ("topmovie", "Piracy: unlicensed film streaming."),
    ("toonstream", "Piracy: unlicensed cartoon streaming."),
    ("cineby", "Piracy: unlicensed film streaming aggregator."),
    ("1flex", "Piracy: unlicensed film streaming."),
    ("1show", "Piracy: unlicensed streaming index."),
    ("tbcpl", "Piracy: unlicensed live sports streaming."),
    ("yarrlist", "Piracy: torrent index."),
    ("famelack", "Piracy: unlicensed film streaming."),
    ("hcinie", "Piracy: unlicensed film streaming."),
    ("playimbd", "Piracy: unlicensed film streaming."),
    ("flimora", "Piracy: unlicensed film streaming."),
    ("filecr", "Software piracy: distributes licensed applications without permission."),
    ("romsfun", "Console ROM distribution without a licence."),
    ("zorcha", "Piracy: unlicensed streaming index."),
    ("multimovie", "Piracy: unlicensed film streaming."),
    ("thepiratebay", "Piracy: torrent index."),
    ("1337x", "Piracy: torrent index."),
    ("callbomber", "Harassment: automated call flooding against a phone number."),
    ("sms24", "Fraud enabler: public numbers used to intercept one-time passcodes."),
    ("bugmenot", "Credential abuse: shares other people's account logins."),
    ("dehashed", "Doxxing: search engine for leaked credentials and personal data."),
    ("intelbase", "Doxxing: personal-data lookup."),
    ("pimeyes", "Doxxing: reverse facial search on people without their consent."),
    ("facecheck", "Doxxing: reverse facial search on people without their consent."),
    ("whatsmyname", "Doxxing: username-to-person correlation across sites."),
    ("inflact", "Harassment: mass Instagram profile lookup and monitoring."),
    ("iplogerr", "Harassment: IP logging on links you send to a target."),
    ("fingerprint", "Tracking: covert device fingerprinting of visitors."),
    ("credit-card-generator", "Fraud: generates card numbers for unauthorised use."),
    ("deepfacelab", "Impersonation: face-swap training on other people."),
    ("faceswap", "Impersonation: face-swap on other people."),
    ("sadtalker", "Impersonation: animates a real person's face from a still photo."),
    ("wav2lip", "Impersonation: lip-syncs a real person to arbitrary audio."),
    ("avatarify", "Impersonation: puppeteers a real person's face in real time."),
    ("voice.ai", "Impersonation: clones a voice from a short sample."),
)

_ALIAS_INDEX: dict[str, Site] = {}
for _site in SITES:
    _ALIAS_INDEX[_site.id.casefold()] = _site
    _ALIAS_INDEX[_site.name.casefold()] = _site
    for _alias in _site.aliases:
        _ALIAS_INDEX.setdefault(_alias.casefold(), _site)

# A leading verb people put in front of a site name.
_LEADING_OPEN_RE = re.compile(
    r"^(?:please\s+)?(?:open|launch|start|visit|go\s+to|show(?:\s+me)?|take\s+me\s+to)\s+",
    re.IGNORECASE,
)
_TRAILING_NOISE_RE = re.compile(
    r"\s+(?:in|with|on|using|via|through)\s+(?:my\s+)?"
    r"(?:browser|edge|chrome|firefox|brave|opera)\s*$",
    re.IGNORECASE,
)
_SITE_SUFFIX_RE = re.compile(r"\s+(?:website|site|page|app|dot\s+com\.?)\s*$", re.IGNORECASE)


def _normalise(value: str) -> str:
    text = " ".join(str(value or "").split())
    text = _LEADING_OPEN_RE.sub("", text)
    text = _TRAILING_NOISE_RE.sub("", text)
    text = _SITE_SUFFIX_RE.sub("", text)
    return text.strip(" .,;:!?")


def refusal_for(value: str) -> str:
    """Return the stated reason if this text targets a refused destination."""
    text = str(value or "").casefold()
    if not text:
        return ""
    for name, reason in REFUSED_DOMAINS:
        if name in text:
            return f"Weronika will not automate {name}. {reason}"
    return ""


def find_site(value: str) -> Site | None:
    """Resolve a spoken site name to a registry entry."""
    key = _normalise(value).casefold()
    if not key:
        return None
    if key in _ALIAS_INDEX:
        return _ALIAS_INDEX[key]
    # "google drive files" -> "google drive"
    for alias, site in _ALIAS_INDEX.items():
        if len(alias) >= 4 and (key.startswith(f"{alias} ") or key.endswith(f" {alias}")):
            return site
    return None


def resolve_target(value: str) -> tuple[str, Site | None]:
    """Turn "radio garden" / "https://x.com" / "example.org" into an openable URL."""
    raw = str(value or "").strip()
    if not raw:
        raise TaskError("Which website should Weronika open?")

    refusal = refusal_for(raw)
    if refusal:
        raise TaskError(refusal)

    site = find_site(raw)
    if site is not None:
        return site.url, site

    candidate = _normalise(raw)
    if re.match(r"^https?://", candidate, re.IGNORECASE):
        return candidate, None
    if re.match(r"^(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?$", candidate, re.IGNORECASE):
        return f"https://{candidate}", None

    host = urlparse(raw).hostname or ""
    if host:
        refusal = refusal_for(host)
        if refusal:
            raise TaskError(refusal)
    raise TaskError(
        f"Weronika does not know “{raw}” as a site. Say the address "
        "(for example example.com) or a name from the site list."
    )


def site_catalog() -> dict[str, Any]:
    """Everything the orb needs to show what can be opened, and what cannot."""
    by_category: dict[str, list[dict[str, Any]]] = {}
    for site in SITES:
        by_category.setdefault(site.category, []).append(site.to_dict())
    return {
        "sites": [site.to_dict() for site in SITES],
        "categories": by_category,
        "count": len(SITES),
        "refused": [{"id": name, "reason": reason} for name, reason in REFUSED_DOMAINS],
    }


def search_sites(query: str, limit: int = 12) -> list[dict[str, Any]]:
    """Fuzzy name search for the orb's site picker."""
    needle = clean_query(query).casefold()
    if not needle:
        return []
    scored: list[tuple[int, Site]] = []
    for site in SITES:
        haystack = " ".join((site.id, site.name, *site.aliases)).casefold()
        if needle in haystack:
            scored.append((0 if haystack.startswith(needle) else 1, site))
    scored.sort(key=lambda pair: (pair[0], pair[1].name))
    return [site.to_dict() for _, site in scored[:limit]]
