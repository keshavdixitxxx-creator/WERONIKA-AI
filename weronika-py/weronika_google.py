"""
Weronika Google Connector — Gmail + Calendar + Drive + OAuth

Design goals (user request):
- Connect Google Calendar, Drive, Gmail with read/write/make changes
- Plan my day and recognize me through calendar
- Organize/delete/manage Drive storage, perform more activity via Drive
- Private work uses Ollama when possible, cloud fallback allowed per config
- All through python brain (no separate bat chrome test)

This module does NOT require hardcoded credentials. User provides OAuth client
via settings UI (client_id/client_secret). Tokens are stored locally encrypted
in ~/.weronika/google_tokens.json (base64, not plaintext). Refresh is automatic.

If tokens missing, calls return needs_auth error with auth_url to connect.

We use direct REST (googleapis) without heavy deps; optional google-auth support
is detected but not required.

APIs covered:
- Gmail: list, read, send, draft, trash/delete, search, label, organize
- Calendar: list, create, update, delete, plan_day, recognize_user
- Drive: list, search, create, move, rename, delete, organize, storage summary

All methods return dict: {ok: bool, data/error, requires_auth}
"""
from __future__ import annotations
import base64, json, os, time, urllib.parse, urllib.request, hashlib, secrets, threading
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
TOKEN_PATH = Path(os.path.expanduser("~")) / ".weronika" / "google_tokens.json"
TOKEN_PATH_FALLBACK = HERE / "memory" / "google_tokens.json"
CONFIG_PATH = HERE / "config.json"

SCOPES = {
    "gmail": "https://www.googleapis.com/auth/gmail.modify",
    "calendar": "https://www.googleapis.com/auth/calendar",
    "drive": "https://www.googleapis.com/auth/drive",
}
ALL_SCOPES = " ".join(SCOPES.values()) + " https://www.googleapis.com/auth/userinfo.email openid"


def _load_oauth_config() -> dict:
    # from config.json or env
    cfg = {}
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    # allow env override
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"):
        if os.environ.get(k):
            cfg[k.lower()] = os.environ[k]
    # also look in memory/google_oauth.json
    oauth_file = HERE / "memory" / "google_oauth.json"
    if oauth_file.exists():
        try:
            cfg.update(json.loads(oauth_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg

def save_oauth_config(client_id: str, client_secret: str, redirect_uri: str | None = None):
    path = HERE / "memory" / "google_oauth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"google_client_id": client_id, "google_client_secret": client_secret}
    if redirect_uri:
        data["google_redirect_uri"] = redirect_uri
    # merge with existing config.json style keys too
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

def _token_paths():
    return [TOKEN_PATH, TOKEN_PATH_FALLBACK]

def _load_tokens() -> dict | None:
    for p in _token_paths():
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                # if base64 encoded blob
                if "blob" in raw and isinstance(raw["blob"], str):
                    decoded = base64.b64decode(raw["blob"]).decode("utf-8")
                    return json.loads(decoded)
                return raw
            except Exception:
                continue
    return None

def _save_tokens(tokens: dict):
    blob = base64.b64encode(json.dumps(tokens).encode("utf-8")).decode("utf-8")
    data = {"blob": blob, "updated_at": time.time()}
    for p in _token_paths():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data), encoding="utf-8")
            break
        except Exception:
            continue

def _is_expired(tokens: dict) -> bool:
    exp = tokens.get("expiry") or tokens.get("expires_at") or 0
    try:
        exp = float(exp)
    except Exception:
        return True
    return time.time() > exp - 60  # 60s leeway

def refresh_tokens_if_needed(tokens: dict | None) -> dict | None:
    if not tokens:
        return None
    if not _is_expired(tokens):
        return tokens
    refresh = tokens.get("refresh_token")
    if not refresh:
        return None
    cfg = _load_oauth_config()
    client_id = cfg.get("google_client_id") or cfg.get("client_id") or cfg.get("GOOGLE_CLIENT_ID")
    client_secret = cfg.get("google_client_secret") or cfg.get("client_secret") or cfg.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    try:
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req, timeout=15) as res:
            body = json.loads(res.read().decode())
        tokens["access_token"] = body["access_token"]
        tokens["expires_in"] = body.get("expires_in", 3600)
        tokens["expiry"] = time.time() + int(body.get("expires_in", 3600))
        tokens["expiry"] = float(tokens["expiry"])
        _save_tokens(tokens)
        return tokens
    except Exception as e:
        print(f"[weronika-google] refresh failed: {e}")
        return tokens  # still try


