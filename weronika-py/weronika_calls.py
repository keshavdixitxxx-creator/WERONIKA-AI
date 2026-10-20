"""WhatsApp call assistant preview.

WhatsApp does not offer a supported public API for answering voice calls.
This module only looks at a visible desktop window when Windows UI automation
exposes one, and it never clicks Accept unless the user explicitly confirms.

On this machine the detector reports available, unsupported, or
permission-required. It never pretends a call was answered.
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from typing import Callable

INCOMING_HINTS = (
    "incoming voice call",
    "incoming video call",
    "incoming call",
    "voice call from",
    "video call from",
)

ACCEPT_TITLES = re.compile(r"^(accept|answer|pick up)$", re.I)

LINUX_REASON = (
    "WhatsApp call detection is unsupported here because this is not Windows. "
    "WhatsApp has no supported public API for answering voice calls, so this "
    "preview needs a visible WhatsApp Desktop window exposed by Windows UI "
    "automation. No call was answered."
)


def sanitize_address(raw: str | None) -> str:
    text = re.sub(r"[\x00-\x1f<>{}]", "", raw or "")
    text = re.sub(r"\s+", " ", text).strip()[:40]
    return text or "Commander"


def prompt_for(address_name: str | None, lang: str | None) -> str:
    title = sanitize_address(address_name)
    if (lang or "").lower().startswith("hi"):
        return f"क्या मैं कॉल उठाकर बातचीत संभाल लूँ, {title}?"
    return f"May I pick up and handle the conversation, {title}?"


def capability_report(platform: str | None = None) -> dict:
    plat = platform or ("windows" if os.name == "nt" else os.name)
    if plat != "windows" and os.name != "nt":
        return {
            "state": "unsupported",
            "platform": plat,
            "reason": LINUX_REASON,
        }
    try:
        import pywinauto  # noqa: F401
    except Exception:
        return {
            "state": "permission-required",
            "platform": "windows",
            "reason": (
                "Windows can see desktop windows, but pywinauto is not installed, "
                "so incoming-call text and the Accept button are not exposed. "
                "Install it with pip install pywinauto and allow UI Automation. "
                "No call was answered."
            ),
        }
    return {
        "state": "available",
        "platform": "windows",
        "reason": (
            "Detector can read visible WhatsApp windows through UI Automation. "
            "A call is answered only after explicit approval, and only if an "
            "Accept control is exposed."
        ),
    }


def _enum_titles_windows() -> list[str]:
    titles: list[str] = []
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return titles
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if title:
            titles.append(title)
        return True

    user32.EnumWindows(_cb, 0)
    return titles


def scan_platform() -> dict:
    """Read-only scan. Never clicks, never answers."""
    report = capability_report()
    if report["state"] == "unsupported":
        return {
            "supported": False,
            "capability": "unsupported",
            "detected": False,
            "window": None,
            "reason": report["reason"],
        }
    if os.name != "nt":
        return {
            "supported": False,
            "capability": "unsupported",
            "detected": False,
            "window": None,
            "reason": LINUX_REASON,
        }

    titles = _enum_titles_windows()
    incoming = [title for title in titles if any(hint in title.lower() for hint in INCOMING_HINTS)]
    whatsapp = [title for title in titles if "whatsapp" in title.lower()]

    if report["state"] == "permission-required":
        if incoming:
            return {
                "supported": False,
                "capability": "permission-required",
                "detected": True,
                "window": incoming[0],
                "reason": (
                    f"A window titled {incoming[0]!r} looks like an incoming call, "
                    "but Accept cannot be clicked without pywinauto. No call was answered."
                ),
            }
        if whatsapp:
            return {
                "supported": False,
                "capability": "permission-required",
                "detected": False,
                "window": whatsapp[0],
                "reason": (
                    "WhatsApp is visible, but incoming-call text is not exposed without "
                    "UI Automation. No call was answered."
                ),
            }
        return {
            "supported": False,
            "capability": "permission-required",
            "detected": False,
            "window": None,
            "reason": report["reason"],
        }

    # pywinauto is installed. Prefer its text, fall back to titles.
    try:
        from pywinauto import Desktop  # noqa: PLC0415

        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            try:
                title = win.window_text() or ""
            except Exception:
                continue
            blob = title.lower()
            try:
                blob += " " + " ".join(win.texts()[:12]).lower()
            except Exception:
                pass
            if any(hint in blob for hint in INCOMING_HINTS) or (
                "whatsapp" in blob and "incoming" in blob
            ):
                return {
                    "supported": True,
                    "capability": "available",
                    "detected": True,
                    "window": title or "WhatsApp",
                    "reason": "A visible incoming-call window was exposed by UI Automation. Nothing was clicked.",
                }
    except Exception as exc:
        return {
            "supported": False,
            "capability": "permission-required",
            "detected": False,
            "window": None,
            "reason": f"UI Automation could not be read ({exc}). No call was answered.",
        }

    return {
        "supported": True,
        "capability": "available",
        "detected": False,
        "window": None,
        "reason": "No visible incoming WhatsApp call. Nothing was answered.",
    }


def attempt_answer(window: str | None) -> dict:
    """Click Accept only when the control is actually exposed. Never guesses."""
    if os.name != "nt":
        return {
            "answered": False,
            "status": "unsupported",
            "reason": LINUX_REASON,
        }
    try:
        from pywinauto import Desktop  # noqa: PLC0415
    except Exception:
        return {
            "answered": False,
            "status": "permission-required",
            "reason": (
                "pywinauto is not installed, so the Accept button cannot be clicked. "
                "The call was not answered."
            ),
        }
    try:
        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            title = ""
            try:
                title = win.window_text() or ""
            except Exception:
                title = ""
            if window and window not in title and "whatsapp" not in title.lower() and "call" not in title.lower():
                continue
            try:
                button = win.child_window(title_re=ACCEPT_TITLES.pattern, control_type="Button")
                if not button.exists(timeout=0.6):
                    continue
                button.click_input()
                return {
                    "answered": True,
                    "status": "handling",
                    "reason": (
                        "Accept was clicked through Windows UI automation. "
                        "WhatsApp does not expose call audio routing, so listening and speaking "
                        "hooks may not reach the caller."
                    ),
                }
            except Exception:
                continue
    except Exception as exc:
        return {
            "answered": False,
            "status": "error",
            "reason": f"Could not operate the call window: {exc}. The call was not answered.",
        }
    return {
        "answered": False,
        "status": "error",
        "reason": "The Accept control was not exposed. The call was not answered.",
    }


class CallAssistant:
    def __init__(
        self,
        scanner: Callable[[], dict] | None = None,
        answerer: Callable[[str | None], dict] | None = None,
        platform: str | None = None,
    ) -> None:
        self._scanner = scanner or scan_platform
        self._answerer = answerer or attempt_answer
        self._platform = platform
        self._lock = threading.Lock()
        self.events: list[dict] = []
        self.state = {
            "state": "idle",
            "capability": capability_report(platform)["state"],
            "platform": "windows" if (platform == "windows" or os.name == "nt") else (platform or os.name),
            "window": None,
            "address_name": "Commander",
            "lang": "en",
            "prompt": None,
            "approved": False,
            "answered": False,
            "simulated": False,
            "reason": capability_report(platform)["reason"],
            "event_id": None,
        }

    def _emit(self, level: str, message: str, **extra) -> dict:
        entry = {
            "id": uuid.uuid4().hex[:10],
            "task_id": "call",
            "level": level,
            "message": message,
            "ts": round(time.time(), 3),
            **extra,
        }
        self.events = (self.events + [entry])[-80:]
        try:
            from weronika_automation import BUS  # noqa: PLC0415

            BUS.emit("call", level, message, **extra)
        except Exception:
            pass
        return entry

    def set_identity(self, address_name: str | None, lang: str | None) -> None:
        with self._lock:
            if address_name:
                self.state["address_name"] = sanitize_address(address_name)
            if lang:
                self.state["lang"] = str(lang)[:8]
            if self.state["state"] == "awaiting_approval":
                self.state["prompt"] = prompt_for(self.state["address_name"], self.state["lang"])

    def status(self) -> dict:
        with self._lock:
            payload = dict(self.state)
        payload["events"] = self.events[-12:]
        payload["answered"] = bool(payload.get("answered"))
        return payload

    def detect(self) -> dict:
        scan = self._scanner()
        with self._lock:
            self.state["capability"] = scan.get("capability") or self.state["capability"]
            self.state["reason"] = scan.get("reason") or ""
            self.state["simulated"] = bool(scan.get("simulated"))
            detected = bool(scan.get("detected"))
            window = scan.get("window")
            previous = self.state["state"]
            if detected and scan.get("capability") in ("available", "permission-required"):
                if previous not in ("awaiting_approval", "approved", "handling"):
                    self.state["state"] = "awaiting_approval"
                    self.state["window"] = window
                    self.state["approved"] = False
                    self.state["answered"] = False
                    self.state["prompt"] = prompt_for(self.state["address_name"], self.state["lang"])
                    self.state["event_id"] = uuid.uuid4().hex[:10]
                    self._emit(
                        "prompt",
                        self.state["prompt"],
                        state="awaiting_approval",
                        window=window,
                        capability=self.state["capability"],
                    )
                elif window:
                    self.state["window"] = window
            elif previous == "awaiting_approval" and not detected:
                self.state["state"] = "idle"
                self.state["window"] = None
                self.state["prompt"] = None
                self.state["answered"] = False
                self._emit("info", "The incoming-call window is no longer visible. Nothing was answered.", state="idle")
            elif scan.get("capability") == "unsupported" and previous in ("idle", "unsupported"):
                self.state["state"] = "unsupported"
                self.state["answered"] = False
                self.state["window"] = None
            elif previous == "idle":
                self.state["window"] = window
            snapshot = dict(self.state)
        snapshot["events"] = self.events[-12:]
        return snapshot

    def approve(self, confirm: bool = False) -> dict:
        if confirm is not True:
            return {
                "ok": False,
                "answered": False,
                "status": "needs_confirmation",
                "state": self.state["state"],
                "reason": "Set confirm to true to approve pickup. The call was not answered.",
            }
        with self._lock:
            if self.state["state"] != "awaiting_approval":
                return {
                    "ok": False,
                    "answered": False,
                    "status": self.state["capability"] if self.state["capability"] != "available" else "idle",
                    "state": self.state["state"],
                    "reason": self.state["reason"] or "There is no incoming call waiting for approval. Nothing was answered.",
                }
            if self.state["capability"] != "available":
                reason = self.state["reason"] or "Call pickup is not available. The call was not answered."
                self._emit("error", reason, state=self.state["state"])
                return {
                    "ok": False,
                    "answered": False,
                    "status": self.state["capability"],
                    "state": self.state["state"],
                    "reason": reason,
                }
            window = self.state["window"]
            self.state["approved"] = True
            self.state["state"] = "approved"
        result = self._answerer(window)
        answered = bool(result.get("answered"))
        with self._lock:
            self.state["answered"] = answered
            self.state["state"] = "handling" if answered else "error"
            self.state["reason"] = result.get("reason") or ""
            self._emit(
                "info" if answered else "error",
                self.state["reason"],
                state=self.state["state"],
                answered=answered,
            )
            snapshot = dict(self.state)
        snapshot.update({"ok": answered, "answered": answered, "status": snapshot["state"]})
        return snapshot

    def decline(self) -> dict:
        with self._lock:
            self.state["state"] = "idle"
            self.state["approved"] = False
            self.state["answered"] = False
            self.state["prompt"] = None
            self.state["window"] = None
            self.state["reason"] = "Declined. The call was not answered."
            self._emit("info", self.state["reason"], state="idle", answered=False)
            snapshot = dict(self.state)
        snapshot["answered"] = False
        return snapshot

    def listen(self) -> dict:
        with self._lock:
            handling = self.state["state"] == "handling" and self.state["answered"]
            capability = self.state["capability"]
        if not handling:
            return {
                "status": "idle",
                "listening": False,
                "answered": False,
                "reason": "Listening starts only after you approve a detected call. Nothing is being recorded.",
            }
        if capability != "available" or os.name != "nt":
            return {
                "status": "unsupported",
                "listening": False,
                "answered": True,
                "reason": (
                    "The call may be open, but this machine cannot attach to WhatsApp's call audio. "
                    "No recording was started."
                ),
            }
        return {
            "status": "hook_ready",
            "listening": False,
            "answered": True,
            "reason": (
                "Listening hook is ready, but WhatsApp does not expose call audio. "
                "This preview does not record the caller. Route the headset yourself if you want to hear them."
            ),
        }

    def speak(self, text: str) -> dict:
        phrase = (text or "").strip()
        if not phrase:
            return {"status": "error", "spoken": False, "routed_to_call": False, "reason": "Nothing to say."}
        with self._lock:
            handling = self.state["state"] == "handling" and self.state["answered"]
        if not handling:
            return {
                "status": "error",
                "spoken": False,
                "routed_to_call": False,
                "answered": False,
                "reason": "No approved call is in progress. Nothing was spoken into a call.",
            }
        if os.name != "nt":
            self._emit("error", "Speaking hook is unsupported on this platform.", state="handling")
            return {
                "status": "unsupported",
                "spoken": False,
                "routed_to_call": False,
                "answered": True,
                "reason": "Speaking into a WhatsApp call is unsupported off Windows. Nothing was played.",
            }
        try:
            import subprocess  # noqa: PLC0415

            safe = phrase.replace("'", "''")[:500]
            subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Add-Type -AssemblyName System.Speech; "
                    f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe}')",
                ]
            )
        except Exception as exc:
            return {
                "status": "unsupported",
                "spoken": False,
                "routed_to_call": False,
                "answered": True,
                "reason": f"The speaking hook could not start ({exc}). Nothing was sent to the caller.",
            }
        self._emit("info", "Played speech on the default output. Call routing is not guaranteed.", state="handling")
        return {
            "status": "played_locally",
            "spoken": True,
            "routed_to_call": False,
            "answered": True,
            "reason": (
                "Speech was played on the default output. WhatsApp does not expose a way to inject "
                "audio into the call, so the caller may not hear it."
            ),
        }


ASSISTANT = CallAssistant()


def feature_status() -> dict:
    report = capability_report()
    current = ASSISTANT.status()
    return {
        "state": report["state"],
        "call_state": current["state"],
        "platform": report["platform"],
        "reason": current.get("reason") or report["reason"],
        "answered": False if current["state"] != "handling" else current.get("answered", False),
    }
