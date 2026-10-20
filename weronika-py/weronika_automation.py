"""
Weronika automation core — OS control, browser automation, file management
and a live log bus, all behind one structured JSON contract:

    {"status": ..., "logs": [...], "output_payload": {...}, "preview_url": ...}

status is one of: ok | error | needs_confirmation

Every step is pushed onto a shared log bus so the Lovable browser interface can
tail http://127.0.0.1:8765/logs (Server-Sent Events) and show real-time
execution logs and live previews.
"""

from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEW_DIR = os.path.join(HERE, "previews")
WORKSPACE = os.path.join(HERE, "workspace")
os.makedirs(PREVIEW_DIR, exist_ok=True)
os.makedirs(WORKSPACE, exist_ok=True)

PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


# --------------------------------------------------------------------------
# Log bus — every subscriber (the web UI) gets its own queue
# --------------------------------------------------------------------------
class LogBus:
    def __init__(self) -> None:
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()
        self.recent: list[dict] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def emit(self, task_id: str, level: str, message: str, **extra) -> dict:
        entry = {
            "task_id": task_id,
            "level": level,
            "message": message,
            "ts": round(time.time(), 3),
            **extra,
        }
        self.recent = (self.recent + [entry])[-300:]
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(entry)
            except Exception:  # noqa: BLE001
                pass
        print(f"[weronika:{level}] {message}")
        return entry


BUS = LogBus()


class Task:
    """Collects the logs for one instruction and builds the JSON response."""

    def __init__(self, label: str = "task") -> None:
        self.id = uuid.uuid4().hex[:12]
        self.logs: list[dict] = []
        self.log("info", f"started: {label}")

    def log(self, level: str, message: str, **extra) -> None:
        self.logs.append(BUS.emit(self.id, level, message, **extra))

    def result(self, status: str, output_payload: dict | None = None,
               preview_url: str | None = None) -> dict:
        self.log("info" if status == "ok" else status, f"finished: {status}")
        return {
            "status": status,
            "task_id": self.id,
            "logs": [f"{l['level']}: {l['message']}" for l in self.logs],
            "log_events": self.logs,
            "output_payload": output_payload or {},
            "preview_url": preview_url,
        }


# --------------------------------------------------------------------------
# Safety
# --------------------------------------------------------------------------
DESTRUCTIVE = [
    r"\brm\s+-[a-z]*r", r"\brmdir\b", r"\bdel\s+/", r"\bformat\b", r"\bmkfs\b",
    r"remove-item[^\n]*-recurse", r"\bshutdown\b", r"\brestart-computer\b",
    r"\breg\s+delete\b", r"\bdiskpart\b", r"\btaskkill\b[^\n]*/f",
    r"\bdrop\s+(table|database)\b", r">\s*/dev/", r":\(\)\s*\{",
]


def is_destructive(command: str) -> bool:
    low = (command or "").lower()
    return any(re.search(p, low) for p in DESTRUCTIVE)


def _safe_path(path: str) -> str:
    """Keep file work inside the agent workspace unless an absolute path is given."""
    if not path:
        raise ValueError("path is required")
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        expanded = os.path.join(WORKSPACE, expanded)
    return os.path.normpath(expanded)


# --------------------------------------------------------------------------
# OS control
# --------------------------------------------------------------------------
def run_shell(command: str, cwd: str | None = None, confirm: bool = False,
              timeout: int = 120) -> dict:
    task = Task(f"shell: {command}")
    if not command.strip():
        return task.result("error", {"error": "empty command"})

    if is_destructive(command) and not confirm:
        task.log("warn", "this command looks destructive — waiting for your confirmation")
        return task.result("needs_confirmation", {
            "command": command,
            "cwd": cwd,
            "reason": "This command can delete data or power off the machine.",
            "confirm_with": {"path": "/api/shell", "body": {"command": command, "confirm": True}},
        })

    workdir = _safe_path(cwd) if cwd else WORKSPACE
    task.log("info", f"running in {workdir}")
    try:
        proc = subprocess.run(
            command, shell=True, cwd=workdir, capture_output=True,
            text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return task.result("error", {"error": f"timed out after {timeout}s"})
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc)})

    for line in (proc.stdout or "").splitlines()[-60:]:
        task.log("stdout", line)
    for line in (proc.stderr or "").splitlines()[-30:]:
        task.log("stderr", line)

    return task.result("ok" if proc.returncode == 0 else "error", {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "cwd": workdir,
    })