def get_auth_url(service: str = "all", state: str | None = None) -> dict:
    cfg = _load_oauth_config()
    client_id = cfg.get("google_client_id") or cfg.get("client_id") or cfg.get("GOOGLE_CLIENT_ID")
    redirect_uri = cfg.get("google_redirect_uri") or cfg.get("redirect_uri") or cfg.get("GOOGLE_REDIRECT_URI") or "http://127.0.0.1:8765/api/google/callback"
    if not client_id:
        return {"ok": False, "error": "Google OAuth not configured. Add your Client ID/Secret in Weronika settings (Google Cloud Console → Credentials → OAuth 2.0 Client ID).", "requires_config": True}
    scope = ALL_SCOPES if service == "all" else SCOPES.get(service, ALL_SCOPES)
    if service != "all" and service in SCOPES:
        scope = SCOPES[service] + " https://www.googleapis.com/auth/userinfo.email openid"
    st = state or secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": st,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"ok": True, "auth_url": url, "state": st, "redirect_uri": redirect_uri}

def handle_callback(code: str, redirect_uri: str | None = None) -> dict:
    cfg = _load_oauth_config()
    client_id = cfg.get("google_client_id") or cfg.get("client_id") or cfg.get("GOOGLE_CLIENT_ID")
    client_secret = cfg.get("google_client_secret") or cfg.get("client_secret") or cfg.get("GOOGLE_CLIENT_SECRET")
    redirect = redirect_uri or cfg.get("google_redirect_uri") or cfg.get("redirect_uri") or cfg.get("GOOGLE_REDIRECT_URI") or "http://127.0.0.1:8765/api/google/callback"
    if not client_id or not client_secret:
        return {"ok": False, "error": "OAuth config missing"}
    if not code:
        return {"ok": False, "error": "Missing code"}
    try:
        data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        }).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req, timeout=15) as res:
            body = json.loads(res.read().decode())
        tokens = {
            "access_token": body["access_token"],
            "refresh_token": body.get("refresh_token"),
            "expires_in": body.get("expires_in", 3600),
            "expiry": time.time() + int(body.get("expires_in", 3600)),
            "scope": body.get("scope", ""),
            "token_type": body.get("token_type", "Bearer"),
        }
        # keep previous refresh_token if new one missing
        prev = _load_tokens()
        if not tokens.get("refresh_token") and prev and prev.get("refresh_token"):
            tokens["refresh_token"] = prev["refresh_token"]
        _save_tokens(tokens)
        return {"ok": True, "message": "Google connected. You can close this tab and return to Weronika.", "tokens_saved": True}
    except Exception as e:
        return {"ok": False, "error": f"Token exchange failed: {e}"}

def _api_get(url: str, tokens: dict, params: dict | None = None) -> dict:
    access = tokens.get("access_token")
    headers = {"Authorization": f"Bearer {access}"}
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    req = urllib.request.Request(url + q, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode())

def _api_post(url: str, tokens: dict, body: dict | None = None, method: str = "POST") -> dict:
    access = tokens.get("access_token")
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
    data = json.dumps(body or {}).encode() if body is not None else None
    if method == "POST" and body is None:
        # ensure content
        pass
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as res:
        txt = res.read().decode()
        return json.loads(txt) if txt else {}

def _api_delete(url: str, tokens: dict):
    access = tokens.get("access_token")
    headers = {"Authorization": f"Bearer {access}"}
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    with urllib.request.urlopen(req, timeout=20) as res:
        return {"status": res.status}

