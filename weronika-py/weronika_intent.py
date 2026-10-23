"""
Universal intent parser — handles every automation channel via brain.

User wants: "open telegram and make a message to boss that i am on leave today and send him"
→ works for any contact/channel: telegram/whatsapp/instagram/gmail/etc
Also: "open youtube and play barsaat / beliver / techno gamer gta 5 + comment great"
→ spotify when user says "play sahiba" (no platform mentioned) → spotify default for songs
→ youtube for videos
Social: texting someone on any platform

This parser is deterministic regex-first, LLM fallback second (via Ollama/cloud).
It returns normalized actions that weronika_apps + weronika_google can execute.
"""
from __future__ import annotations
import re, json
from typing import Any

# Maps for platform disambiguation
SONG_KEYWORDS = ("song","gaana","track","spotify","audio","music")
VIDEO_KEYWORDS = ("video","youtube","watch","clip","gaming","vlog","trailer")

APP_SYNONYMS = {
    "telegram": ["telegram","tg","टेलीग्राम"],
    "whatsapp": ["whatsapp","wa","whats app","व्हाट्सएप","व्हाट्सऐप्प"],
    "instagram": ["instagram","insta","ig","इंस्टाग्राम"],
    "youtube": ["youtube","yt","यूट्यूब"],
    "spotify": ["spotify","स्पॉटिफ़ाई"],
    "gmail": ["gmail","email","mail","जीमेल","e-mail"],
    "google_calendar": ["calendar","gcal","google calendar","कैलेंडर"],
    "google_drive": ["drive","google drive","ड्राइव"],
    "outlook": ["outlook","hotmail"],
}

def _norm(s: str) -> str:
    return re.sub(r"\s+"," ", (s or "").strip().lower())

def detect_app(text: str) -> str | None:
    low = _norm(text)
    for canonical, syns in APP_SYNONYMS.items():
        for sy in syns:
            if re.search(rf"\b{re.escape(sy)}\b", low):
                return canonical
    return None

