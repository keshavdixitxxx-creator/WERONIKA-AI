"""Local, visible-browser workflows for Weronika's signed-in apps.

This module uses a dedicated persistent Playwright profile and normal web UIs.
It does not use app APIs, OAuth, or stored app passwords. The user signs in in
that visible browser profile. All DOM text returned by this module is private;
callers must keep it on the local agent and use the local-only Ollama route.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

APPS: dict[str, dict[str, Any]] = {
    "gmail": {"url": "https://mail.google.com/mail/u/0/#inbox", "kind": "mail"},
    "outlook": {"url": "https://outlook.live.com/mail/0/inbox", "kind": "mail"},
    "instagram": {"url": "https://www.instagram.com/direct/inbox/", "kind": "chat"},
    "telegram": {"url": "https://web.telegram.org/k/", "kind": "chat"},
    "whatsapp": {"url": "https://web.whatsapp.com/", "kind": "chat"},
    "google_calendar": {"url": "https://calendar.google.com/calendar/u/0/r/week", "kind": "calendar"},
    "microsoft_calendar": {"url": "https://outlook.live.com/calendar/0/view/week", "kind": "calendar"},
    "spotify": {"url": "https://open.spotify.com/", "kind": "media"},
    "youtube": {"url": "https://www.youtube.com/", "kind": "media"},
}

APP_ALIASES = {
    "google calendar": "google_calendar",
    "google_calendar": "google_calendar",
    "gcal": "google_calendar",
    "calendar": "google_calendar",
    "microsoft calendar": "microsoft_calendar",
    "outlook calendar": "microsoft_calendar",
    "microsoft_calendar": "microsoft_calendar",
    "ms calendar": "microsoft_calendar",
    "outlook": "outlook",
    "hotmail": "outlook",
    "youtube music": "youtube",
}

MAX_APP_TEXT_CHARS = 60_000
MAX_MESSAGE_CHARS = 10_000
PENDING_TTL_SECONDS = 180
FAMILY_DEFAULT_TERMS = (
    "mom", "mother", "mum", "dad", "father", "sister", "brother",
    "wife", "husband", "son", "daughter", "family", "माँ", "पापा", "परिवार",
)


class AppAutomationError(RuntimeError):
    """A safe, user-displayable local browser automation error."""


def normalize_app(value: object) -> str:
    key = re.sub(r"\s+", " ", str(value or "").strip().lower().replace("-", " "))
    app = APP_ALIASES.get(key, key.replace(" ", "_"))
    if app not in APPS:
        raise ValueError("Choose one of the supported apps: Gmail, Outlook, Instagram, Telegram, WhatsApp, Google Calendar, Microsoft Calendar, Spotify, or YouTube.")
    return app


def _bounded_text(value: object, label: str, limit: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > limit:
        raise ValueError(f"{label} is too long (maximum {limit} characters)")
    return text


def _safe_datetime(value: object, tz_name: object) -> datetime:
    raw = _bounded_text(value, "event date/time", 80)
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Use an ISO date/time such as 2026-10-17T15:00") from exc
    if result.tzinfo is None:
        zone_name = str(tz_name or "UTC")[:80]
        try:
            result = result.replace(tzinfo=ZoneInfo(zone_name))
        except ZoneInfoNotFoundError as exc:
            raise ValueError("The browser supplied an unknown time zone") from exc
    return result


def _format_google_dates(start: datetime, end: datetime) -> str:
    return f"{start.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}/{end.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"


def _compact_visible_text(text: object, limit: int = MAX_APP_TEXT_CHARS) -> str:
    value = str(text or "").replace("\x00", "")
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value[:limit]


def _line_delta(previous: str, current: str) -> str:
    old_lines = {line.strip() for line in previous.splitlines() if line.strip()}
    new_lines = [line.strip() for line in current.splitlines() if line.strip() and line.strip() not in old_lines]
    return "\n".join(new_lines[-35:])[:5_000]


class LocalAppBrowser:
    """A single-threaded, persistent headed browser controlled by local requests."""

    def __init__(self, profile_dir: str | None = None) -> None:
        self.profile_dir = profile_dir or os.environ.get(
            "WERONIKA_BROWSER_PROFILE", os.path.join(os.path.expanduser("~"), ".weronika", "app-browser-profile")
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="weronika-app-browser")
        self._playwright = None
        self._context = None
        self._pages: dict[str, Any] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []
        self._events_lock = threading.Lock()
        self._watch_config: dict[str, Any] | None = None
        self._watch_stop = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._snapshots: dict[str, str] = {}
        self._active_call_alerts: set[str] = set()
        self._closed = False

    def _submit(self, callback, timeout: int = 90):
        if self._closed:
            raise AppAutomationError("The local app browser is shutting down. Restart Weronika's local agent.")
        try:
            return self._executor.submit(callback).result(timeout=timeout)
        except FutureTimeout as exc:
            raise AppAutomationError("The browser is taking too long. It remains open; check the local app window and retry.") from exc

    def _ensure_context(self):
        if self._context is not None:
            try:
                if self._context.pages is not None:
                    return self._context
            except Exception:
                self._context = None
                self._pages.clear()
        # Same-browser CDP mode: if user started Chrome with --remote-debugging-port=9222, connect to it
        cdp_endpoint = (__import__("os").environ.get("WERONIKA_CDP_ENDPOINT") or __import__("os").environ.get("WERONIKA_SAME_BROWSER_ENDPOINT") or "")
        same_browser = __import__("os").environ.get("WERONIKA_SAME_BROWSER") in ("1","true","yes") or bool(cdp_endpoint)
        if same_browser:
            try:
                from playwright.sync_api import sync_playwright  # noqa: PLC0415
                import requests as _req
                ep = cdp_endpoint or "http://127.0.0.1:9222"
                try:
                    # quick probe
                    _req.get(ep + "/json/version", timeout=1.5)
                except Exception:
                    pass
                self._playwright = sync_playwright().start()
                # try CDP
                try:
                    browser = self._playwright.chromium.connect_over_cdp(ep)
                    self._context = browser.contexts[0] if browser.contexts else browser.new_context(viewport={"width": 1440, "height": 960})
                    self._context.set_default_timeout(8_000)
                    self._context.set_default_navigation_timeout(60_000)
                    return self._context
                except Exception as _cdp_err:
                    try:
                        self._playwright.stop()
                    except Exception:
                        pass
                    self._playwright = None
                    # fall through to persistent profile fallback; frontend same-tab also works
                    print(f"[weronika] CDP connect failed ({_cdp_err}), using fallback profile. For same-browser direct control, start Chrome with --remote-debugging-port=9222")
            except Exception:
                pass
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            raise AppAutomationError("Signed-in app automation needs Playwright. Install it with: pip install playwright && python -m playwright install chromium. Or use same-browser mode: just keep your normal Chrome open — Weronika will open new tabs there (no separate install needed).") from exc
        # User prefers same-browser (new tab in current browser) - don't launch separate chrome test.
        # Only launch fallback if explicitly allowed via WERONIKA_ALLOW_FALLBACK_CHROMIUM=1
        import os as _os
        if _os.environ.get("WERONIKA_ALLOW_FALLBACK_CHROMIUM") != "1":
            raise AppAutomationError("Same-browser mode is active — I open new tabs in your current browser instead of a separate chrome test. To enable local Chromium fallback, set WERONIKA_ALLOW_FALLBACK_CHROMIUM=1 and restart. Meanwhile, your current browser tab will handle Telegram/WhatsApp/YouTube/Spotify just fine — check the new tab I opened for you.")
        os.makedirs(self.profile_dir, exist_ok=True)
        self._playwright = sync_playwright().start()
        try:
            self._context = self._playwright.chromium.launch_persistent_context(
                self.profile_dir,
                headless=False,
                viewport={"width": 1440, "height": 960},
                accept_downloads=False,
                args=["--no-first-run", "--disable-session-crashed-bubble"],
            )
            self._context.set_default_timeout(8_000)
            self._context.set_default_navigation_timeout(60_000)
        except Exception as exc:  # noqa: BLE001
            try:
                self._playwright.stop()
            except Exception:  # noqa: BLE001
                pass
            self._playwright = None
            self._context = None
            raise AppAutomationError(f"Could not start the local Chromium profile: {exc}") from exc
        return self._context

    def _page(self, app: str):
        context = self._ensure_context()
        page = self._pages.get(app)
        if page is not None:
            try:
                if not page.is_closed():
                    return page
            except Exception:
                pass
        pages = context.pages
        page = pages[0] if pages and not self._pages else context.new_page()
        page.set_default_timeout(8_000)
        page.set_default_navigation_timeout(60_000)
        self._pages[app] = page
        return page

    @staticmethod
    def _navigate(page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass

    def _app_page(self, app: str, navigate: bool = False):
        page = self._page(app)
        expected_url = APPS[app]["url"]
        current = page.url or ""
        if navigate or current in ("", "about:blank"):
            self._navigate(page, expected_url)
        else:
            host = current.lower().split("/", 3)[2] if "://" in current else ""
            expected_host = expected_url.lower().split("/", 3)[2]
            # A login redirect may use an identity-provider hostname. Keep it
            # open so the user can sign in; do not silently navigate away.
            if host not in {expected_host, "accounts.google.com", "login.live.com", "login.microsoftonline.com"}:
                self._navigate(page, expected_url)
        return page

    @staticmethod
    def _body_text(page) -> str:
        try:
            return _compact_visible_text(page.locator("body").inner_text(timeout=8_000))
        except Exception:
            return ""

    @staticmethod
    def _requires_sign_in(app: str, page, text: str) -> bool:
        url = (page.url or "").lower()
        lower = text.lower()
        if app in {"gmail", "google_calendar"} and "accounts.google.com" in url:
            return True
        if app in {"outlook", "microsoft_calendar"} and any(host in url for host in ("login.live.com", "login.microsoftonline.com")):
            return True
        if app == "instagram" and "/accounts/login" in url:
            return True
        if app == "telegram" and ("/auth" in url or "log in by phone number" in lower):
            return True
        if app == "whatsapp" and any(phrase in lower for phrase in ("scan the qr code", "link with phone number", "use whatsapp on your phone")):
            return True
        if app == "spotify" and "log in to spotify" in lower:
            return True
        return False

    @staticmethod
    def _locator_text(page, selector: str, max_items: int = 50) -> list[str]:
        try:
            rows = page.locator(selector)
            count = min(rows.count(), max_items)
            found = []
            for index in range(count):
                try:
                    item = _compact_visible_text(rows.nth(index).inner_text(timeout=1_500), 2_000)
                    if item:
                        found.append(item)
                except Exception:
                    continue
            return found
        except Exception:
            return []

    def _mail_rows(self, page, selector: str, app: str) -> list[str]:
        try:
            rows = page.locator(selector)
            count = min(rows.count(), 60)
        except Exception:
            return []
        output = []
        for index in range(count):
            row = rows.nth(index)
            try:
                text = _compact_visible_text(row.inner_text(timeout=1_500), 2_000)
                if not text:
                    continue
                class_name = (row.get_attribute("class") or "").lower()
                aria = (row.get_attribute("aria-label") or "").lower()
                unread = (app == "gmail" and "ze" in class_name.split()) or "unread" in class_name or "unread" in aria
                output.append(f"{'UNREAD' if unread else 'VISIBLE'}: {text}")
            except Exception:
                continue
        return output

    def _read_content(self, app: str, page) -> tuple[str, str]:
        if app == "gmail":
            rows = self._mail_rows(page, "tr.zA", app)
            if rows:
                return "VISIBLE GMAIL MESSAGE ROWS (latest visible first):\n" + "\n---\n".join(rows), "gmail-message-rows"
        if app == "outlook":
            rows = self._mail_rows(page, "[role='option']", app)
            if rows:
                return "VISIBLE OUTLOOK ITEMS:\n" + "\n---\n".join(rows), "outlook-list-items"
        if app == "whatsapp":
            side = self._locator_text(page, "#pane-side", 1)
            main = self._locator_text(page, "#main", 1)
            if side or main:
                return "RECENT WHATSAPP CHATS:\n" + (side[0] if side else "") + "\n\nOPEN CHAT:\n" + (main[0] if main else ""), "whatsapp-visible-chats"
        if app == "telegram":
            left = self._locator_text(page, "#column-left", 1)
            center = self._locator_text(page, "#column-center", 1)
            if left or center:
                return "RECENT TELEGRAM CHATS/CHANNELS:\n" + (left[0] if left else "") + "\n\nOPEN CHAT/CHANNEL:\n" + (center[0] if center else ""), "telegram-visible-chats"
        if app == "instagram":
            main = self._locator_text(page, "main", 1)
            if main:
                return main[0], "instagram-current-view"
        if app in {"google_calendar", "microsoft_calendar"}:
            main = self._locator_text(page, "main", 1)
            if main:
                return main[0], "calendar-visible-view"
        if app == "spotify":
            main = self._locator_text(page, "main", 1)
            if main:
                return main[0], "spotify-visible-view"
        return self._body_text(page), "visible-page-text"

    def _open(self, app: str) -> dict[str, Any]:
        page = self._app_page(app, navigate=True)
        text = self._body_text(page)
        login = self._requires_sign_in(app, page, text)
        return {
            "ok": True,
            "app": app,
            "url": page.url,
            "title": page.title(),
            "requires_sign_in": login,
            "message": "Sign in manually in the opened browser window, then ask again." if login else "App opened in Weronika's persistent local browser profile.",
        }

    def _select_chat_target(self, app: str, page, target: str) -> None:
        target = _bounded_text(target, "chat or channel name", 120)
        selectors = {
            "whatsapp": "#pane-side [role='row'], #pane-side [data-testid='cell-frame-container'], #pane-side [title]",
            "telegram": "#column-left [role='listitem'], #column-left [role='button'], #column-left button, #column-left [title]",
            "instagram": "main [role='listitem'], main a[href*='/direct/t/']",
        }
        rows = page.locator(selectors[app])
        try:
            count = min(rows.count(), 100)
        except Exception:
            count = 0
        for index in range(count):
            row = rows.nth(index)
            try:
                visible_text = _compact_visible_text(row.inner_text(timeout=1_000), 1_500)
                title = row.get_attribute("title") or ""
                accessible = row.get_attribute("aria-label") or ""
                if target.lower() not in f"{visible_text} {title} {accessible}".lower():
                    continue
                row.click(timeout=4_000)
                page.wait_for_timeout(350)
                return
            except Exception:
                continue
        raise AppAutomationError(f"Couldn't find a visible chat/channel named {target!r}. No message was opened or sent.")

    def _active_chat_target(self, app: str, page) -> str:
        selectors = {
            "whatsapp": "#main header",
            "telegram": "#column-center header",
            "instagram": "main h1, main h2",
        }
        selector = selectors.get(app)
        if not selector:
            return ""
        labels = self._locator_text(page, selector, 1)
        return labels[0][:180] if labels else ""

    def _read(self, app: str, target: str = "") -> dict[str, Any]:
        page = self._app_page(app)
        text = self._body_text(page)
        if self._requires_sign_in(app, page, text):
            return {"ok": False, "app": app, "requires_sign_in": True, "error": "Sign in manually in the opened local browser, then retry. No page content was processed."}
        if target and APPS[app]["kind"] == "chat":
            self._select_chat_target(app, page, target)
        content, source = self._read_content(app, page)
        content = _compact_visible_text(content)
        if not content:
            return {"ok": False, "app": app, "error": "No readable visible app content was found. Open the inbox/chat/calendar in the local browser and retry."}
        return {
            "ok": True,
            "app": app,
            "source": source,
            "url": page.url,
            "title": page.title(),
            "content": content,
            "active_target": self._active_chat_target(app, page),
            "characters": len(content),
            "note": "Visible UI text only; processed on this PC.",
        }

    @staticmethod
    def _first_visible(locators):
        for locator in locators:
            try:
                count = locator.count()
                for index in range(min(count, 5)):
                    candidate = locator.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                continue
        return None

    def _click_named_button(self, page, labels: list[str]):
        import re as _re
        for label in labels:
            try:
                locator = page.get_by_role("button", name=_re.compile(label, _re.I))
                item = self._first_visible([locator])
                if item is not None:
                    item.click(timeout=4_000)
                    return True
            except Exception:
                continue
        return False

    def _media_play(self, app: str, query: str) -> dict[str, Any]:
        query = _bounded_text(query, "track or video search", 200)
        page = self._page(app)
        if app == "spotify":
            self._navigate(page, f"https://open.spotify.com/search/{quote(query, safe='')}")
            if self._requires_sign_in(app, page, self._body_text(page)):
                return {"ok": False, "app": app, "requires_sign_in": True, "error": "Sign in to Spotify in the opened local browser, then retry."}
            track_link = self._first_visible([page.locator('a[href*="/track/"]')])
            title = ""
            if track_link is not None:
                try:
                    title = _compact_visible_text(track_link.inner_text(timeout=2_000), 300)
                    track_link.click(timeout=5_000)
                    page.wait_for_timeout(700)
                except Exception:
                    track_link = None
            play = self._first_visible([
                page.locator('button[data-testid="play-button"]'),
                page.locator('button[aria-label*="Play"]'),
            ])
            played = False
            if play is not None:
                try:
                    play.click(timeout=4_000)
                    played = True
                except Exception:
                    pass
            return {"ok": True, "app": app, "query": query, "title": title or query, "played": played,
                    "message": "Playback started." if played else "Search results are open; choose a track or sign in to start playback."}

        self._navigate(page, f"https://www.youtube.com/results?{urlencode({'search_query': query})}")
        result = self._first_visible([
            page.locator("ytd-video-renderer a#video-title"),
            page.locator('a[href*="/watch?v="]'),
        ])
        title = ""
        if result is None:
            return {"ok": False, "app": app, "query": query, "error": "No visible YouTube search result was found."}
        try:
            title = _compact_visible_text(result.inner_text(timeout=2_000), 300)
            result.click(timeout=5_000)
            page.wait_for_timeout(1_500)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "app": app, "query": query, "error": f"Could not open the first visible result: {exc}"}
        play_button = self._first_visible([page.locator("button.ytp-play-button")])
        played = False
        if play_button is not None:
            try:
                label = (play_button.get_attribute("aria-label") or "").lower()
                if "play" in label and "pause" not in label:
                    play_button.click(timeout=3_000)
                played = True
            except Exception:
                pass
        return {"ok": True, "app": app, "query": query, "title": title or page.title(), "url": page.url,
                "played": played, "message": "Video opened." if played else "Video opened; press Play in the local browser if it did not start."}

    def _email_compose(self, app: str, page, mode: str, recipient: str, subject: str, body: str) -> tuple[str, str]:
        import re as _re
        if mode == "new":
            if not recipient:
                raise ValueError("A recipient is required to compose a new email")
            opened = self._click_named_button(page, [r"^compose$", r"new mail", r"new message"])
            if not opened:
                raise AppAutomationError("Could not find the app's Compose/New mail button. Open the mail app and retry.")
            if app == "gmail":
                to = self._first_visible([
                    page.locator('input[name="to"]'), page.locator('textarea[name="to"]'),
                    page.locator('input[aria-label*="To recipients"]'), page.get_by_role("textbox", name=_re.compile(r"To recipients", _re.I)),
                ])
            else:
                to = self._first_visible([
                    page.locator('input[aria-label*="To"]'), page.locator('input[placeholder*="To"]'),
                    page.get_by_role("textbox", name=_re.compile(r"To", _re.I)),
                ])
            if to is None:
                raise AppAutomationError("The recipient field is not visible; the draft was not sent.")
            to.fill(recipient)
            try:
                to.press("Enter")
            except Exception:
                pass
            if subject:
                subj = self._first_visible([
                    page.locator('input[name="subjectbox"]'), page.locator('input[placeholder*="Subject"]'),
                    page.get_by_role("textbox", name=_re.compile(r"Subject", _re.I)),
                ])
                if subj is not None:
                    subj.fill(subject)
        else:
            # Reply only inside a visible, selected mail thread. If the inbox
            # is open, select the newest matching row (or newest row) first.
            reply_button = self._first_visible([
                page.get_by_role("button", name=_re.compile(r"^Reply(?: all)?$", _re.I)),
                page.locator('button[aria-label*="Reply"]'),
                page.locator('[role="button"][aria-label*="Reply"]'),
            ])
            selected_row_text = ""
            if reply_button is None:
                selector = "tr.zA" if app == "gmail" else "[role='option']"
                rows = page.locator(selector)
                try:
                    row_count = min(rows.count(), 60)
                except Exception:
                    row_count = 0
                for index in range(row_count):
                    row = rows.nth(index)
                    try:
                        row_text = _compact_visible_text(row.inner_text(timeout=1_500), 2_000)
                        if recipient and recipient.lower() not in row_text.lower():
                            continue
                        row.click(timeout=4_000)
                        selected_row_text = row_text
                        page.wait_for_timeout(500)
                        break
                    except Exception:
                        continue
                reply_button = self._first_visible([
                    page.get_by_role("button", name=_re.compile(r"^Reply(?: all)?$", _re.I)),
                    page.locator('button[aria-label*="Reply"]'),
                    page.locator('[role="button"][aria-label*="Reply"]'),
                ])
            if reply_button is None:
                raise AppAutomationError("Open the email thread you want to reply to in the local browser first. No message was sent.")
            if recipient:
                visible_target = selected_row_text or self._body_text(page)
                if recipient.lower() not in visible_target.lower():
                    raise AppAutomationError("The visible email does not match the requested sender. No draft was prepared or sent.")
            reply_button.click(timeout=4_000)
            page.wait_for_timeout(300)

        body_box = self._first_visible([
            page.locator('div[aria-label="Message Body"]'),
            page.locator('div[contenteditable="true"][aria-label*="Message"]'),
            page.locator('div[contenteditable="true"][role="textbox"]'),
            page.locator('div[contenteditable="true"]'),
            page.locator("textarea"),
        ])
        if body_box is None:
            raise AppAutomationError("The email body editor is not visible. The message was not sent.")
        body_box.fill(body)
        target = recipient or "the currently selected email thread"
        return target, "email"

    def _chat_compose(self, app: str, page, body: str, recipient: str) -> tuple[str, str]:
        selectors = {
            "whatsapp": ["#main footer [contenteditable='true']", "#main footer [role='textbox']", "#main footer textarea"],
            "telegram": ["#column-center [contenteditable='true']", ".input-message-input", "#column-center [role='textbox']", "textarea"],
            "instagram": ["main textarea", "main [contenteditable='true']", "main [role='textbox']"],
        }
        candidates = [page.locator(selector) for selector in selectors[app]]
        editor = self._first_visible(candidates)
        if editor is None:
            raise AppAutomationError("Open the exact chat in the local browser first. The message editor is not visible; nothing was sent.")
        active_target = ""
        for selector in ("#main header", "#column-center header", "main h1", "main h2", "header"):
            names = self._locator_text(page, selector, 1)
            if names:
                active_target = names[0][:180]
                break
        if recipient and (not active_target or recipient.lower() not in active_target.lower()):
            raise AppAutomationError("The open chat does not clearly match the requested recipient. Select the correct conversation; nothing was sent.")
        editor.fill(body)
        return active_target or recipient or "the currently selected conversation", "chat"

    def _prepare_send(self, app: str, payload: dict[str, Any]) -> dict[str, Any]:
        if APPS[app]["kind"] not in {"mail", "chat"}:
            raise ValueError("Replies are supported only in mail and chat apps")
        body = _bounded_text(payload.get("body"), "reply text", MAX_MESSAGE_CHARS)
        recipient = str(payload.get("recipient") or "").strip()[:240]
        subject = str(payload.get("subject") or "").strip()[:240]
        mode = str(payload.get("mode") or "reply").lower()
        if mode not in {"reply", "new"}:
            raise ValueError("message mode must be reply or new")
        page = self._app_page(app)
        text = self._body_text(page)
        if self._requires_sign_in(app, page, text):
            return {"ok": False, "app": app, "requires_sign_in": True, "error": "Sign in in the local app browser first. No message was sent."}
        if APPS[app]["kind"] == "mail":
            target, kind = self._email_compose(app, page, mode, recipient, subject, body)
        else:
            if recipient and recipient.lower() not in self._active_chat_target(app, page).lower():
                self._select_chat_target(app, page, recipient)
            target, kind = self._chat_compose(app, page, body, recipient)
        token = uuid.uuid4().hex
        self._pending[token] = {
            "kind": "send", "app": app, "created": time.time(), "target": target,
            "body": body, "mode": mode,
        }
        return {"ok": True, "app": app, "prepared": True, "requires_confirmation": True,
                "confirmation_token": token, "target": target, "body": body,
                "message": "Draft is visible in the app and has not been sent."}

    def _calendar_create(self, app: str, payload: dict[str, Any]) -> dict[str, Any]:
        if APPS[app]["kind"] != "calendar":
            raise ValueError("Calendar event creation needs a calendar app")
        title = _bounded_text(payload.get("title"), "event title", 240)
        start = _safe_datetime(payload.get("start"), payload.get("timezone"))
        end = _safe_datetime(payload.get("end"), payload.get("timezone"))
        if end <= start:
            raise ValueError("event end must be after its start")
        details = str(payload.get("details") or "").strip()[:2_000]
        if app == "google_calendar":
            params = {"action": "TEMPLATE", "text": title, "dates": _format_google_dates(start, end)}
            if details:
                params["details"] = details
            url = "https://calendar.google.com/calendar/render?" + urlencode(params)
        else:
            params = {
                "path": "/calendar/action/compose",
                "subject": title,
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
                "body": details,
            }
            url = "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(params)
        page = self._page(app)
        self._navigate(page, url)
        text = self._body_text(page)
        if self._requires_sign_in(app, page, text):
            return {"ok": False, "app": app, "requires_sign_in": True, "error": "Sign in in the local calendar browser first. No event was created."}
        token = uuid.uuid4().hex
        self._pending[token] = {
            "kind": "calendar_save", "app": app, "created": time.time(),
            "title": title, "start": start.isoformat(), "end": end.isoformat(),
        }
        return {"ok": True, "app": app, "prepared": True, "requires_confirmation": True,
                "confirmation_token": token, "title": title, "start": start.isoformat(), "end": end.isoformat(),
                "message": "Event details are open in the calendar UI and have not been saved."}

    def _detect_call(self, app: str) -> dict[str, Any]:
        if app not in {"telegram", "whatsapp"}:
            raise ValueError("Incoming call detection is supported for Telegram and WhatsApp Web")
        page = self._app_page(app)
        text = self._body_text(page)
        lower = text.lower()
        incoming = any(marker in lower for marker in ("incoming call", "incoming voice call", "incoming video call", "calling you", "is calling"))
        if not incoming:
            return {"ok": True, "app": app, "detected": False, "message": "No incoming call is visible in the local browser."}
        accept = self._first_visible([
            page.get_by_role("button", name=re.compile(r"^(answer|accept|join|join call)$", re.I)),
            page.locator('button[aria-label*="Answer"]'),
            page.locator('button[aria-label*="Accept"]'),
        ])
        if accept is None:
            return {"ok": False, "app": app, "detected": True, "message": "An incoming call is visible, but no Answer/Accept control is exposed. It was not answered."}
        token = uuid.uuid4().hex
        self._pending[token] = {"kind": "answer_call", "app": app, "created": time.time()}
        return {"ok": True, "app": app, "detected": True, "requires_confirmation": True,
                "confirmation_token": token, "message": "Incoming call detected. It will not be answered until you confirm."}

    def _confirm(self, token: str, confirm: bool) -> dict[str, Any]:
        token = str(token or "")
        pending = self._pending.pop(token, None)
        if not pending or time.time() - pending.get("created", 0) > PENDING_TTL_SECONDS:
            return {"ok": False, "error": "That confirmation expired. Prepare the action again."}
        if confirm is not True:
            return {"ok": True, "confirmed": False, "message": "Cancelled. The draft/event remains open and was not submitted."}
        app = pending["app"]
        page = self._app_page(app)
        if pending["kind"] == "send":
            send_button = self._first_visible([
                page.get_by_role("button", name=re.compile(r"^send(?: now)?$", re.I)),
                page.locator('button[aria-label^="Send"]'),
                page.locator('[role="button"][aria-label^="Send"]'),
            ])
            if send_button is None:
                return {"ok": False, "error": "No Send button is visible. The draft remains open and was not submitted."}
            send_button.click(timeout=5_000)
            page.wait_for_timeout(350)
            return {"ok": True, "confirmed": True, "send_clicked": True, "app": app,
                    "target": pending.get("target"), "message": "Send was clicked after your confirmation. Check the app for its delivery status."}
        if pending["kind"] == "calendar_save":
            save = self._first_visible([
                page.get_by_role("button", name=re.compile(r"^save(?: event)?$", re.I)),
                page.locator('button[aria-label^="Save"]'),
            ])
            if save is None:
                return {"ok": False, "error": "No Save button is visible. The event remains open and was not saved."}
            save.click(timeout=5_000)
            page.wait_for_timeout(350)
            return {"ok": True, "confirmed": True, "saved": True, "app": app,
                    "message": "Save was clicked after your confirmation. Check the calendar for the event."}
        if pending["kind"] == "answer_call":
            text = self._body_text(page).lower()
            if not any(marker in text for marker in ("incoming call", "incoming voice call", "incoming video call", "calling you", "is calling")):
                return {"ok": False, "error": "The incoming call is no longer visible. Nothing was answered."}
            accept = self._first_visible([
                page.get_by_role("button", name=re.compile(r"^(answer|accept|join|join call)$", re.I)),
                page.locator('button[aria-label*="Answer"]'),
                page.locator('button[aria-label*="Accept"]'),
            ])
            if accept is None:
                return {"ok": False, "error": "The Answer/Accept control is no longer visible. Nothing was answered."}
            accept.click(timeout=5_000)
            return {"ok": True, "confirmed": True, "answered_click": True, "app": app,
                    "message": "The call-answer control was clicked after your confirmation."}
        return {"ok": False, "error": "Unsupported pending action."}

    def _status(self) -> dict[str, Any]:
        try:
            import playwright  # noqa: F401
            installed = True
        except Exception:
            installed = False
        return {
            "ok": True,
            "playwright_installed": installed,
            "browser_running": self._context is not None,
            "profile_exists": os.path.isdir(self.profile_dir),
            "active_apps": [app for app, page in self._pages.items() if page is not None],
            "profile_note": "A separate local browser profile; sign in manually once. No passwords or app API tokens are read by Weronika.",
            "alerts_active": self._watch_config is not None,
        }

    def status(self) -> dict[str, Any]:
        return self._submit(self._status, timeout=10)

    def _push_event(self, event: dict[str, Any]) -> None:
        with self._events_lock:
            sequence = (self._events[-1]["id"] + 1) if self._events else 1
            event["id"] = sequence
            event["created_at"] = time.time()
            self._events = (self._events + [event])[-200:]

    def alerts(self, since: int = 0) -> dict[str, Any]:
        try:
            since_id = max(0, int(since))
        except (TypeError, ValueError):
            since_id = 0
        with self._events_lock:
            events = [dict(event) for event in self._events if event["id"] > since_id]
        return {"ok": True, "events": events, "alerts_active": self._watch_config is not None}

    def _family_alert_loop(self) -> None:
        while not self._watch_stop.wait(20):
            config = self._watch_config
            if not config:
                return
            for app in config["apps"]:
                try:
                    result = self._submit(lambda current_app=app: self._read(current_app), timeout=30)
                except Exception:
                    continue
                if not result.get("ok"):
                    continue
                content = result.get("content", "")
                lowered = content.lower()
                call_visible = any(marker in lowered for marker in (
                    "incoming call", "incoming voice call", "incoming video call", "calling you", "is calling",
                ))
                if app in {"telegram", "whatsapp"} and call_visible and app not in self._active_call_alerts:
                    self._active_call_alerts.add(app)
                    try:
                        call = self._submit(lambda current_app=app: self._detect_call(current_app), timeout=10)
                        if call.get("requires_confirmation"):
                            self._push_event({
                                "type": "incoming_call", "app": app,
                                "confirmation_token": call.get("confirmation_token"),
                                "message": "Incoming call visible in the local app browser.",
                            })
                    except Exception:
                        pass
                elif not call_visible:
                    self._active_call_alerts.discard(app)

                digest = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()
                previous = self._snapshots.get(app)
                self._snapshots[app] = content
                if previous is None or hashlib.sha256(previous.encode("utf-8", "replace")).hexdigest() == digest:
                    continue
                delta = _line_delta(previous, content)
                if not delta:
                    continue
                terms = config["contacts"] or FAMILY_DEFAULT_TERMS
                lowered_delta = delta.lower()
                active_target = str(result.get("active_target") or "").lower()
                if not any(term.lower() in lowered_delta or term.lower() in active_target for term in terms):
                    continue
                alert_text = f"From/Chat: {result.get('active_target') or 'visible conversation'}\n{delta}"
                self._push_event({"type": "family_message", "app": app, "text": alert_text, "source": result.get("source")})

    def _start_alerts(self, apps: list[object], contacts: list[object] | None) -> dict[str, Any]:
        normalized = []
        for item in apps:
            app = normalize_app(item)
            if APPS[app]["kind"] != "chat":
                raise ValueError("Family message monitoring only supports WhatsApp, Telegram, and Instagram DMs")
            if app not in normalized:
                normalized.append(app)
        if not normalized:
            normalized = ["whatsapp", "telegram"]
        self._ensure_context()
        normalized_contacts = [str(name).strip().lower()[:80] for name in (contacts or []) if str(name).strip()]
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_stop.set()
            self._watch_thread.join(timeout=1)
        self._watch_stop = threading.Event()
        self._watch_config = {"apps": normalized, "contacts": normalized_contacts}
        self._snapshots.clear()
        self._active_call_alerts.clear()
        # Prime a baseline immediately on the browser worker. Subsequent DOM
        # changes produce local alerts; message text is never logged or hosted.
        login_needed = []
        for app in normalized:
            try:
                result = self._read(app)
                if result.get("requires_sign_in"):
                    login_needed.append(app)
                if result.get("ok"):
                    content = result.get("content", "")
                    self._snapshots[app] = content
                    lowered = content.lower()
                    call_visible = any(marker in lowered for marker in (
                        "incoming call", "incoming voice call", "incoming video call", "calling you", "is calling",
                    ))
                    if app in {"telegram", "whatsapp"} and call_visible:
                        self._active_call_alerts.add(app)
                        call = self._detect_call(app)
                        if call.get("requires_confirmation"):
                            self._push_event({
                                "type": "incoming_call", "app": app,
                                "confirmation_token": call.get("confirmation_token"),
                                "message": "Incoming call visible in the local app browser.",
                            })
            except Exception:
                pass
        self._watch_thread = threading.Thread(target=self._family_alert_loop, daemon=True, name="weronika-family-alerts")
        self._watch_thread.start()
        message = "Local family-message monitoring started. Keep the local agent and signed-in app tabs open."
        if login_needed:
            message += f" Sign in manually in the local browser for: {', '.join(login_needed)}."
        return {"ok": True, "alerts_active": True, "apps": normalized,
                "requires_sign_in": login_needed,
                "contacts": normalized_contacts or list(FAMILY_DEFAULT_TERMS),
                "interval_seconds": 20, "message": message}

    def _perform(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        app_value = payload.get("app")
        if action == "start_family_alerts":
            return self._start_alerts(payload.get("apps") or ["whatsapp", "telegram"], payload.get("contacts"))
        if action == "stop_family_alerts":
            self._watch_stop.set()
            self._watch_config = None
            self._active_call_alerts.clear()
            return {"ok": True, "alerts_active": False, "message": "Family-message monitoring stopped."}
        if action == "confirm":
            return self._confirm(payload.get("confirmation_token"), payload.get("confirm") is True)
        if not app_value:
            raise ValueError("app is required")
        app = normalize_app(app_value)
        if action == "open":
            return self._open(app)
        if action == "read":
            return self._read(app, str(payload.get("target") or payload.get("contact") or ""))
        if action == "play":
            if app not in {"spotify", "youtube"}:
                raise ValueError("Search-and-play is supported only for Spotify and YouTube")
            return self._media_play(app, payload.get("query", ""))
        if action == "prepare_send":
            return self._prepare_send(app, payload)
        if action == "calendar_create":
            return self._calendar_create(app, payload)
        if action == "detect_call":
            return self._detect_call(app)
        raise ValueError("Unsupported local app action")

    def perform(self, action: object, payload: object) -> dict[str, Any]:
        action_name = str(action or "").strip().lower()
        if not isinstance(payload, dict):
            return {"ok": False, "error": "Request payload must be a JSON object."}
        try:
            if action_name == "status":
                return self.status()
            if action_name == "alerts":
                return self.alerts(payload.get("since", 0))
            if action_name not in {"open", "read", "play", "prepare_send", "confirm", "calendar_create", "detect_call", "start_family_alerts", "stop_family_alerts"}:
                return {"ok": False, "error": "Unsupported local app action."}
            # Keep UI message bodies out of the log bus and console.
            result = self._submit(lambda: self._perform(action_name, payload), timeout=90)
            return result if isinstance(result, dict) else {"ok": False, "error": "Invalid browser result."}
        except (ValueError, AppAutomationError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"Local browser action failed: {exc}"}

    def shutdown(self) -> None:
        if self._closed:
            return
        self._watch_stop.set()
        try:
            def close_browser():
                if self._context is not None:
                    try:
                        self._context.close()
                    except Exception:
                        pass
                    self._context = None
                    self._pages.clear()
                if self._playwright is not None:
                    try:
                        self._playwright.stop()
                    except Exception:
                        pass
                    self._playwright = None
            self._executor.submit(close_browser).result(timeout=10)
        except Exception:
            pass
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)


APP_BROWSER = LocalAppBrowser()