APP_TARGETS = {
    "vs code": "code", "vscode": "code", "code": "code",
    "spotify": "spotify", "chrome": "chrome", "edge": "msedge",
    "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
    "notepad": "notepad", "explorer": "explorer", "calculator": "calc",
}


def launch_app(name: str) -> dict:
    task = Task(f"launch: {name}")
    raw = (name or "").strip().lower()
    target = APP_TARGETS.get(raw, raw)
    if not target:
        return task.result("error", {"error": "no app named"})
    try:
        if os.name == "nt":
            subprocess.Popen(f'start "" "{target}"', shell=True)
        else:
            subprocess.Popen([target])
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc)})
    task.log("info", f"launched {target}")
    return task.result("ok", {"app": target})


def list_dir(path: str = ".") -> dict:
    task = Task(f"list: {path}")
    try:
        target = _safe_path(path)
        entries = []
        for name in sorted(os.listdir(target))[:500]:
            full = os.path.join(target, name)
            entries.append({
                "name": name,
                "type": "dir" if os.path.isdir(full) else "file",
                "size": os.path.getsize(full) if os.path.isfile(full) else None,
            })
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc)})
    task.log("info", f"{len(entries)} entries")
    return task.result("ok", {"path": target, "entries": entries})


# --------------------------------------------------------------------------
# File management
# --------------------------------------------------------------------------
def read_file(path: str) -> dict:
    task = Task(f"read: {path}")
    try:
        target = _safe_path(path)
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(400_000)
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc)})
    task.log("info", f"read {len(content)} chars")
    return task.result("ok", {"path": target, "content": content})


def write_file(path: str, content: str, append: bool = False) -> dict:
    task = Task(f"write: {path}")
    try:
        target = _safe_path(path)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(content or "")
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc)})
    task.log("info", f"saved {target}")
    return task.result("ok", {"path": target, "bytes": len(content or "")})


def delete_path(path: str, confirm: bool = False) -> dict:
    task = Task(f"delete: {path}")
    target = _safe_path(path)
    if not confirm:
        task.log("warn", "deletion needs your confirmation")
        return task.result("needs_confirmation", {
            "path": target,
            "reason": "This permanently removes the file or folder.",
            "confirm_with": {"path": "/api/file/delete", "body": {"path": path, "confirm": True}},
        })
    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc)})
    task.log("info", f"deleted {target}")
    return task.result("ok", {"path": target})


# --------------------------------------------------------------------------
# Browser automation (Playwright, optional)
# --------------------------------------------------------------------------
def _playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        return sync_playwright
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "browser automation needs Playwright: pip install playwright && playwright install chromium"
        ) from exc


def browse(url: str, headless: bool = True, actions: list[dict] | None = None,
           scrape: bool = True, screenshot: bool = True) -> dict:
    """Open a page, optionally fill/click, then return text + a live screenshot."""
    task = Task(f"browse: {url}")
    if not url:
        return task.result("error", {"error": "url is required"})
    if not url.startswith("http"):
        url = "https://" + url

    try:
        sync_playwright = _playwright()
    except RuntimeError as exc:
        return task.result("error", {"error": str(exc)})

    shot_name = f"shot-{uuid.uuid4().hex[:10]}.png"
    shot_path = os.path.join(PREVIEW_DIR, shot_name)
    payload: dict = {"url": url, "actions_done": []}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
            task.log("info", f"opening {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)

            for step in actions or []:
                kind = (step.get("type") or "").lower()
                selector = step.get("selector") or ""
                value = step.get("value") or ""
                task.log("info", f"{kind} {selector} {value}".strip())
                if kind == "fill":
                    page.fill(selector, value)
                elif kind == "click":
                    page.click(selector)
                elif kind == "press":
                    page.press(selector or "body", value or "Enter")
                elif kind == "wait":
                    page.wait_for_timeout(int(value or 1000))
                elif kind == "goto":
                    page.goto(value, wait_until="domcontentloaded", timeout=60_000)
                payload["actions_done"].append(step)

            page.wait_for_timeout(600)
            payload["title"] = page.title()
            payload["final_url"] = page.url
            if scrape:
                text = page.inner_text("body")[:20_000]
                payload["text"] = text
                task.log("info", f"scraped {len(text)} chars")
            if screenshot:
                page.screenshot(path=shot_path)
                task.log("info", "screenshot captured")
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return task.result("error", {"error": str(exc), **payload})

    preview = f"{BASE_URL}/previews/{shot_name}" if screenshot and os.path.exists(shot_path) else None
    return task.result("ok", payload, preview)