def parse_telegram_whatsapp_insta(text: str) -> dict | None:
    """
    Examples:
    - open telegram and make a message to boss that i am on leave today and send him
    - send whatsapp message to mom saying happy birthday
    - DM on instagram to rahul: hey bro
    - telegram read messages from boss / unread / latest
    """
    low = _norm(text)
    app = detect_app(text)
    if app not in ("telegram","whatsapp","instagram"):
        # also handle generic "message to X that ..." without app explicit -> default whatsapp/telegram heuristic later
        if not re.search(r"\b(send|message|dm|tell|write|bhej|भेज)\b", low):
            return None
        # Try to infer from "open telegram"
        if "telegram" in low: app = "telegram"
        elif "whatsapp" in low: app = "whatsapp"
        elif "instagram" in low: app = "instagram"
        else:
            return None

    # Determine intent: read vs send
    # Read signals
    read_re = r"\b(read|check|show|list|get|fetch|unread|latest|recent|inbox|conversation|chat|messages?|padh|देख|दिखा|बताओ)\b"
    send_re = r"\b(send|message|dm|tell|write|post|share|forward|reply|bhej|भेज|मैसेज)\b"

    is_read = bool(re.search(read_re, low) and not re.search(r"\bthat\s+.+\b", low[:120]))  # heuristic
    # stronger read vs send: if "send|message to X that <content>" -> it's send, not read
    if re.search(r"\b(to\s+\w+.+?that\s+.+|saying\s+.+|message\s+.+\s+that\s+.+)\b", low):
        is_read = False
    is_send = bool(re.search(send_re, low))

    # If both, prefer send (more specific)
    if is_send and "that" in low:
        is_read = False

    # Extract target/recipient and content for send
    if is_send or (re.search(r"\bthat\s+.+", low) and app):
        # recipient patterns: "to boss", "to my boss", "to Ankit", "to @username"
        rec = None
        m = re.search(r"(?:\bto\s+|\bfor\s+|\b@)([a-z0-9_.\-\s]{1,40}?)(?:\s+that\s+|\s+saying\s+|\s*:\s*|\s+message\s+|\s+tell\s+|\s+hi\b|\s+hello\b|\s+sending\b|$)", low)
        # also: "message boss that ..." without "to"
        if not m:
            m2 = re.search(r"\bmessage\s+([a-z0-9_.\-]{1,30})\s+that\b", low)
            if m2:
                rec = m2.group(1).strip()
        if m and not rec:
            rec = m.group(1).strip()
        # fallback: "boss" alone
        if not rec or len(rec) < 2 or rec in ("that","him","her","them","it"):
            # try find named entity before "that"
            m3 = re.search(r"\bopen\s+\w+\s+and\s+(?:make\s+)?a?\s*message\s+to\s+(\w+)", low)
            if m3:
                rec = m3.group(1)
            else:
                # generic second word after "to"
                m4 = re.search(r"\bto\s+(\w{2,30})\b", low)
                if m4:
                    rec = m4.group(1)

        # content: after "that", "saying", ":"
        content = None
        for delim in [" that ", " saying ", " : ", " message ", " tell him ", " tell her ", " tell them "]:
            if delim in low:
                idx = low.find(delim)
                # get original case slice
                # use original text case-insensitive slice
                orig_low = low
                # find position in original text approximatively
                content_start = idx + len(delim)
                content = text[content_start:].strip() if content_start < len(text) else low[content_start:].strip()
                # remove trailing "and send him" etc
                content = re.sub(r"\s+and\s+send\s+(him|her|them|it)?\s*$", "", content, flags=re.I)
                content = re.sub(r"\s+and\s+send\s*$", "", content, flags=re.I)
                break
        if not content:
            # fallback: last "that ..." in original
            m5 = re.search(r"that\s+(.+)", text, flags=re.I | re.S)
            if m5:
                content = m5.group(1).strip()

        # Determine confirm/send flag
        send_now = bool(re.search(r"\bsend\b", low))
        # "send him" at end -> send
        # default: prepare draft unless explicit send
        action = "prepare_send"
        target = rec or ""
        # Clean target: first word is likely name
        if target:
            target = target.split()[0].strip("@,:")
        # Infer message language: keep original
        if not content:
            # if no content extracted but we have "open telegram and make a message to boss" incomplete, ask brain
            pass
        return {
            "app": app,
            "action": action,
            "payload": {"app": app, "target": target, "contact": target, "message": content or "", "text": content or text, "send": send_now, "channel": app},
            "send": send_now,
        }

    if is_read:
        # target might be specified: "from boss", "from rahul"
        target = None
        m = re.search(r"\bfrom\s+([a-z0-9_.\-]{1,30})\b", low)
        if m:
            target = m.group(1)
        return {"app": app, "action": "read", "payload": {"app": app, "target": target or "", "contact": target or ""}}

    return None

def parse_youtube(text: str) -> dict | None:
    low = _norm(text)
    if "youtube" not in low and "yt" not in low.split() and "techno gamer" not in low and "gta" not in low:
        # also handle "play the song barsaat" ambiguous - default spotify, not youtube; but if user explicitly says youtube, catch
        has_youtube_verb = re.search(r"\b(play|watch|search|open)\b.*\b(youtube|yt)\b|\b(youtube|yt)\b.*\b(play|search|watch)\b", low)
        if not has_youtube_verb:
            # However "play a video of techno gamer where he was playing gta 5 and make a comment" -> has video + gta, should trigger youtube even without platform word? Use heuristic.
            if not re.search(r"\b(video|watch|comment|channel)\b", low):
                return None
            # if video/comment and not spotify, consider youtube
            if re.search(r"\b(spotify|song|gaana)\b", low):
                return None
            # fallback: if contains video comment, treat as youtube
            if not re.search(r"\b(video|gaming|gta|techno)\b", low):
                return None

    # Determine sub-action: play vs comment vs search
    # Extract query
    # patterns: "play the song X on youtube", "play a video of techno gamer where he was playing gta 5", "play barsaat", "play believer"
    query = None
    comment = None

    # comment extraction: "make a comment there that it is great" -> comment = "it is great"
    cm = re.search(r"\bcomment\b.*?that\s+(.+)", text, flags=re.I | re.S)
    if not cm:
        cm = re.search(r"\bcomment\s*[:\-]?\s*\"?([^\"]{2,200})\"?", text, flags=re.I)
    if cm:
        comment = cm.group(1).strip().strip('"\'')
        # clean trailing "there" etc
        comment = re.sub(r"\b(?:there|on that video|on video)\b\.?$", "", comment, flags=re.I).strip()

    # query extraction
    # "play a video of techno gamer where he was playing gta 5"
    m = re.search(r"play\s+(?:a\s+)?(?:video|song|track)?\s*(?:of\s+)?(.+?)(?:\s+and\s+make\s+a\s+comment|\s+on\s+youtube|\s+on\s+yt\s*$|\s+and\s+comment|$)", low, flags=re.I)
    if m:
        q = m.group(1).strip()
        # strip "the song", "the video"
        q = re.sub(r"^(the\s+)?(song|video|track|music)\s+", "", q, flags=re.I)
        if q and len(q) > 2:
            query = q
    if not query:
        m2 = re.search(r"(?:youtube|yt)\s+(?:play\s+)?(.+?)(?:\s+and\s+make|\s+and\s+comment|$)", low)
        if m2:
            query = m2.group(1).strip()
    if not query:
        # fallback: whole text after "play"
        m3 = re.search(r"\bplay\s+(.+?)(?:\s+and\s+make\s+a\s+comment|\s+and\s+comment|$)", low)
        if m3:
            query = m3.group(1).strip()

    if query:
        # clean youtube suffixes
        query = re.sub(r"\s+on\s+(youtube|yt|spotify)\s*$", "", query, flags=re.I).strip()

    if not query and not comment:
        return None

    # Determine youtube action: if comment present -> play+comment, else play
    app = "youtube"
    if comment and query:
        return {"app": app, "action": "play_and_comment", "payload": {"app": app, "query": query, "comment": comment}}
    if comment and not query:
        return {"app": app, "action": "comment", "payload": {"app": app, "comment": comment, "query": ""}}
    if query:
        return {"app": app, "action": "play", "payload": {"app": app, "query": query}}

    return None