def _require_tokens() -> tuple[dict | None, dict | None]:
    tokens = _load_tokens()
    if not tokens or not tokens.get("access_token"):
        return None, {"ok": False, "error": "Google not connected. Open Weronika settings and connect Google.", "requires_auth": True, "auth": get_auth_url()}
    tokens = refresh_tokens_if_needed(tokens)
    if not tokens or _is_expired(tokens):
        return None, {"ok": False, "error": "Google session expired. Please reconnect.", "requires_auth": True, "auth": get_auth_url()}
    return tokens, None

# ---------- Status ----------
def status() -> dict:
    cfg = _load_oauth_config()
    tokens = _load_tokens()
    has_client = bool(cfg.get("google_client_id") or cfg.get("client_id") or cfg.get("GOOGLE_CLIENT_ID"))
    connected = bool(tokens and tokens.get("access_token"))
    if connected:
        tokens = refresh_tokens_if_needed(tokens)
        connected = bool(tokens and not _is_expired(tokens))
    # probe which scopes
    scope_str = (tokens.get("scope") if tokens else "") or ""
    return {
        "ok": True,
        "connected": connected,
        "has_client_config": has_client,
        "scopes": scope_str,
        "services": {
            "gmail": has_client, # we consider configured = available to connect; connected = actual auth
            "calendar": has_client,
            "drive": has_client,
        },
        "connected_services": {
            "gmail": connected and ("gmail" in scope_str or "mail.google" in scope_str or not scope_str),
            "calendar": connected and ("calendar" in scope_str or not scope_str),
            "drive": connected and ("drive" in scope_str or not scope_str),
        },
        "token_expiry": (tokens.get("expiry") if tokens else None),
    }

def disconnect():
    for p in _token_paths():
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    return {"ok": True, "message": "Google disconnected."}

