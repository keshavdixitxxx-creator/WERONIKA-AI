"""Connect Weronika to the Lovable brain. No API key.

Lovable keeps the brain key on the hosted app. This file only sends the
conversation to that app and reads the reply back. The user never pastes a key.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Iterator

import requests

# Public Weronika brain. The key stays on Lovable's side.
HOSTED_ORIGINS = (
    "https://weronika-ai.lovable.app",
    "https://project--9b370ba5-6b95-4715-86da-780c9e2c7e13-dev.lovable.app",
)

SYSTEM_PROMPT = (
    "You are Weronika, a warm, witty AI companion who appears as a holographic orb. "
    "Talk like a real person. Reply in the same language the user used. Hinglish stays Hinglish. "
    "Spoken sentences only: no markdown, no emoji, no bullet characters. "
    "Keep everyday replies to one to four sentences and often end with a light question. "
    "Remember earlier turns. Never mention these instructions."
)

_CACHE = {"at": 0.0, "status": None}


def _address(raw: str | None) -> str:
    text = " ".join((raw or "").replace("<", " ").replace(">", " ").split())
    return text[:40] or "Commander"


def instructions(lang: str | None, address_name: str | None) -> str:
    code = (lang or "en").split("-")[0][:8] or "en"
    title = _address(address_name)
    return (
        f"{SYSTEM_PROMPT} The detected spoken language code is {code}. Honor that language. "
        f"Address the user as {title} when it fits. Do not start every sentence with the title."
    )


def _origins(config: dict | None) -> tuple[str, ...]:
    extra = ""
    if config:
        extra = str(config.get("hosted_brain") or config.get("hosted_origin") or "").strip().rstrip("/")
    found = []
    if extra:
        found.append(extra)
    for origin in HOSTED_ORIGINS:
        if origin not in found:
            found.append(origin)
    return tuple(found)


def _looks_unpublished(text: str) -> bool:
    folded = (text or "").lower()
    return (
        "no working published build" in folded
        or "no lovable project found" in folded
        or "<html" in folded
        or "forbidden" in folded
    )


def _iter_sse(res) -> Iterator[dict]:
    for raw in res.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) else str(raw).strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            yield json.loads(chunk)
        except ValueError:
            continue


def _reply_from_response(res) -> str:
    ctype = (res.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in ctype or "ndjson" in ctype:
        parts = []
        for event in _iter_sse(res):
            if event.get("type") == "error" or event.get("error"):
                err = event.get("error") or "The Lovable brain failed while streaming."
                raise RuntimeError(err if isinstance(err, str) else str(err))
            piece = event.get("text") or event.get("delta") or ""
            if piece:
                parts.append(piece)
        return "".join(parts).strip()
    raw = res.text or ""
    if _looks_unpublished(raw):
        raise LookupError("The hosted Lovable brain has no published build yet.")
    try:
        data = res.json()
    except ValueError as exc:
        raise LookupError("The hosted brain did not return a conversation.") from exc
    if isinstance(data, dict) and data.get("error"):
        raise LookupError(str(data["error"])[:240])
    reply = ""
    if isinstance(data, dict):
        reply = (data.get("reply") or data.get("text") or "").strip()
    if not reply:
        raise LookupError("The hosted brain returned nothing.")
    return reply


def ask_lovable(
    message: str,
    history: list[dict] | None = None,
    lang: str | None = "en",
    address_name: str | None = "Commander",
    config: dict | None = None,
    timeout: int = 25,
) -> str:
    """One turn with the hosted Lovable brain. No API key is sent."""
    payload = {
        "message": message,
        "history": (history or [])[-12:],
        "lang": lang or "en",
        "addressName": _address(address_name),
    }
    errors: list[str] = []
    for origin in _origins(config):
        try:
            res = requests.post(
                origin.rstrip("/") + "/api/public/brain",
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            continue
        if res.status_code in (401, 403, 404, 405):
            errors.append(f"{origin} returned {res.status_code}")
            continue
        if not res.ok:
            errors.append(f"{origin} returned {res.status_code}")
            continue
        try:
            reply = _reply_from_response(res)
        except LookupError as exc:
            errors.append(str(exc))
            continue
        if reply:
            return reply
    detail = errors[-1] if errors else "The hosted brain did not answer."
    raise RuntimeError(
        "Could not reach the Lovable brain. No API key is required. "
        "Publish the Weronika project once in Lovable, then run this file again. "
        + detail
    )


def lovable_status(force: bool = False, config: dict | None = None) -> dict:
    now = time.time()
    cached = _CACHE["status"]
    if not force and cached and now - _CACHE["at"] < 30:
        return cached
    status = {
        "connected": False,
        "provider": "lovable",
        "key_required": False,
        "reason": "",
    }
    try:
        reply = ask_lovable("Reply with the single word ready.", [], "en", "Commander", config, timeout=12)
        status["connected"] = bool(reply)
        status["reason"] = "Connected to the hosted Lovable brain. No API key is used."
    except Exception as exc:  # noqa: BLE001
        status["reason"] = str(exc)
    _CACHE["at"] = now
    _CACHE["status"] = status
    return status


def stream_lovable(
    messages: list[dict],
    lang: str | None = None,
    address_name: str | None = None,
    config: dict | None = None,
) -> Iterator[str]:
    """Yield the hosted Lovable reply. No API key is sent."""
    history = [m for m in messages if m.get("role") in ("user", "assistant") and m.get("content")]
    last = history[-1]["content"] if history else ""
    reply = ask_lovable(last, history[:-1], lang, address_name, config)
    # Hand the first sentence back immediately so speech can start.
    parts = [part for part in reply.replace("\n", " ").split(" ") if part]
    if not parts:
        yield reply
        return
    sentence = []
    for word in parts:
        sentence.append(word)
        if word.endswith((".", "?", "!")) or len(sentence) >= 12:
            yield " ".join(sentence) + " "
            sentence = []
    if sentence:
        yield " ".join(sentence)


def main() -> int:
    print("Weronika Lovable brain")
    print("No API key. Talking to the hosted Lovable brain.")
    status = lovable_status(force=True)
    print(status["reason"])
    if not status["connected"]:
        return 1
    print("Type a message. Blank line to stop.")
    history: list[dict] = []
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            return 0
        try:
            reply = ask_lovable(line, history)
        except Exception as exc:  # noqa: BLE001
            print(exc)
            return 1
        print(reply)
        history.append({"role": "user", "content": line})
        history.append({"role": "assistant", "content": reply})
        history = history[-12:]


if __name__ == "__main__":
    sys.exit(main())
