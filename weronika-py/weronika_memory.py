"""
Weronika persistent memory — survives shutdowns.

Stores:
- conversation history (last 40 turns)
- user profile inferred from calendar/mails
- daily context (last plan, last drive state)
- google tokens reference (actual tokens live in weronika_google.py store)

Frontend syncs to localStorage as well; this file is the disk truth.
Works offline. Atomic writes. No cloud.
"""
from __future__ import annotations
import json, os, time, threading, re
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
MEM_DIR = HERE / "memory"
MEM_FILE = MEM_DIR / "conversation.json"
PROFILE_FILE = MEM_DIR / "profile.json"
LOCK = threading.Lock()

DEFAULT_HISTORY_LIMIT = 40

def _ensure():
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    if not MEM_FILE.exists():
        _atomic_write(MEM_FILE, {"history": [], "sessions": [], "updated_at": time.time()})
    if not PROFILE_FILE.exists():
        _atomic_write(PROFILE_FILE, {"name": None, "timezone": None, "calendar_patterns": {}, "day_plans": [], "drive_preferences": {}, "updated_at": time.time()})

def _atomic_write(path: Path, data: Any):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def load_history(limit: int = 40) -> list[dict]:
    _ensure()
    try:
        with open(MEM_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        hist = data.get("history", [])
        if not isinstance(hist, list):
            return []
        # sanitize
        clean = []
        for item in hist[-limit:]:
            if isinstance(item, dict) and item.get("role") in ("user","assistant") and isinstance(item.get("content"), str):
                clean.append({"role": item["role"], "content": item["content"][:4000]})
        return clean
    except Exception:
        return []

def save_history(history: list[dict]):
    _ensure()
    with LOCK:
        try:
            with open(MEM_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        # keep only last 40
        hist = []
        for item in history[-DEFAULT_HISTORY_LIMIT:]:
            if isinstance(item, dict) and item.get("role") in ("user","assistant"):
                hist.append({"role": item["role"], "content": str(item.get("content",""))[:4000]})
        data["history"] = hist
        data["updated_at"] = time.time()
        # session log (for debugging, keep last 20 sessions markers)
        if "sessions" not in data:
            data["sessions"] = []
        _atomic_write(MEM_FILE, data)

def append_turn(role: str, content: str):
    if role not in ("user","assistant"):
        return
    hist = load_history(100)
    hist.append({"role": role, "content": content[:4000]})
    if len(hist) > DEFAULT_HISTORY_LIMIT:
        hist = hist[-DEFAULT_HISTORY_LIMIT:]
    save_history(hist)

def clear_history():
    _ensure()
    with LOCK:
        _atomic_write(MEM_FILE, {"history": [], "sessions": [], "updated_at": time.time()})

def load_profile() -> dict:
    _ensure()
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_profile(profile: dict):
    _ensure()
    with LOCK:
        profile["updated_at"] = time.time()
        _atomic_write(PROFILE_FILE, profile)

def update_profile_from_calendar(events: list[dict]):
    """Infer patterns from calendar events to recognize user day."""
    if not events:
        return
    prof = load_profile()
    patterns = prof.get("calendar_patterns", {})
    # simple heuristic: most frequent titles, time blocks
    for ev in events:
        title = str(ev.get("summary","")).strip()
        if not title:
            continue
        key = title.lower()[:60]
        patterns[key] = patterns.get(key, 0) + 1
    prof["calendar_patterns"] = dict(sorted(patterns.items(), key=lambda x: -x[1])[:50])
    # infer timezone from first event with timezone
    for ev in events:
        tz = ev.get("timezone")
        if tz:
            prof["timezone"] = tz
            break
    save_profile(prof)

def get_day_context() -> dict:
    """For greeting: returns last history + profile + time."""
    hist = load_history(6)
    prof = load_profile()
    now = time.time()
    last_user = next((h["content"] for h in reversed(hist) if h["role"]=="user"), "")
    return {
        "history_tail": hist[-6:],
        "profile": prof,
        "last_user": last_user,
        "now": now,
    }

def add_day_plan(plan: dict):
    prof = load_profile()
    plans = prof.get("day_plans", [])
    plans.append({**plan, "ts": time.time()})
    prof["day_plans"] = plans[-20:]
    save_profile(prof)

# Helpers for frontend sync
def merge_frontend_history(frontend_history: list[dict]):
    """Called when frontend sends its history; merge with disk (union, dedup last)."""
    disk = load_history(40)
    # If frontend has more recent tail, prefer frontend
    if not frontend_history:
        return disk
    # simple: if frontend longer, use frontend
    if len(frontend_history) >= len(disk):
        save_history(frontend_history)
        return frontend_history
    # otherwise merge dedup
    seen = set(json.dumps(x, sort_keys=True) for x in disk)
    merged = disk[:]
    for item in frontend_history:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            merged.append(item)
            seen.add(key)
    merged = merged[-DEFAULT_HISTORY_LIMIT:]
    save_history(merged)
    return merged