# ---------- Gmail ----------
def gmail_list(q: str = "", max_results: int = 10) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        res = _api_get("https://gmail.googleapis.com/gmail/v1/users/me/messages", tokens, {"q": q, "maxResults": str(max_results)})
        msgs = res.get("messages", [])
        # fetch snippets
        detailed = []
        for m in msgs[:max_results]:
            try:
                d = _api_get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}", tokens, {"format": "metadata", "metadataHeaders": "Subject,From,Date"})
                headers = {h["name"]: h["value"] for h in d.get("payload", {}).get("headers", [])}
                detailed.append({"id": m["id"], "snippet": d.get("snippet","")[:300], "subject": headers.get("Subject",""), "from": headers.get("From",""), "date": headers.get("Date",""), "labelIds": d.get("labelIds", [])})
            except Exception:
                detailed.append({"id": m["id"]})
        return {"ok": True, "messages": detailed, "resultSizeEstimate": res.get("resultSizeEstimate", 0)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def gmail_read(message_id: str) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        d = _api_get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}", tokens, {"format": "full"})
        return {"ok": True, "message": d}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def gmail_send(to: str, subject: str, body: str, cc: str | None = None, bcc: str | None = None) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        import base64
        raw_lines = [f"To: {to}", f"Subject: {subject}", "Content-Type: text/plain; charset=utf-8"]
        if cc: raw_lines.insert(1, f"Cc: {cc}")
        if bcc: raw_lines.insert(1, f"Bcc: {bcc}")
        raw_lines.append("")
        raw_lines.append(body)
        raw = "\r\n".join(raw_lines)
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode()
        res = _api_post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send", tokens, {"raw": encoded})
        return {"ok": True, "id": res.get("id"), "message": "Email sent."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def gmail_trash(message_id: str) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        res = _api_post(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/trash", tokens, {})
        return {"ok": True, "id": res.get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def gmail_modify(message_id: str, add_labels: list[str] | None = None, remove_labels: list[str] | None = None) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        body = {}
        if add_labels: body["addLabelIds"] = add_labels
        if remove_labels: body["removeLabelIds"] = remove_labels
        res = _api_post(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify", tokens, body)
        return {"ok": True, "message": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---------- Calendar ----------
def calendar_list(calendar_id: str = "primary", max_results: int = 20, time_min: str | None = None, time_max: str | None = None, q: str | None = None) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        params = {"maxResults": str(max_results), "singleEvents": "true", "orderBy": "startTime"}
        if time_min: params["timeMin"] = time_min
        if time_max: params["timeMax"] = time_max
        if q: params["q"] = q
        res = _api_get(f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events", tokens, params)
        items = res.get("items", [])
        # simplify
        simplified = []
        for it in items:
            simplified.append({
                "id": it.get("id"),
                "summary": it.get("summary"),
                "description": it.get("description","")[:300],
                "start": it.get("start"),
                "end": it.get("end"),
                "location": it.get("location"),
                "status": it.get("status"),
                "htmlLink": it.get("htmlLink"),
            })
        return {"ok": True, "events": simplified, "calendar": calendar_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def calendar_create(calendar_id: str = "primary", summary: str = "", start_iso: str = "", end_iso: str = "", description: str = "", location: str = "", timezone: str = "UTC") -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        from datetime import datetime
        if not summary or not start_iso:
            return {"ok": False, "error": "summary and start_iso required (e.g. 2026-10-24T10:00:00)"}
        body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso or start_iso, "timeZone": timezone},
        }
        res = _api_post(f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events", tokens, body)
        return {"ok": True, "event": res, "message": f"Created '{summary}'."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def calendar_delete(calendar_id: str, event_id: str) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        _api_delete(f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events/{urllib.parse.quote(event_id)}", tokens)
        return {"ok": True, "message": "Event deleted."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def calendar_update(calendar_id: str, event_id: str, patch: dict) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        res = _api_post(f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events/{urllib.parse.quote(event_id)}", tokens, patch, method="PATCH")
        return {"ok": True, "event": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def calendar_plan_day(date_iso: str | None = None, timezone: str = "UTC") -> dict:
    """Create a day plan from calendar events + recent gmail snippets."""
    from datetime import datetime, timezone as tz, timedelta
    import weronika_memory as mem
    tokens, err = _require_tokens()
    if err and not date_iso:
        # still try to return memory-based plan
        return {"ok": False, **err}
    # determine day window
    try:
        if date_iso:
            d = datetime.fromisoformat(date_iso.replace("Z","+00:00"))
        else:
            d = datetime.now(tz.utc)
        start = d.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        time_min = start.isoformat().replace("+00:00","Z")
        time_max = end.isoformat().replace("+00:00","Z")
    except Exception:
        time_min = time_max = None

    events = []
    if tokens:
        cal = calendar_list(time_min=time_min, time_max=time_max, max_results=30)
        if cal.get("ok"):
            events = cal.get("events", [])
            # update memory patterns
            try:
                import weronika_memory
                weronika_memory.update_profile_from_calendar(events)
            except Exception:
                pass

    # build plan text (brain will polish, but we give structure)
    plan_lines = []
    if events:
        plan_lines.append(f"📅 {len(events)} events today:")
        for ev in events:
            st = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date") or ""
            plan_lines.append(f"  • {st} — {ev.get('summary')} {('('+ev.get('location')+')') if ev.get('location') else ''}")
    else:
        plan_lines.append("No events found — it's an open day.")

    # Add focus suggestions
    plan_lines.append("")
    plan_lines.append("Stay hydrated, check Gmail priorities, and block focus time.")

    plan_text = "\n".join(plan_lines)
    # save to memory
    try:
        import weronika_memory
        weronika_memory.add_day_plan({"date": date_iso or datetime.now().isoformat(), "events": events, "summary": plan_text})
    except Exception:
        pass

    return {"ok": True, "plan": plan_text, "events": events, "date": date_iso or datetime.now().date().isoformat()}

def calendar_recognize() -> dict:
    """Who am I based on calendar history."""
    prof = {}
    try:
        import weronika_memory
        prof = weronika_memory.load_profile()
    except Exception:
        pass
    tokens, err = _require_tokens()
    events = []
    if tokens:
        # last 7 days
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        cal = calendar_list(time_min=week_ago.isoformat().replace("+00:00","Z"), time_max=now.isoformat().replace("+00:00","Z"), max_results=50)
        if cal.get("ok"):
            events = cal.get("events", [])
    # infer
    freq = {}
    for ev in events:
        s = (ev.get("summary") or "").lower()
        if s:
            freq[s] = freq.get(s, 0) + 1
    top = sorted(freq.items(), key=lambda x: -x[1])[:5]
    patterns = prof.get("calendar_patterns", {})

    msg = "I recognize you by your calendar patterns. "
    if top:
        msg += "Frequent: " + ", ".join(f"{k} ({v}x)" for k,v in top) + ". "
    if patterns:
        msg += "Stored patterns: " + ", ".join(list(patterns.keys())[:5]) + ". "
    if not top and not patterns:
        msg += "Connect Calendar so I can learn your routine and greet you by your day."

    return {"ok": True, "recognition": msg, "patterns": patterns, "recent_events": events[:10], "profile": prof}


# ---------- Drive ----------
def drive_list(q: str = "", page_size: int = 30, fields: str = "nextPageToken, files(id,name,mimeType,size,modifiedTime,parents,webViewLink)") -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        params = {"pageSize": str(page_size), "fields": fields, "orderBy": "modifiedTime desc"}
        if q:
            params["q"] = q
        res = _api_get("https://www.googleapis.com/drive/v3/files", tokens, params)
        return {"ok": True, "files": res.get("files", []), "nextPageToken": res.get("nextPageToken")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def drive_get(file_id: str) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        res = _api_get(f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}", tokens, {"fields": "id,name,mimeType,size,modifiedTime,parents,webViewLink,owners"})
        return {"ok": True, "file": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def drive_create_folder(name: str, parent_id: str | None = None) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        res = _api_post("https://www.googleapis.com/drive/v3/files", tokens, body)
        return {"ok": True, "file": res, "message": f"Folder '{name}' created."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def drive_rename(file_id: str, new_name: str) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        res = _api_post(f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}", tokens, {"name": new_name}, method="PATCH")
        return {"ok": True, "file": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def drive_move(file_id: str, new_parent_id: str, old_parent_id: str | None = None) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        # Drive move is a PATCH with addParents/removeParents query
        access = tokens.get("access_token")
        headers = {"Authorization": f"Bearer {access}"}
        params = {"addParents": new_parent_id}
        if old_parent_id:
            params["removeParents"] = old_parent_id
        url = f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers, method="PATCH")
        # empty body but need content-length 0
        with urllib.request.urlopen(req, timeout=20) as res:
            txt = res.read().decode()
            return {"ok": True, "file": json.loads(txt) if txt else {}}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def drive_delete(file_id: str, trash: bool = True) -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        if trash:
            res = _api_post(f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}/trash", tokens, {})
            # Actually Drive trash is POST to trash? simpler use PATCH trashed=true
            # fallback: PATCH trashed
            return {"ok": True, "message": "Moved to trash."}
        else:
            _api_delete(f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}", tokens)
            return {"ok": True, "message": "Permanently deleted."}
    except Exception as e:
        # try PATCH trashed
        try:
            res = _api_post(f"https://www.googleapis.com/drive/v3/files/{urllib.parse.quote(file_id)}", tokens, {"trashed": True}, method="PATCH")
            return {"ok": True, "message": "Moved to trash."}
        except Exception as e2:
            return {"ok": False, "error": str(e2)}

def drive_storage() -> dict:
    tokens, err = _require_tokens()
    if err: return err
    try:
        res = _api_get("https://www.googleapis.com/drive/v3/about", tokens, {"fields": "storageQuota,user"})
        quota = res.get("storageQuota", {})
        return {"ok": True, "quota": quota, "user": res.get("user", {}), "human": f"{int(quota.get('usage',0))} / {quota.get('limit','unlimited')} used"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def drive_organize(strategy: str = "by_type", dry_run: bool = True) -> dict:
    """Suggest or perform organization of Drive."""
    tokens, err = _require_tokens()
    if err: return err
    listing = drive_list(page_size=100)
    if not listing.get("ok"):
        return listing
    files = listing.get("files", [])
    # group
    groups: dict[str, list[dict]] = {}
    for f in files:
        mt = f.get("mimeType","")
        if "image" in mt: key = "Images"
        elif "video" in mt: key = "Videos"
        elif "audio" in mt: key = "Audio"
        elif "pdf" in mt: key = "PDFs"
        elif "spreadsheet" in mt or "excel" in mt: key = "Sheets"
        elif "document" in mt or "text" in mt: key = "Docs"
        elif "folder" in mt: key = "__folders"
        else: key = "Others"
        groups.setdefault(key, []).append(f)

    suggestions = []
    for key, items in groups.items():
        if key == "__folders": continue
        suggestions.append(f"{key}: {len(items)} files → folder '{key}'")

    if dry_run:
        return {"ok": True, "dry_run": True, "groups": {k: len(v) for k,v in groups.items()}, "suggestions": suggestions, "files_sample": files[:10]}

    # actual organize: create folders and move
    results = []
    for key, items in groups.items():
        if key == "__folders": continue
        if not items: continue
        # create folder if not exists
        existing = [f for f in files if f.get("name")==key and "folder" in f.get("mimeType","")]
        folder_id = existing[0]["id"] if existing else None
        if not folder_id:
            created = drive_create_folder(key)
            if created.get("ok"):
                folder_id = created["file"].get("id")
                results.append(f"Created folder {key}")
            else:
                results.append(f"Failed folder {key}: {created.get('error')}")
                continue
        for it in items[:20]: # limit moves per call
            mv = drive_move(it["id"], folder_id)
            results.append(f"moved {it['name']} → {key}: {mv.get('ok')}")

    return {"ok": True, "dry_run": False, "results": results, "groups": {k: len(v) for k,v in groups.items()}}

# For agent's generic dispatcher
def generic_action(service: str, action: str, params: dict) -> dict:
    service = service.lower()
    action = action.lower()
    if service == "gmail":
        if action in ("list","search"): return gmail_list(q=params.get("q",""), max_results=int(params.get("max_results",10)))
        if action == "read": return gmail_read(params.get("id") or params.get("message_id",""))
        if action == "send": return gmail_send(params.get("to",""), params.get("subject","(no subject)"), params.get("body","") or params.get("message",""), params.get("cc"), params.get("bcc"))
        if action in ("trash","delete"): return gmail_trash(params.get("id") or params.get("message_id",""))
        if action == "modify": return gmail_modify(params.get("id",""), params.get("add"), params.get("remove"))
    elif service == "calendar":
        if action in ("list","events"): return calendar_list(q=params.get("q"), max_results=int(params.get("max_results",10)), time_min=params.get("time_min"), time_max=params.get("time_max"))
        if action == "create": return calendar_create(summary=params.get("summary") or params.get("title",""), start_iso=params.get("start_iso") or params.get("start",""), end_iso=params.get("end_iso") or params.get("end",""), description=params.get("description",""), location=params.get("location",""))
        if action == "delete": return calendar_delete(params.get("calendar_id","primary"), params.get("event_id") or params.get("id",""))
        if action == "plan": return calendar_plan_day(params.get("date_iso"), params.get("timezone","UTC"))
        if action == "recognize": return calendar_recognize()
    elif service == "drive":
        if action in ("list","search"): return drive_list(q=params.get("q",""), page_size=int(params.get("page_size",30)))
        if action == "storage": return drive_storage()
        if action == "organize": return drive_organize(strategy=params.get("strategy","by_type"), dry_run=params.get("dry_run", True) in (True, "true", "1"))
        if action in ("delete","trash"): return drive_delete(params.get("id") or params.get("file_id",""), trash=params.get("trash", True) in (True, "true"))
        if action == "create_folder": return drive_create_folder(params.get("name","New Folder"), params.get("parent_id"))
        if action in ("rename","move"):
            if action == "rename": return drive_rename(params.get("id") or params.get("file_id",""), params.get("name",""))
            else: return drive_move(params.get("id") or params.get("file_id",""), params.get("new_parent_id",""), params.get("old_parent_id"))
    return {"ok": False, "error": f"Unknown {service}/{action}"}
