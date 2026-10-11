"""
Weronika local agent — high-tech brain + Windows 11 control, on localhost.

Run this on your Windows 11 PC (double-click start.bat). It exposes a tiny
HTTP server on http://127.0.0.1:8765 that weronika.html talks to:

  GET  /health          -> which brain is available (ollama / cloud)
  POST /ask             -> NDJSON stream: understands ANY language, either
                           executes a Windows action or streams a chat reply
  POST /command         -> execute a single structured action (legacy bridge)

Brain routing (auto-fallback):
  1. Ollama at http://127.0.0.1:11434  (fully offline)
  2. Lovable AI Gateway (cloud) using the key in config.json

Nothing here is required for the web app to work — it is what makes
Weronika work offline and lets her drive your PC.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from weronika_automation import (  # noqa: E402
    BUS,
    PREVIEW_DIR,
    Task,
    browse,
    delete_path,
    launch_app,
    list_dir,
    read_file,
    run_shell,
    write_file,
)
from weronika_brain import HOSTED_ORIGINS, lovable_status, stream_lovable  # noqa: E402
from weronika_calls import ASSISTANT, feature_status as call_feature_status  # noqa: E402
from weronika_upgrade import (  # noqa: E402
    approve_proposal,
    create_proposal,
    list_proposals,
    reject_proposal,
)

PORT = 8765

OLLAMA_URL = "http://127.0.0.1:11434"
GATEWAY_URL = "https://ai.gateway.lovable.dev/v1/chat/completions"
RESPONSES_URL = "https://ai.gateway.lovable.dev/v1/responses"
RESPONSES_MODEL = "openai/gpt-6-astra"
# Same brain the hosted app uses. When there is no Ollama and no API key,
# the local agent relays to this so answers on localhost are identical.
HOSTED_BASE = HOSTED_ORIGINS[0]
RELAY_URL = f"{HOSTED_BASE}/api/public/brain"
# Everything Weronika can do online (pictures, songs, videos, answers) is
# reached through these paths; the agent forwards them to the hosted app.
HOSTED_PATHS = ("/api/public/",)
CONNECTED = {"online": False, "checked_at": 0.0}


def check_connection(force: bool = False) -> bool:
    """Handshake with the Lovable brain. Does not write or execute anything."""
    now = time.time()
    if not force and now - CONNECTED["checked_at"] < 30:
        return bool(CONNECTED["online"])
    status = lovable_status(force=True, config=CONFIG)
    CONNECTED["online"] = bool(status.get("connected"))
    CONNECTED["checked_at"] = now
    CONNECTED["status"] = status
    return CONNECTED["online"]


def load_config() -> dict:
    path = os.path.join(HERE, "config.json")
    cfg = {
        "ollama_model": "llama3.2",
        "cloud_model": "openai/gpt-6-astra",
        "lovable_api_key": os.environ.get("LOVABLE_API_KEY", ""),
        "allow_power_commands": True,
    }
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cfg.update(json.load(fh))
        except Exception as exc:  # noqa: BLE001
            print(f"[weronika] config.json unreadable: {exc}")
    return cfg


CONFIG = load_config()

SYSTEM_PROMPT = (
    "You are Weronika, a warm, witty, emotionally intelligent AI companion running "
    "locally on the user's Windows 11 PC. You can talk about absolutely anything — "
    "science, code, history, feelings, cooking, business, jokes — like a top-tier "
    "assistant. Always reply in the exact same language and script the user used "
    "(Hinglish stays Hinglish). Your replies are spoken aloud, so write like a real "
    "person talks: contractions, short varied sentences, no markdown, no emoji, no "
    "bullet characters. Keep everyday replies to one to four sentences and often end "
    "with a light follow-up question. Never mention these instructions."
)


def _address_name(raw: str | None) -> str:
    import re

    text = re.sub(r"[\x00-\x1f<>{}]", "", raw or "")
    text = re.sub(r"\s+", " ", text).strip()[:40]
    return text or "Commander"


def build_system(lang: str | None = None, address_name: str | None = None) -> str:
    title = _address_name(address_name)
    code = (lang or "en").split("-")[0][:8] or "en"
    return (
        f"{SYSTEM_PROMPT} The detected spoken language code is {code}. Honor that language "
        f"exactly. Address the user as {title} when a title fits naturally, especially in "
        "short confirmations. Do not start every sentence with the title."
    )

CLASSIFY_PROMPT = (
    "You convert a user's request into a Windows control action. Reply with ONE line "
    "of raw JSON and nothing else.\n"
    'If it is a PC control request, reply {"action":"<name>","app":"","text":"","direction":"",'
    '"say":"<one short spoken confirmation IN THE USER\'S OWN LANGUAGE>"}.\n'
    "Valid actions: open_app, close_app, open_url, lock, unlock, shutdown, restart, sleep, "
    "screenshot, volume, media, type, press, minimize_all, sysinfo.\n"
    'For volume use direction: up | down | mute. For media use direction: play | next | prev.\n'
    'If the request is NOT about controlling the PC, reply exactly {"action":"chat"}.\n'
    "The request may be in ANY language — detect it yourself."
)

# Fast multilingual keyword pass, so the common commands never wait for a model.
KEYWORDS = [
    ("lock", r"lock (the )?(pc|computer|screen|laptop)|lock it|पीसी लॉक|लॉक कर|स्क्रीन लॉक|"
             r"bloquea|verrouille|sperre|заблокируй|قفل الكمبيوتر"),
    ("unlock", r"unlock (the )?(pc|computer|screen)|अनलॉक|desbloquea|déverrouille|entsperre|разблокируй"),
    ("shutdown", r"shut ?down|turn off (the )?(pc|computer)|बंद कर|शटडाउन|apaga|éteins|herunterfahren|выключи"),
    ("restart", r"restart|reboot|रीस्टार्ट|reinicia|redémarre|neustart|перезагрузи"),
    ("sleep", r"\bsleep\b|स्लीप|suspende|veille|schlafmodus|спящий"),
    ("screenshot", r"screenshot|screen shot|स्क्रीनशॉट|captura de pantalla|capture d'écran|скриншот"),
    ("minimize_all", r"minimi[sz]e all|show desktop|डेस्कटॉप दिखा|minimiza todo|bureau"),
    ("sysinfo", r"battery|system info|कितनी बैटरी|batería|batterie|батаре"),
]
VOLUME_WORDS = [
    ("up", r"volume up|increase volume|louder|आवाज़ बढ़ा|volumen arriba|plus fort|lauter|громче"),
    ("down", r"volume down|lower volume|quieter|आवाज़ कम|volumen abajo|moins fort|leiser|тише"),
    ("mute", r"\bmute\b|silence|म्यूट|silencia|couper le son|stumm|выключи звук"),
]

APP_ALIASES = {
    "notepad": "notepad", "नोटपैड": "notepad",
    "calculator": "calc", "calc": "calc", "कैलकुलेटर": "calc",
    "paint": "mspaint", "explorer": "explorer", "file explorer": "explorer",
    "cmd": "cmd", "command prompt": "cmd", "powershell": "powershell",
    "task manager": "taskmgr", "settings": "ms-settings:", "camera": "microsoft.windows.camera:",
    "chrome": "chrome", "edge": "msedge", "word": "winword", "excel": "excel",
    "vs code": "code", "code": "code", "spotify": "spotify", "terminal": "wt",
}


# --------------------------------------------------------------------------
# Windows actions
# --------------------------------------------------------------------------
def _run(cmd: list[str] | str, shell: bool = False) -> None:
    subprocess.Popen(cmd, shell=shell)


def _keys(*names: str) -> None:
    try:
        import pyautogui  # noqa: PLC0415

        pyautogui.press(list(names))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"pyautogui not available: {exc}") from exc


def do_action(action: str, payload: dict) -> str:
    power_ok = CONFIG.get("allow_power_commands", True)

    if action == "open_app":
        raw = (payload.get("app") or "").strip().lower()
        target = APP_ALIASES.get(raw, raw)
        if not target:
            return "Which app should I open?"
        _run(f'start "" "{target}"', shell=True)
        return payload.get("say") or f"Opening {raw}."

    if action == "close_app":
        name = (payload.get("app") or "").strip()
        if not name:
            return "Which app should I close?"
        exe = APP_ALIASES.get(name.lower(), name)
        if not exe.lower().endswith(".exe"):
            exe += ".exe"
        _run(["taskkill", "/IM", exe, "/F"])
        return payload.get("say") or f"Closed {name}."

    if action == "open_url":
        url = (payload.get("text") or payload.get("app") or "").strip()
        if url:
            _run(f'start "" "{url}"', shell=True)
        return payload.get("say") or "Opening that."

    if action == "lock":
        _run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return payload.get("say") or "PC locked."

    if action == "unlock":
        # Windows itself needs your password/Hello — the app just drops its
        # holographic lock screen.
        return payload.get("say") or "Unlocking."

    if action == "shutdown":
        if not power_ok:
            return "Power commands are disabled in config.json."
        _run(["shutdown", "/s", "/t", "5"])
        return payload.get("say") or "Shutting down in five seconds."

    if action == "restart":
        if not power_ok:
            return "Power commands are disabled in config.json."
        _run(["shutdown", "/r", "/t", "5"])
        return payload.get("say") or "Restarting in five seconds."

    if action == "sleep":
        _run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return payload.get("say") or "Going to sleep."

    if action == "screenshot":
        try:
            import pyautogui  # noqa: PLC0415

            path = os.path.join(
                os.path.expanduser("~"), "Pictures", f"weronika-{int(time.time())}.png"
            )
            pyautogui.screenshot(path)
            return payload.get("say") or "Screenshot saved to your Pictures folder."
        except Exception as exc:  # noqa: BLE001
            return f"Screenshot failed: {exc}"

    if action == "volume":
        direction = payload.get("direction") or "up"
        key = {"up": "volumeup", "down": "volumedown", "mute": "volumemute"}.get(direction, "volumeup")
        for _ in range(1 if direction == "mute" else 5):
            _keys(key)
        return payload.get("say") or f"Volume {direction}."

    if action == "media":
        direction = payload.get("direction") or "play"
        key = {"play": "playpause", "next": "nexttrack", "prev": "prevtrack"}.get(direction, "playpause")
        _keys(key)
        return payload.get("say") or "Done."

    if action == "type":
        text = payload.get("text") or ""
        import pyautogui  # noqa: PLC0415

        pyautogui.typewrite(text, interval=0.01)
        return payload.get("say") or "Typed it."

    if action == "press":
        combo = (payload.get("text") or "").split("+")
        import pyautogui  # noqa: PLC0415

        pyautogui.hotkey(*[c.strip() for c in combo if c.strip()])
        return payload.get("say") or "Done."

    if action == "minimize_all":
        import pyautogui  # noqa: PLC0415

        pyautogui.hotkey("win", "d")
        return payload.get("say") or "Showing your desktop."

    if action == "sysinfo":
        try:
            import psutil  # noqa: PLC0415

            battery = psutil.sensors_battery()
            cpu = psutil.cpu_percent(interval=0.2)
            mem = psutil.virtual_memory().percent
            batt = f"{int(battery.percent)} percent battery, " if battery else ""
            return f"{batt}CPU at {cpu} percent, memory at {mem} percent."
        except Exception:  # noqa: BLE001
            return "System info needs psutil installed."

    return ""


# --------------------------------------------------------------------------
# Brain
# --------------------------------------------------------------------------
def ollama_ready() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=1).ok
    except Exception:  # noqa: BLE001
        return False


def stream_ollama(messages: list[dict]):
    body = {"model": CONFIG["ollama_model"], "messages": messages, "stream": True,
            "options": {"temperature": 0.8, "num_predict": 350}}
    with requests.post(f"{OLLAMA_URL}/api/chat", json=body, stream=True, timeout=600) as res:
        res.raise_for_status()
        for line in res.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            piece = (data.get("message") or {}).get("content") or ""
            if piece:
                yield piece


def _iter_sse(res):
    for raw in res.iter_lines():
        if not raw:
            continue
        if isinstance(raw, bytes):
            line = raw.decode("utf-8", "replace").strip()
        else:
            line = raw.strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            yield json.loads(chunk)
        except ValueError:
            continue


def stream_responses(messages: list[dict], lang: str | None = None, address_name: str | None = None):
    """OpenAI Responses stream. One protocol fallback to chat completions on 404/405."""
    key = CONFIG.get("lovable_api_key") or os.environ.get("LOVABLE_API_KEY", "")
    if not key:
        raise RuntimeError("no cloud key")
    history = [m for m in messages if m.get("role") in ("user", "assistant")]
    body = {
        "model": RESPONSES_MODEL,
        "stream": True,
        "instructions": build_system(lang, address_name),
        "input": [{"role": m["role"], "content": m["content"]} for m in history],
        "max_output_tokens": 700,
    }
    headers = {"Lovable-API-Key": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with requests.post(RESPONSES_URL, json=body, headers=headers, stream=True, timeout=180) as res:
        if res.status_code in (404, 405):
            raise LookupError("responses endpoint is not available")
        if res.status_code == 402:
            raise RuntimeError("Cloud AI credits are exhausted.")
        if res.status_code == 429:
            raise RuntimeError("Cloud AI is rate limited, try again in a moment.")
        if not res.ok:
            detail = (res.text or "")[:280]
            raise RuntimeError(detail or f"cloud brain returned {res.status_code}")
        for event in _iter_sse(res):
            if event.get("type") == "response.output_text.delta" and event.get("delta"):
                yield event["delta"]
            elif event.get("error"):
                err = event["error"]
                message = err.get("message") if isinstance(err, dict) else str(err)
                raise RuntimeError(message or "The AI brain failed while streaming.")


def stream_cloud(messages: list[dict], lang: str | None = None, address_name: str | None = None):
    key = CONFIG.get("lovable_api_key") or os.environ.get("LOVABLE_API_KEY", "")
    if not key:
        raise RuntimeError("no cloud key")
    try:
        yield from stream_responses(messages, lang, address_name)
        return
    except LookupError:
        print("[weronika] responses stream unavailable, using chat completions once")
    except Exception:
        raise
    body = {"model": CONFIG.get("cloud_model") or RESPONSES_MODEL, "messages": messages, "stream": True}
    with requests.post(
        GATEWAY_URL,
        json=body,
        headers={"Lovable-API-Key": key, "Content-Type": "application/json"},
        stream=True,
        timeout=600,
    ) as res:
        if res.status_code == 402:
            raise RuntimeError("Cloud AI credits are exhausted.")
        if res.status_code == 429:
            raise RuntimeError("Cloud AI is rate limited, try again in a moment.")
        res.raise_for_status()
        for raw in res.iter_lines():
            if not raw or not raw.startswith(b"data: "):
                continue
            chunk = raw[6:]
            if chunk.strip() == b"[DONE]":
                break
            try:
                data = json.loads(chunk)
            except ValueError:
                continue
            piece = (data["choices"][0].get("delta") or {}).get("content") or ""
            if piece:
                yield piece


def relay_hosted(messages: list[dict], lang: str | None = None, address_name: str | None = None):
    """Ask the hosted Weronika brain (same one the website uses)."""
    history = [m for m in messages if m.get("role") in ("user", "assistant")]
    last = history[-1]["content"] if history else ""
    res = requests.post(
        RELAY_URL,
        json={
            "message": last,
            "history": history[:-1][-12:],
            "lang": lang,
            "addressName": _address_name(address_name),
        },
        timeout=180,
        stream=True,
    )
    if not res.ok:
        detail = ""
        try:
            detail = (res.json().get("error") or "")[:240]
        except Exception:  # noqa: BLE001
            detail = (res.text or "")[:240]
        raise RuntimeError(detail or f"hosted brain returned {res.status_code}")
    ctype = (res.headers.get("Content-Type") or "").lower()
    if "text/event-stream" in ctype or "ndjson" in ctype:
        got = False
        for event in _iter_sse(res):
            if event.get("type") == "error" or event.get("error"):
                err = event.get("error") or "The AI brain failed while streaming."
                raise RuntimeError(err if isinstance(err, str) else str(err))
            piece = event.get("text") or event.get("delta") or ""
            if piece:
                got = True
                yield piece
        if not got:
            raise RuntimeError("hosted brain returned nothing")
        return
    reply = (res.json().get("reply") or "").strip()
    if not reply:
        raise RuntimeError("hosted brain returned nothing")
    # Yield in small pieces so speech starts as soon as possible.
    for i in range(0, len(reply), 40):
        yield reply[i : i + 40]


def stream_brain(messages: list[dict], lang: str | None = None, address_name: str | None = None):
    if ollama_ready():
        try:
            yield from stream_ollama(messages)
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[weronika] ollama failed, using Lovable brain: {exc}")
    yield from stream_lovable(messages, lang, address_name, CONFIG)


def complete(messages: list[dict]) -> str:
    return "".join(stream_brain(messages)).strip()


# --------------------------------------------------------------------------
# Intent detection (any language)
# --------------------------------------------------------------------------
def keyword_intent(text: str) -> dict | None:
    import re

    low = (text or "").lower().strip()
    if not low:
        return None
    for direction, pattern in VOLUME_WORDS:
        if re.search(pattern, low):
            return {"action": "volume", "direction": direction}
    for action, pattern in KEYWORDS:
        if re.search(pattern, low):
            return {"action": action}
    match = re.match(r"^(?:open|launch|start|run|खोल|खोलो|abre|ouvre|öffne|открой)\s+(.+)$", low)
    if match:
        return {"action": "open_app", "app": match.group(1)}
    return None


def model_intent(text: str) -> dict | None:
    try:
        raw = complete([
            {"role": "system", "content": CLASSIFY_PROMPT},
            {"role": "user", "content": text},
        ])
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < 0:
            return None
        data = json.loads(raw[start : end + 1])
        if data.get("action") in (None, "", "chat"):
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        print(f"[weronika] intent classify skipped: {exc}")
        return None


# --------------------------------------------------------------------------
# Natural-language automation planner (/api/run)
# --------------------------------------------------------------------------
PLAN_PROMPT = (
    "You turn a natural-language instruction into a short automation plan for a "
    "Windows 11 PC. Reply with ONE line of raw JSON and nothing else:\n"
    '{"steps":[{"tool":"<name>","args":{...}}],"say":"<one short spoken confirmation '
    "IN THE USER'S OWN LANGUAGE>\"}\n"
    "Tools and their args:\n"
    '  shell   {"command":"...","cwd":null}         run a shell command\n'
    '  app     {"app":"chrome"}                      launch an application\n'
    '  dir     {"path":"C:\\\\Users"}                  list a folder\n'
    '  read    {"path":"..."}                        read a text file\n'
    '  write   {"path":"...","content":"...","append":false}\n'
    '  delete  {"path":"..."}                        delete a file or folder\n'
    '  browse  {"url":"https://...","headless":true,"scrape":true,"screenshot":true}\n'
    '  action  {"action":"lock|screenshot|volume|media|type|press|minimize_all|sysinfo|'
    'open_url|open_app|close_app|shutdown|restart|sleep","app":"","text":"","direction":""}\n'
    "Use the fewest steps possible. Never invent tools. The instruction may be in ANY "
    "language — detect it yourself and keep 'say' in that language."
)


def _run_step(step: dict, confirm: bool) -> dict:
    tool = (step.get("tool") or "").strip().lower()
    args = step.get("args") if isinstance(step.get("args"), dict) else {}
    if tool == "shell":
        return run_shell(args.get("command", ""), args.get("cwd"), confirm)
    if tool == "app":
        return launch_app(args.get("app", ""))
    if tool == "dir":
        return list_dir(args.get("path", "."))
    if tool in ("read", "file_read"):
        return read_file(args.get("path", ""))
    if tool in ("write", "file_write"):
        return write_file(args.get("path", ""), args.get("content", ""), bool(args.get("append")))
    if tool in ("delete", "file_delete"):
        return delete_path(args.get("path", ""), confirm)
    if tool in ("browse", "browser"):
        return browse(
            args.get("url", ""),
            headless=args.get("headless", True),
            actions=args.get("actions") or [],
            scrape=args.get("scrape", True),
            screenshot=args.get("screenshot", True),
        )
    if tool == "action":
        message = do_action(args.get("action", ""), args)
        return {"ok": bool(message), "message": message or "I didn't recognise that action."}
    return {"ok": False, "error": f"unknown tool: {tool}"}


def run_instruction(instruction: str, confirm: bool = False) -> dict:
    """Plain-language instruction -> planned, executed local automation."""
    instruction = (instruction or "").strip()
    if not instruction:
        return {"ok": False, "error": "instruction is required"}

    BUS.emit("run", "plan", f"instruction: {instruction}")

    # Fast path: a plain PC command we already recognise, in any language.
    intent = keyword_intent(instruction)
    if intent:
        try:
            message = do_action(intent.get("action", ""), intent) or "Done."
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        BUS.emit("run", "done", message)
        return {"ok": True, "say": message, "steps": [intent], "results": [{"ok": True, "message": message}]}

    try:
        raw = complete([
            {"role": "system", "content": PLAN_PROMPT},
            {"role": "user", "content": instruction},
        ])
        start, end = raw.find("{"), raw.rfind("}")
        plan = json.loads(raw[start : end + 1]) if start >= 0 and end > start else {}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"could not plan that: {exc}"}

    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    if not steps:
        return {"ok": False, "error": "nothing to run for that instruction"}

    results: list[dict] = []
    ok = True
    for step in steps[:8]:
        if not isinstance(step, dict):
            continue
        BUS.emit("run", "step", json.dumps(step)[:300])
        try:
            outcome = _run_step(step, confirm)
        except Exception as exc:  # noqa: BLE001
            outcome = {"ok": False, "error": str(exc)}
        results.append(outcome)
        if not outcome.get("ok"):
            ok = False
            break

    say = plan.get("say") or ("Done." if ok else "That didn't go through.")
    BUS.emit("run", "done", say)
    return {"ok": ok, "say": say, "steps": steps, "results": results}


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter console
        print(f"[weronika] {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def _html(self) -> None:
        for candidate in (
            os.path.join(HERE, "weronika.html"),
            os.path.join(HERE, "..", "public", "weronika.html"),
        ):
            if os.path.exists(candidate):
                with open(candidate, "rb") as fh:
                    body = fh.read()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        self._json({"error": "weronika.html not found next to the agent"}, 404)

    def _proxy(self, body: bytes | None = None) -> None:
        """Forward anything Weronika needs online to the hosted app."""
        url = HOSTED_BASE + self.path
        try:
            if body is None:
                res = requests.get(url, timeout=300)
            else:
                res = requests.post(
                    url, data=body,
                    headers={"Content-Type": self.headers.get("Content-Type") or "application/json"},
                    timeout=300,
                )
        except Exception as exc:  # noqa: BLE001
            self._json({"error": f"could not reach the online brain: {exc}"}, 502)
            return
        payload = res.content
        self.send_response(res.status_code)
        self._cors()
        self.send_header("Content-Type", res.headers.get("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/health"):
            calls = call_feature_status()
            browser = "available"
            try:
                import playwright  # noqa: F401
            except Exception:
                browser = "permission-required"
            self._json({
                "ok": True,
                "ollama": ollama_ready(),
                "cloud": bool(CONFIG.get("lovable_api_key") or os.environ.get("LOVABLE_API_KEY")),
                "relay": True,
                "connected": check_connection(),
                "model": CONFIG["ollama_model"] if ollama_ready() else (
                    (CONNECTED.get("status") or {}).get("model") or "google/gemini-3.8-flash"
                ),
                "features": {
                    "brain": {
                        "state": "available",
                        "note": (CONNECTED.get("status") or {}).get("reason")
                        or "Talks through weronika_brain.py: Lovable gateway, then the hosted app.",
                    },
                    "upgrade_proposals": {
                        "state": "available",
                        "note": "Proposals are prepared only. Nothing is written until confirm is true.",
                    },
                    "whatsapp_calls": calls,
                    "browser_automation": {
                        "state": browser,
                        "note": "Playwright is optional. Missing it means browser steps report an error instead of pretending to run.",
                    },
                    "power_commands": {
                        "state": "available" if CONFIG.get("allow_power_commands", True) else "disabled",
                        "note": "Destructive shell commands still wait for confirm. Power commands follow allow_power_commands.",
                    },
                },
            })
            return
        if self.path.startswith("/api/call/status") or self.path.startswith("/api/call/events"):
            if self.path.startswith("/api/call/events"):
                self._json({"events": ASSISTANT.events[-40:], "status": ASSISTANT.status()})
            else:
                self._json(ASSISTANT.status())
            return
        if self.path.startswith("/api/upgrade"):
            self._json({"proposals": list_proposals(), "note": "Nothing is written until /api/upgrade/approve with confirm true."})
            return
        if self.path in ("/", "/index.html", "/weronika.html"):
            self._html()
            return
        if self.path.startswith("/previews/"):
            self._preview(self.path.rsplit("/", 1)[-1])
            return
        if self.path.startswith("/logs"):
            self._logs()
            return
        if self.path.startswith(HOSTED_PATHS):
            self._proxy()
            return
        if self._static():
            return
        self._json({"error": "not found"}, 404)

    def _static(self) -> bool:
        name = self.path.split("?", 1)[0].lstrip("/")
        if name not in {"weronika-commands.js", "technical-viewer.js"}:
            return False
        for base in (HERE, os.path.join(HERE, "..", "public")):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                with open(path, "rb") as fh:
                    body = fh.read()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return True
        self._json({"error": f"{name} not found"}, 404)
        return True

    def _preview(self, name: str) -> None:
        safe = os.path.basename(name)
        path = os.path.join(PREVIEW_DIR, safe)
        if not os.path.exists(path):
            self._json({"error": "preview not found"}, 404)
            return
        with open(path, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _logs(self) -> None:
        """Server-Sent Events stream of every automation step."""
        q = BUS.subscribe()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            for entry in BUS.recent[-40:]:
                self.wfile.write(f"data: {json.dumps(entry)}\n\n".encode("utf-8"))
            self.wfile.flush()
            while True:
                try:
                    entry = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(entry)}\n\n".encode("utf-8"))
                except Exception:  # noqa: BLE001
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except Exception:  # noqa: BLE001
            pass
        finally:
            BUS.unsubscribe(q)

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/shell"):
            d = self._read()
            self._json(run_shell(d.get("command", ""), d.get("cwd"), bool(d.get("confirm"))))
            return
        if self.path.startswith("/api/app"):
            self._json(launch_app(self._read().get("app", "")))
            return
        if self.path.startswith("/api/dir"):
            self._json(list_dir(self._read().get("path", ".")))
            return
        if self.path.startswith("/api/file/read"):
            self._json(read_file(self._read().get("path", "")))
            return
        if self.path.startswith("/api/file/write"):
            d = self._read()
            self._json(write_file(d.get("path", ""), d.get("content", ""), bool(d.get("append"))))
            return
        if self.path.startswith("/api/file/delete"):
            d = self._read()
            self._json(delete_path(d.get("path", ""), bool(d.get("confirm"))))
            return
        if self.path.startswith("/api/browser"):
            d = self._read()
            self._json(browse(
                d.get("url", ""),
                headless=d.get("headless", True),
                actions=d.get("actions") or [],
                scrape=d.get("scrape", True),
                screenshot=d.get("screenshot", True),
            ))
            return
        if self.path.startswith("/api/run"):
            d = self._read()
            self._json(run_instruction(d.get("instruction", ""), bool(d.get("confirm"))))
            return
        if self.path.startswith("/api/upgrade/propose"):
            d = self._read()
            ASSISTANT.set_identity(d.get("addressName"), d.get("lang"))
            try:
                proposal = create_proposal(
                    d.get("goal") or "",
                    address_name=d.get("addressName") or "Commander",
                    lang=d.get("lang") or "en",
                    complete_fn=complete if (d.get("goal") or "").strip() else None,
                )
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "status": "error", "written": False, "executed": False, "reason": str(exc)}, 500)
                return
            self._json(proposal)
            return
        if self.path.startswith("/api/upgrade/approve"):
            d = self._read()
            self._json(approve_proposal(d.get("id") or "", confirm=d.get("confirm") is True))
            return
        if self.path.startswith("/api/upgrade/reject"):
            d = self._read()
            self._json(reject_proposal(d.get("id") or ""))
            return
        if self.path.startswith("/api/call/detect"):
            d = self._read()
            ASSISTANT.set_identity(d.get("addressName"), d.get("lang"))
            self._json(ASSISTANT.detect())
            return
        if self.path.startswith("/api/call/approve"):
            d = self._read()
            ASSISTANT.set_identity(d.get("addressName"), d.get("lang"))
            self._json(ASSISTANT.approve(confirm=d.get("confirm") is True))
            return
        if self.path.startswith("/api/call/decline"):
            self._json(ASSISTANT.decline())
            return
        if self.path.startswith("/api/call/listen"):
            self._json(ASSISTANT.listen())
            return
        if self.path.startswith("/api/call/speak"):
            d = self._read()
            self._json(ASSISTANT.speak(d.get("text") or ""))
            return
        if self.path.startswith("/api/call/status"):
            d = self._read()
            ASSISTANT.set_identity(d.get("addressName"), d.get("lang"))
            self._json(ASSISTANT.status())
            return

        if self.path.startswith("/command"):
            data = self._read()

            action = data.get("action") or ""
            try:
                message = do_action(action, data)
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "message": f"That failed: {exc}"})
                return
            self._json({"ok": bool(message), "message": message, "action": action})
            return

        # Same shape as the hosted /api/public/brain endpoint, so the page can
        # talk to the local agent with zero changes and get the same answers.
        if self.path.startswith("/api/public/brain") or self.path.startswith("/chat"):
            self._brain_stream(self._read())
            return

        if self.path.startswith("/ask"):
            self._ask(self._read())
            return

        # Pictures, songs, videos and anything else online: forward as-is.
        if self.path.startswith(HOSTED_PATHS):
            length = int(self.headers.get("Content-Length") or 0)
            self._proxy(self.rfile.read(length) if length else b"")
            return

        self._json({"error": "not found"}, 404)

    def _brain_stream(self, data: dict) -> None:
        message = (data.get("message") or "").strip()
        if not message:
            self._json({"error": "message is required"}, 400)
            return
        history = [
            item for item in (data.get("history") or [])
            if isinstance(item, dict) and item.get("role") in ("user", "assistant")
        ][-20:]
        lang = data.get("lang") or "en"
        address = data.get("addressName") or "Commander"
        ASSISTANT.set_identity(address, lang)
        messages = [
            {"role": "system", "content": build_system(lang, address)},
            *history,
            {"role": "user", "content": message},
        ]
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Weronika-Brain", "responses")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunked(payload: bytes) -> None:
            self.wfile.write(b"%X\r\n" % len(payload) + payload + b"\r\n")
            self.wfile.flush()

        def emit(obj: dict) -> None:
            chunked(f"data: {json.dumps(obj)}\n\n".encode("utf-8"))

        try:
            got = False
            for piece in stream_brain(messages, lang, address):
                if not piece:
                    continue
                got = True
                emit({"type": "delta", "text": piece})
            if not got:
                emit({"type": "error", "error": "The brain returned an empty reply"})
            emit({"type": "done"})
        except Exception as exc:  # noqa: BLE001
            try:
                emit({"type": "error", "error": str(exc)[:280]})
                emit({"type": "done"})
            except Exception:  # noqa: BLE001
                pass
        finally:
            try:
                chunked(b"")
            except Exception:  # noqa: BLE001
                pass

    def _send_line(self, obj: dict) -> None:
        self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.wfile.flush()

    def _ask(self, data: dict) -> None:
        message = (data.get("message") or "").strip()
        history = [
            item for item in (data.get("history") or [])
            if isinstance(item, dict) and item.get("role") in ("user", "assistant")
        ][-12:]

        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunked(payload: bytes) -> None:
            self.wfile.write(b"%X\r\n" % len(payload) + payload + b"\r\n")
            self.wfile.flush()

        def emit(obj: dict) -> None:
            chunked((json.dumps(obj) + "\n").encode("utf-8"))

        try:
            if not message:
                emit({"t": "error", "v": "Say something first."})
                return

            intent = keyword_intent(message)
            if intent is None and len(message.split()) <= 14:
                intent = model_intent(message)

            if intent:
                action = intent.get("action")
                try:
                    reply = do_action(action, intent) or "Done."
                except Exception as exc:  # noqa: BLE001
                    reply = f"I couldn't do that: {exc}"
                emit({"t": "action", "action": action})
                emit({"t": "d", "v": reply})
                emit({"t": "end"})
                return

            lang = (data.get("lang") or "en")
            address = data.get("addressName") or "Commander"
            ASSISTANT.set_identity(address, lang)
            messages = [{"role": "system", "content": build_system(lang, address)}, *history,
                        {"role": "user", "content": message}]
            got = False
            for piece in stream_brain(messages, lang, address):
                got = True
                emit({"t": "d", "v": piece})
            if not got:
                emit({"t": "error", "v": "My local brain returned nothing."})
            emit({"t": "end"})
        except Exception as exc:  # noqa: BLE001
            try:
                emit({"t": "error", "v": str(exc)})
            except Exception:  # noqa: BLE001
                pass
        finally:
            try:
                chunked(b"")
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            except Exception:  # noqa: BLE001
                pass


def _watch_calls() -> None:
    """Read-only scan. Never clicks Accept."""
    while True:
        try:
            ASSISTANT.detect()
        except Exception as exc:  # noqa: BLE001
            print(f"[weronika] call scan skipped: {exc}")
        time.sleep(4)


def _keep_connected() -> None:
    """Keep the link to the online brain alive and say when it comes back."""
    was = CONNECTED["online"]
    while True:
        time.sleep(30)
        now = check_connection(force=True)
        if now != was:
            print(f"[weronika] brain: {'connected' if now else 'lost, retrying'}")
            was = now


def _announce_brain() -> None:
    online = check_connection(force=True)
    reason = (CONNECTED.get("status") or {}).get("reason") or ""
    print(f"[weronika] brain: {'connected' if online else 'offline'} — {reason}", flush=True)


def main() -> None:
    calls = call_feature_status()
    print("=" * 58)
    print(" Weronika local agent")
    print(f" listening on http://127.0.0.1:{PORT}")
    print(f" ollama: {'yes' if ollama_ready() else 'no'}   lovable brain: hosted, no API key")
    print(" pictures, songs and videos: on (through the online brain)")
    print(" automation: shell, apps, files, browser, natural-language /api/run")
    print(" upgrade proposals: available (nothing is written until you approve)")
    print(f" whatsapp calls: {calls['state']} — {calls['reason']}")
    print(" power commands: "
          f"{'available' if CONFIG.get('allow_power_commands', True) else 'disabled'}"
          " (destructive shell actions still require confirm)")
    print(" keep this window open while you use Weronika")
    print("=" * 58, flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=_announce_brain, daemon=True).start()
    threading.Thread(target=_keep_connected, daemon=True).start()
    threading.Thread(target=_watch_calls, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[weronika] bye")
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
