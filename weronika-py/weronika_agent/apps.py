"""Open desktop apps (and sites) by name, on this computer, without the cloud brain.

"Open notepad", "open the calculator", "launch VS Code", "open Spotify and YouTube":
the orb sends the spoken names here and the worker starts them.

Nothing the user (or a web page) says is ever handed to a shell. A name can only
select one of these:

* an entry of the built-in list below, whose command is a fixed string
  (on Windows it is started with ``cmd /c start "" <fixed name>``);
* an app that is already in the system's own app list (the Start menu on Windows,
  Applications on macOS, the desktop entries on Linux), started the way that menu
  starts it;
* a site of the site registry, opened in the Weronika browser window;
* nothing, in which case the request is refused with a clear message and nothing
  is started.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote

from .site_registry import find_site, refusal_for, resolve_target
from .tasks import TaskError


MAX_APPS_PER_REQUEST = 5
MAX_TARGETS_PER_REQUEST = 10
APP_LIST_TTL_SECONDS = 120.0
_NAME_RE = re.compile(r"^[\w .+&'()#-]{1,60}$", re.UNICODE)
_NOISE_RE = re.compile(r"\b(?:the|my|app|application|program|software|desktop)\b", re.IGNORECASE)
_SKIP_ENTRY_RE = re.compile(r"uninstall|readme|read me|help|license|website|release notes|documentation", re.IGNORECASE)
_ADDRESS_RE = re.compile(r"^(?:https?://\S+|(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?)$", re.IGNORECASE)
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flash for the app-list query


class AppError(TaskError):
    """A desktop app could not be opened."""


# name -> how to start it on each system.
#   ("start", target)  Windows: cmd /c start "" target   (target is a fixed string)
#   ("uri", target)    hand a fixed URI to the system opener
#   ("app", name)      macOS: open -a name
#   ("bin", [names])   Linux: the first of these programs that is installed
_BUILT_IN: dict[str, dict[str, tuple[str, Any]]] = {
    "Notepad": {"win32": ("start", "notepad"), "darwin": ("app", "TextEdit"), "linux": ("bin", ["gedit", "gnome-text-editor", "kate", "mousepad", "xed"])},
    "Calculator": {"win32": ("start", "calc"), "darwin": ("app", "Calculator"), "linux": ("bin", ["gnome-calculator", "kcalc", "galculator", "xcalc"])},
    "Paint": {"win32": ("start", "mspaint"), "darwin": ("app", "Preview"), "linux": ("bin", ["drawing", "kolourpaint", "pinta", "gimp"])},
    "File Explorer": {"win32": ("start", "explorer"), "darwin": ("app", "Finder"), "linux": ("bin", ["nautilus", "dolphin", "thunar", "nemo", "pcmanfm"])},
    "Command Prompt": {"win32": ("start", "cmd"), "darwin": ("app", "Terminal"), "linux": ("bin", ["gnome-terminal", "konsole", "xfce4-terminal", "xterm"])},
    "PowerShell": {"win32": ("start", "powershell")},
    "Task Manager": {"win32": ("start", "taskmgr"), "darwin": ("app", "Activity Monitor"), "linux": ("bin", ["gnome-system-monitor", "ksysguard", "xfce4-taskmanager"])},
    "Settings": {"win32": ("uri", "ms-settings:"), "darwin": ("app", "System Settings"), "linux": ("bin", ["gnome-control-center", "systemsettings", "xfce4-settings-manager"])},
    "Control Panel": {"win32": ("start", "control")},
    "Snipping Tool": {"win32": ("uri", "ms-screenclip:"), "darwin": ("app", "Screenshot"), "linux": ("bin", ["gnome-screenshot", "spectacle", "xfce4-screenshooter"])},
    "Camera": {"win32": ("uri", "microsoft.windows.camera:"), "darwin": ("app", "Photo Booth"), "linux": ("bin", ["cheese", "snapshot", "kamoso"])},
    "Clock": {"win32": ("uri", "ms-clock:"), "darwin": ("app", "Clock"), "linux": ("bin", ["gnome-clocks", "kclock"])},
    "WordPad": {"win32": ("start", "write")},
    "Character Map": {"win32": ("start", "charmap")},
    "On-Screen Keyboard": {"win32": ("start", "osk")},
    "Magnifier": {"win32": ("start", "magnify")},
    # These names are also Google sites ("open calendar" means Google Calendar), so the
    # desktop version opens only when the request says "app": "open the calendar app".
    "Photos": {"win32": ("uri", "ms-photos:"), "darwin": ("app", "Photos"), "linux": ("bin", ["eog", "gwenview", "shotwell"])},
    "Calendar": {"win32": ("uri", "outlookcal:"), "darwin": ("app", "Calendar"), "linux": ("bin", ["gnome-calendar", "korganizer"])},
    "Mail": {"win32": ("uri", "outlookmail:"), "darwin": ("app", "Mail"), "linux": ("bin", ["thunderbird", "geary", "evolution"])},
    "Maps": {"win32": ("uri", "bingmaps:"), "darwin": ("app", "Maps"), "linux": ("bin", ["gnome-maps", "marble"])},
    "Microsoft Store": {"win32": ("uri", "ms-windows-store:"), "darwin": ("app", "App Store"), "linux": ("bin", ["gnome-software", "plasma-discover"])},
}

# What people say -> the name used above or in the system's app list.
APP_ALIASES: dict[str, str] = {
    "calc": "Calculator", "calculator": "Calculator",
    "notepad": "Notepad", "text editor": "Notepad", "textedit": "Notepad",
    "paint": "Paint", "ms paint": "Paint", "mspaint": "Paint",
    "explorer": "File Explorer", "file explorer": "File Explorer", "files": "File Explorer",
    "file manager": "File Explorer", "this pc": "File Explorer", "finder": "File Explorer",
    "cmd": "Command Prompt", "command prompt": "Command Prompt", "terminal": "Command Prompt", "console": "Command Prompt",
    "powershell": "PowerShell", "power shell": "PowerShell",
    "task manager": "Task Manager", "taskmgr": "Task Manager", "activity monitor": "Task Manager", "system monitor": "Task Manager",
    "settings": "Settings", "system settings": "Settings", "windows settings": "Settings", "pc settings": "Settings",
    "control panel": "Control Panel",
    "snipping tool": "Snipping Tool", "screenshot tool": "Snipping Tool",
    "camera": "Camera", "webcam": "Camera",
    "clock": "Clock", "alarm clock": "Clock",
    "wordpad": "WordPad", "character map": "Character Map",
    "on screen keyboard": "On-Screen Keyboard", "on-screen keyboard": "On-Screen Keyboard", "virtual keyboard": "On-Screen Keyboard",
    "magnifier": "Magnifier",
    "photos": "Photos", "calendar": "Calendar", "mail": "Mail", "maps": "Maps",
    "store": "Microsoft Store", "microsoft store": "Microsoft Store", "app store": "Microsoft Store",
    # Installed programs: the spoken name -> the name in the Start menu / Applications.
    "chrome": "Google Chrome", "google chrome": "Google Chrome",
    "edge": "Microsoft Edge", "microsoft edge": "Microsoft Edge",
    "firefox": "Firefox", "brave": "Brave", "opera": "Opera",
    "vs code": "Visual Studio Code", "vscode": "Visual Studio Code", "code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "word": "Word", "ms word": "Word", "microsoft word": "Word",
    "excel": "Excel", "ms excel": "Excel", "microsoft excel": "Excel",
    "powerpoint": "PowerPoint", "power point": "PowerPoint", "ppt": "PowerPoint",
    "outlook": "Outlook", "onenote": "OneNote", "one note": "OneNote",
    "teams": "Microsoft Teams", "ms teams": "Microsoft Teams",
    "vlc": "VLC media player", "vlc player": "VLC media player",
    "spotify": "Spotify", "whatsapp": "WhatsApp", "telegram": "Telegram", "discord": "Discord",
    "zoom": "Zoom", "steam": "Steam", "obs": "OBS Studio", "notion": "Notion", "slack": "Slack",
    "photoshop": "Adobe Photoshop", "premiere": "Adobe Premiere Pro", "blender": "Blender",
    "android studio": "Android Studio", "pycharm": "PyCharm", "postman": "Postman", "git bash": "Git Bash",
}

# Built-in names that are also sites: without the word "app" the site wins.
_SITE_FIRST = {"Photos", "Calendar", "Mail", "Maps", "Microsoft Store"}

# The chat apps Weronika reads and answers live in her own signed-in browser windows.
# "Open WhatsApp" shows that window (and is how the account is connected); the desktop
# program opens when the request says "app".
CHAT_WINDOWS = {
    "whatsapp": ("whatsapp", "WhatsApp", "scan the QR code with your phone"),
    "whatsapp web": ("whatsapp", "WhatsApp", "scan the QR code with your phone"),
    "telegram": ("telegram", "Telegram", "log in with your phone number"),
    "telegram web": ("telegram", "Telegram", "log in with your phone number"),
}


def clean_app_name(value: object) -> str:
    """The spoken name without filler words, or "" when it is not a usable name."""
    text = " ".join(str(value or "").split()).strip(" .!?,;:")
    text = " ".join(_NOISE_RE.sub(" ", text).split())
    return text if text and _NAME_RE.match(text) else ""


class SystemRunner:
    """The only place that starts programs. Tests replace it."""

    def spawn(self, argv: list[str]) -> None:
        subprocess.Popen(  # noqa: S603 - argv comes from the fixed table or the system's app list
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

    def run(self, argv: list[str], timeout: float = 15.0) -> int:
        return subprocess.run(  # noqa: S603
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        ).returncode

    def capture(self, argv: list[str], timeout: float = 15.0) -> str:
        kwargs: dict[str, Any] = {}
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = _NO_WINDOW
        result = subprocess.run(  # noqa: S603 - a fixed command, see _windows_start_apps
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            **kwargs,
        )
        return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else ""

    def start_file(self, target: str) -> None:
        os.startfile(target)  # type: ignore[attr-defined]  # noqa: S606 - Windows shell open, no command line

    def which(self, name: str) -> str | None:
        return shutil.which(name)


class AppLauncher:
    def __init__(
        self,
        platform: str | None = None,
        runner: SystemRunner | None = None,
        environ: dict[str, str] | None = None,
        app_dirs: Iterable[Path] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        raw = platform or sys.platform
        self.platform = "win32" if raw.startswith("win") else "darwin" if raw == "darwin" else "linux"
        self.runner = runner or SystemRunner()
        self._environ = dict(os.environ if environ is None else environ)
        self._app_dirs = [Path(path) for path in app_dirs] if app_dirs is not None else self._default_app_dirs()
        self._clock = clock
        self._cache: tuple[float, dict[str, tuple[str, str]]] | None = None

    # ------------------------------------------------------------- app list
    def _default_app_dirs(self) -> list[Path]:
        if self.platform == "win32":
            roots = [self._environ.get("PROGRAMDATA", ""), self._environ.get("APPDATA", "")]
            return [Path(root) / "Microsoft" / "Windows" / "Start Menu" / "Programs" for root in roots if root]
        if self.platform == "darwin":
            return [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]
        return [Path("/usr/share/applications"), Path.home() / ".local" / "share" / "applications"]

    def _windows_start_apps(self) -> dict[str, tuple[str, str]]:
        """Every Start-menu entry, Store apps included: name -> ("appid", id)."""
        try:
            raw = self.runner.capture(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress",
                ]
            )
            data = json.loads(raw) if raw.strip() else []
        except Exception:
            return {}
        entries = data if isinstance(data, list) else [data]
        found: dict[str, tuple[str, str]] = {}
        for entry in entries[:4000]:
            if not isinstance(entry, dict):
                continue
            name = " ".join(str(entry.get("Name") or "").split())
            app_id = str(entry.get("AppID") or "").strip()
            if name and app_id and len(app_id) <= 400 and not _SKIP_ENTRY_RE.search(name):
                found.setdefault(name, ("appid", app_id))
        return found

    def _scan_dirs(self) -> dict[str, tuple[str, str]]:
        pattern = {"win32": "*.lnk", "darwin": "*.app", "linux": "*.desktop"}[self.platform]
        found: dict[str, tuple[str, str]] = {}
        for root in self._app_dirs:
            try:
                paths = sorted(root.glob(pattern) if self.platform == "darwin" else root.rglob(pattern))
            except OSError:
                continue
            for path in paths[:4000]:
                name = self._display_name(path)
                if name and not _SKIP_ENTRY_RE.search(name):
                    found.setdefault(name, ("file", str(path)))
        return found

    def _display_name(self, path: Path) -> str:
        if self.platform != "linux":
            return path.stem
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:80]:
                if line.startswith("Name="):
                    return line[5:].strip()
        except OSError:
            return ""
        return path.stem

    def installed(self) -> dict[str, tuple[str, str]]:
        """Display name -> how the system starts it. Cached for a short while."""
        now = self._clock()
        if self._cache is not None and now - self._cache[0] < APP_LIST_TTL_SECONDS:
            return self._cache[1]
        found = self._scan_dirs()
        if self.platform == "win32":
            for name, entry in self._windows_start_apps().items():
                found.setdefault(name, entry)
        self._cache = (now, found)
        return found

    def _match_installed(self, wanted: str) -> tuple[str, tuple[str, str], str] | None:
        key = wanted.casefold()
        apps = self.installed()
        names = sorted(apps, key=lambda name: (len(name), name.casefold()))
        for name in names:
            if name.casefold() == key:
                return name, apps[name], "exact"
        for name in names:
            if name.casefold().startswith(key + " "):
                return name, apps[name], "exact"
        loose = [name for name in names if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", name.casefold())]
        if len(loose) == 1:
            return loose[0], apps[loose[0]], "loose"
        if len(loose) > 1:
            listed = ", ".join(loose[:4])
            raise AppError(f"Several apps match “{wanted}”: {listed}. Say the full name. Nothing was opened.")
        return None

    def resolve(self, name: object) -> dict[str, Any] | None:
        """How ``name`` would be opened, without opening it. None when it is unknown."""
        cleaned = clean_app_name(name)
        if not cleaned:
            return None
        wanted = APP_ALIASES.get(cleaned.casefold(), cleaned)
        for label, per_system in _BUILT_IN.items():
            if label.casefold() == wanted.casefold():
                spec = per_system.get(self.platform)
                if spec and (spec[0] != "bin" or any(self.runner.which(binary) for binary in spec[1])):
                    return {"name": label, "kind": spec[0], "target": spec[1], "match": "built-in"}
        match = self._match_installed(wanted)
        if match:
            return {"name": match[0], "kind": match[1][0], "target": match[1][1], "match": match[2]}
        return None

    def known(self, name: object) -> bool:
        try:
            return self.resolve(name) is not None
        except AppError:
            return False

    # ------------------------------------------------------------------- open
    def launch(self, plan: dict[str, Any]) -> None:
        kind, target = plan["kind"], plan["target"]
        try:
            if kind == "start":
                self.runner.spawn(["cmd", "/c", "start", "", target])
            elif kind == "uri":
                self.open_uri(target)
            elif kind == "app":
                if self.runner.run(["open", "-a", target]) != 0:
                    raise AppError(f"macOS could not open “{plan['name']}”.")
            elif kind == "bin":
                binary = next((path for path in map(self.runner.which, target) if path), None)
                if not binary:
                    raise AppError(f"“{plan['name']}” is not installed on this computer.")
                self.runner.spawn([binary])
            elif kind == "appid":
                self.runner.spawn(["explorer.exe", f"shell:AppsFolder\\{target}"])
            elif self.platform == "win32":
                self.runner.start_file(target)
            elif self.platform == "darwin":
                if self.runner.run(["open", target]) != 0:
                    raise AppError(f"macOS could not open “{plan['name']}”.")
            else:
                self.runner.spawn(["gtk-launch", Path(target).stem])
        except AppError:
            raise
        except Exception as exc:  # a missing program, a blocked launch
            raise AppError(f"Weronika could not start “{plan['name']}”: {str(exc)[:160]}") from exc

    def open_uri(self, uri: str) -> None:
        if self.platform == "win32":
            self.runner.start_file(uri)
        elif self.platform == "darwin":
            self.runner.spawn(["open", uri])
        else:
            self.runner.spawn(["xdg-open", uri])

    def plan(self, name: object) -> dict[str, Any]:
        plan = self.resolve(name)
        if plan is None:
            shown = " ".join(str(name).split())[:60]
            raise AppError(
                f"Weronika could not find an app called “{shown}” on this computer. "
                "Say its name as it appears in the Start menu. Nothing was opened."
            )
        return plan

    def open(self, names: list[str] | str) -> dict[str, Any]:
        """Open one or more apps. Either every name is found, or nothing is started."""
        raw = [names] if isinstance(names, str) else list(names or [])
        wanted = [str(value) for value in raw if str(value or "").strip()]
        if not wanted:
            raise AppError("Which app should Weronika open?")
        if len(wanted) > MAX_APPS_PER_REQUEST:
            raise AppError(f"Weronika opens up to {MAX_APPS_PER_REQUEST} apps at a time.")
        plans: list[dict[str, Any]] = []
        for name in wanted:
            plan = self.plan(name)
            if plan not in plans:
                plans.append(plan)
        for plan in plans:
            self.launch(plan)
        opened = [{"name": plan["name"], "kind": "app"} for plan in plans]
        label = ", ".join(entry["name"] for entry in opened)
        return {"opened": opened, "count": len(opened), "message": f"Opened {label} on this computer."}

    # ------------------------------------------------------------------ music
    def music(self, service: str, query: str, open_url: Callable[[str], str] | None = None) -> dict[str, Any]:
        """Show a song in Spotify. Pressing play stays with the user."""
        text = " ".join(str(query or "").split())[:120]
        if " ".join(str(service or "").split()).casefold() != "spotify":
            raise AppError("Weronika can hand a song to Spotify this way, not to other players yet.")
        if not text:
            raise AppError("Which song should Weronika look for on Spotify?")
        note = "Press play on the top result. Spotify does not let Weronika press play for you."
        if self.known("spotify"):
            try:
                self.open_uri(f"spotify:search:{quote(text, safe='')}")
            except Exception as exc:
                raise AppError(f"Weronika could not open Spotify: {str(exc)[:160]}") from exc
            return {"service": "spotify", "query": text, "where": "app", "message": f"Spotify is showing “{text}”. {note}"}
        if open_url is None:
            raise AppError("The Spotify app is not installed on this computer.")
        open_url(f"https://open.spotify.com/search/{quote(text, safe='')}")
        return {
            "service": "spotify",
            "query": text,
            "where": "browser",
            "message": f"The Spotify app is not installed, so Spotify’s web player is showing “{text}” in your browser. {note}",
        }


def _target(value: object) -> tuple[str, str]:
    kind = "auto"
    if isinstance(value, dict):
        kind = str(value.get("kind") or "auto").casefold()
        value = value.get("name")
    name = " ".join(str(value or "").split())[:120]
    if name.casefold().endswith(".exe"):  # "notepad.exe" is a program, not an address
        return name[:-4], "app"
    return name, kind if kind in {"auto", "app", "site"} else "auto"


class OpenService:
    """“Open X, Y and Z”: each name becomes a desktop app or a site, never a guess."""

    def __init__(self, sites, apps: AppLauncher, chat_window: Callable[[str], bool] | None = None) -> None:
        self.sites = sites
        self.apps = apps
        # chat_window("whatsapp") shows that app's own window; True = it waits for a sign-in.
        self.chat_window = chat_window

    def _decide(self, name: str, kind: str) -> tuple[str, Any]:
        refusal = refusal_for(name)
        if refusal:
            raise AppError(refusal)
        if kind == "app":
            return "app", self.apps.plan(name)
        chat = CHAT_WINDOWS.get(clean_app_name(name).casefold())
        if chat and kind == "auto" and self.chat_window is not None:
            return "chat", chat
        is_site = find_site(name) is not None or bool(_ADDRESS_RE.match(name))
        if kind == "site":
            resolve_target(name)  # raises with the registry's own message when unknown
            return "site", name
        plan = self.apps.resolve(name) if not _ADDRESS_RE.match(name) else None
        if plan and plan["match"] == "built-in" and not (is_site and plan["name"] in _SITE_FIRST):
            return "app", plan
        if plan and plan["match"] == "exact":
            return "app", plan
        if is_site:
            return "site", name
        if plan:
            return "app", plan
        raise AppError(
            f"Weronika does not know “{name[:60]}” as an app on this computer or as a site. "
            "Say the app’s name as it appears in the Start menu, or the site’s address. Nothing was opened."
        )

    def open(self, targets: list[Any] | str) -> dict[str, Any]:
        """Decide every name first; open only when all of them are known."""
        raw = [targets] if isinstance(targets, (str, dict)) else list(targets or [])
        wanted = [pair for pair in (_target(value) for value in raw) if pair[0]]
        if not wanted:
            raise AppError("What should Weronika open?")
        if len(wanted) > MAX_TARGETS_PER_REQUEST:
            raise AppError(f"Weronika opens up to {MAX_TARGETS_PER_REQUEST} things at a time.")
        decided = [self._decide(name, kind) for name, kind in wanted]
        plans: list[dict[str, Any]] = []
        site_names: list[str] = []
        chats: list[tuple[str, str, str]] = []
        for what, value in decided:
            if what == "app" and value not in plans:
                plans.append(value)
            elif what == "site" and value not in site_names:
                site_names.append(value)
            elif what == "chat" and value not in chats:
                chats.append(value)
        if len(plans) > MAX_APPS_PER_REQUEST:
            raise AppError(f"Weronika opens up to {MAX_APPS_PER_REQUEST} apps at a time.")

        opened: list[dict[str, str]] = []
        tabs: list[dict[str, str]] = []
        notes: list[str] = []
        for platform, label, how in chats:
            try:
                needs_sign_in = bool(self.chat_window(platform))
            except Exception as exc:
                raise AppError(str(exc) or f"Weronika could not open her {label} window.") from exc
            opened.append({"name": label, "kind": "chat"})
            notes.append(
                f"Opened {label} in Weronika’s own browser window. "
                + (
                    f"It is not signed in yet: {how} there once, and she can read and answer the chats you name."
                    if needs_sign_in
                    else "It is signed in, so she can read and answer the chats you name."
                )
            )
        if site_names:
            result = self.sites.open(site_names)
            tabs = list(result.get("opened") or [])
            opened.extend({"name": str(tab.get("name") or tab.get("url") or ""), "kind": "site"} for tab in tabs)
        for plan in plans:
            self.apps.launch(plan)
            opened.append({"name": plan["name"], "kind": "app"})

        apps_label = ", ".join(entry["name"] for entry in opened if entry["kind"] == "app")
        sites_label = ", ".join(entry["name"] for entry in opened if entry["kind"] == "site")
        parts = []
        if apps_label:
            parts.append(f"Opened {apps_label} on this computer.")
        if sites_label:
            parts.append(f"Opened {sites_label} in the Weronika browser window.")
        parts.extend(notes)
        return {"opened": opened, "tabs": tabs, "count": len(opened), "message": " ".join(parts)}