def parse_spotify(text: str) -> dict | None:
    low = _norm(text)
    # user said: "when user only like play the sahiba so it should work on spotify"
    # => generic song play without platform -> default spotify
    # detect: "play <song name>" with or without "on spotify"
    # but exclude youtube explicit cases already handled
    if re.search(r"\b(play|play the|play a|play song|play track| Baja|bajao|chalao)\b", low):
        # if youtube already matched, skip
        # check if youtube explicit in text; if yes, don't treat as spotify
        if "youtube" in low or "youtub" in low:
            return None
        # if video keyword, not spotify
        if re.search(r"\b(video|watch|youtube|trailer|gaming|gta|gameplay)\b", low):
            return None
        # extract song name
        # patterns: "play the sahiba", "play sahiba on spotify", "play barsaat", "play believer", "play a song barsaat"
        m = re.search(r"\bplay\s+(?:the\s+)?(?:song\s+)?(.+?)(?:\s+on\s+spotify\s*$|\s+on\s+youtube.*$|\s*$)", low)
        if m:
            song = m.group(1).strip()
            song = re.sub(r"^(a\s+|the\s+)", "", song, flags=re.I)
            # filter out generic non-song requests like "play the video" already excluded, but "play something" with >1 char
            if song and len(song) >= 2 and len(song.split()) <= 12:
                # ignore if song is "video of techno" -> already excluded, but extra guard
                if "video" in song or "game" in song:
                    return None
                # need to ensure it's a music request, not "play game"
                # allow any short phrase as song
                return {"app": "spotify", "action": "play", "payload": {"app": "spotify", "query": song.strip()}}
        # also pattern "spotify play X"
        m2 = re.search(r"spotify\s+play\s+(.+)", low)
        if m2:
            return {"app": "spotify", "action": "play", "payload": {"app": "spotify", "query": m2.group(1).strip()}}
    return None

def parse_drive_calendar_gmail(text: str) -> dict | None:
    low = _norm(text)
    # drive
    if re.search(r"\b(drive|storage|files?|folder|organize|organise|delete|trash|clean|move|rename)\b", low) and ("drive" in low or "storage" in low or "folder" in low or re.search(r"\borganize\b", low)):
        if "drive" in low or "storage" in low:
            # determine action
            if re.search(r"\borganize|organise|arrange|clean|sort\b", low):
                return {"app": "google_drive", "action": "organize", "payload": {"q": "", "strategy": "by_type", "dry_run": not bool(re.search(r"\b(do it|actually|confirm|yes)\b", low))}}
            if re.search(r"\bdelete|remove|trash|erase\b", low):
                # extract file name
                m = re.search(r"(?:delete|remove|trash)\s+(?:the\s+)?(.+?)(?:\s+from\s+drive|\s*$)", low)
                fn = m.group(1).strip() if m else ""
                return {"app": "google_drive", "action": "delete", "payload": {"q": fn}}
            if re.search(r"\blist|show|what.*in.*drive|my files\b", low):
                return {"app": "google_drive", "action": "list", "payload": {}}
            return {"app": "google_drive", "action": "list", "payload": {}}
    # calendar
    if re.search(r"\b(calendar|agenda|events?|schedule|meeting|plan my day|plan today|what.*today|recognize me|who am i)\b", low):
        if re.search(r"\bplan\s*(my|today|the)?\s*day\b", low) or re.search(r"\bwhat.*(today|schedule)\b", low):
            return {"app": "google_calendar", "action": "plan", "payload": {}}
        if re.search(r"\brecognize|who am i|know me\b", low):
            return {"app": "google_calendar", "action": "recognize", "payload": {}}
        if re.search(r"\bcreate|add|schedule|set\s+up\b", low) and "calendar" in low or "event" in low:
            # extract title/time loosely, delegate to LLM to fill but provide placeholder
            m = re.search(r"(?:create|add)\s+(?:a\s+)?(?:event\s+)?(.+?)(?:\s+on\s+|\s+at\s+|\s*$)", text, flags=re.I)
            title = m.group(1).strip() if m else text
            return {"app": "google_calendar", "action": "create", "payload": {"summary": title, "start_iso": "", "end_iso": ""}}
        if re.search(r"\b(calendar|events|agenda)\b", low):
            return {"app": "google_calendar", "action": "list", "payload": {}}
    # gmail
    if re.search(r"\b(gmail|email|mail|inbox|mails?)\b", low):
        if re.search(r"\bread|check|show|list|unread|latest|summari|priority|who sent\b", low):
            return {"app": "gmail", "action": "list", "payload": {"q": "is:unread" if "unread" in low else ""}}
        if re.search(r"\b(send|write|draft|forward|reply)\b", low):
            m = re.search(r"to\s+([a-z0-9._%+\-@]+)", low)
            to = m.group(1) if m else ""
            return {"app": "gmail", "action": "send", "payload": {"to": to, "subject": "", "body": text}}
        return {"app": "gmail", "action": "list", "payload": {}}
    return None

def parse_generic_open(text: str) -> dict | None:
    low = _norm(text)
    m = re.search(r"\bopen\s+([a-z0-9 ._\-]{2,40})\b", low)
    if m:
        app = m.group(1).strip()
        # map to known
        mapped = detect_app(app)
        if mapped and mapped in ("telegram","whatsapp","instagram","youtube","spotify","gmail","google_calendar","google_drive"):
            return {"app": mapped, "action": "open", "payload": {"app": mapped}}
        # generic app open (pc app)
        return {"app": app, "action": "open_app", "payload": {"app": app}}
    return None

def detect_universal_automation(text: str) -> dict | None:
    """Try in priority order; return first match."""
    if not text or len(text.strip()) < 2:
        return None
    # Highest priority: messaging apps (telegram/whatsapp/instagram) because they need recipient extraction
    for parser in (parse_telegram_whatsapp_insta, parse_youtube, parse_spotify, parse_drive_calendar_gmail, parse_generic_open):
        try:
            res = parser(text)
            if res:
                return res
        except Exception:
            continue
    return None

def classify_with_brain(text: str, brain_complete_fn) -> dict | None:
    """LLM fallback: ask Ollama/cloud to turn free-form into action JSON."""
    prompt = (
        "Turn this user request into a JSON action for Weronika. "
        "Reply with ONE JSON object and nothing else. "
        'If automation: {"app":"telegram|whatsapp|instagram|youtube|spotify|gmail|google_calendar|google_drive", "action":"send|read|play|comment|create|list|organize|delete|open", "payload":{...}} '
        'Payload keys: for messaging {"target":"name","message":"text","send":true}; for youtube {"query":"search term","comment":"text"}; for spotify {"query":"song name"}; for gmail/calendar/drive use intuitive keys. '
        'If not automation, reply {"app":"none"}.\n'
        f"Request: {text}"
    )
    try:
        raw = brain_complete_fn([{"role":"user","content": prompt}])
        start, end = raw.find("{"), raw.rfind("}")
        if start >=0 and end > start:
            data = json.loads(raw[start:end+1])
            if data.get("app") and data["app"] != "none":
                return {"app": data["app"], "action": data.get("action",""), "payload": data.get("payload",{})}
    except Exception:
        pass
    return None
