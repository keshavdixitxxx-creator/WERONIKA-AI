"""Visible-browser web automation: search, open, read, play, and approved posting.

Everything happens in the Weronika-managed Chromium window so the user can watch it.
There is no headless scraping, no private API, and no form submission that the user
did not approve in the orb first.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from .tasks import (
    MAX_TEXT_CHARS,
    PageReading,
    Step,
    TaskError,
    clean_query,
    resolve_target,
)
from .workflow import MessagingError

MAX_READ_CHARS = 4000
_BLOCKED_HOSTS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
)
_ACCOUNT_WORDS_RE = re.compile(
    r"\b(?:your account|my account|logged in as|sign in as|profile)\b", re.IGNORECASE
)
_YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "music.youtube.com")


@dataclass(frozen=True)
class SubmitOutcome:
    submitted: bool
    detail: str


def _preferred_matches(preferred: str, name: str) -> bool:
    wanted = str(preferred or "").strip().casefold()
    if not wanted:
        return True
    return wanted in name.casefold() or name.casefold() in wanted


def browser_candidates(preferred: str = "") -> list[tuple[str, list[str]]]:
    """Browsers Weronika can open directly, honouring an explicit preference."""
    candidates: list[tuple[str, list[str]]] = [
        ("Microsoft Edge", ["msedge"]),
        (
            "Google Chrome",
            ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
        ),
        ("Mozilla Firefox", ["firefox"]),
    ]
    if sys.platform.startswith("win"):
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for root in [value for value in roots if value]:
            candidates[0][1].append(str(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe"))
            candidates[1][1].append(str(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    elif sys.platform == "darwin":
        candidates[0][1].append("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
        candidates[1][1].append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    return [entry for entry in candidates if _preferred_matches(preferred, entry[0])]


def find_browser(preferred: str = "") -> tuple[str, str] | None:
    """Return (display name, executable) for an installed browser, or None."""
    for name, executables in browser_candidates(preferred):
        for executable in executables:
            if not executable:
                continue
            path = Path(executable)
            if path.is_file():
                return name, str(path)
            found = shutil.which(executable)
            if found:
                return name, found
    return None


def is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.casefold()
    return not any(host == blocked or host.endswith(f".{blocked}") for blocked in _BLOCKED_HOSTS)


class BrowserTaskAdapter:
    """Run approved steps in the visible browser Weronika already controls."""

    def __init__(self, browser, *, launcher=None, max_results: int = 5) -> None:
        self.browser = browser
        self.launcher = launcher or find_browser
        self.max_results = max_results
        self.page = None

    # ------------------------------------------------------------------ pages

    def _doc(self):
        if self.page is None or self.page.is_closed():
            context = self.browser.workspace_browser()
            pages = [page for page in context.pages if page.url != "about:blank"]
            self.page = pages[-1] if pages else context.new_page()
        return self.page

    def _open(self, url: str) -> str:
        if not is_public_url(url):
            raise TaskError(f"“{url}” is not a public http(s) address, so Weronika did not open it.")
        page = self._doc()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(700)
        except Exception as exc:
            raise TaskError(f"Weronika could not open “{url}”. Nothing else was changed.") from exc
        return page.url

    # ------------------------------------------------------------- primitives

    def search(self, query: str) -> str:
        query = clean_query(query)
        if not query:
            raise TaskError("What should Weronika search for?")
        return self._open(f"https://duckduckgo.com/?q={quote_plus(query)}&ia=web")

    def open_url(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            raise TaskError("Which website should Weronika open?")
        if not re.match(r"^https?://", raw, re.I):
            raw = f"https://{raw}"
        return self._open(raw)

    def click_result(self, index: int = 0) -> str:
        page = self._doc()
        links = self._result_links(page)
        if not links:
            raise TaskError("No search result link is visible on this page, so nothing was opened.")
        position = max(0, min(index, len(links) - 1))
        label, href = links[position]
        page.goto(href, wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(500)
        return f"{label} — {page.url}"

    def _result_links(self, page) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        seen: set[str] = set()
        try:
            locator = page.locator("a[href]")
            count = min(locator.count(), 400)
        except Exception:
            return rows
        for index in range(count):
            anchor = locator.nth(index)
            try:
                if not anchor.is_visible():
                    continue
                href = anchor.get_attribute("href", timeout=400) or ""
                text = " ".join(anchor.inner_text(timeout=400).split())
            except Exception:
                continue
            if not href.startswith("http") or not text or len(text) < 3:
                continue
            if any(host in href for host in ("duckduckgo.com", "google.com/", "bing.com")):
                continue
            if href in seen:
                continue
            seen.add(href)
            rows.append((text[:120], href))
            if len(rows) >= 20:
                break
        return rows

    def read_page(self) -> PageReading:
        page = self._doc()
        try:
            title = " ".join(page.title().split())[:200]
            text = page.inner_text("body", timeout=8_000)
        except Exception as exc:
            raise TaskError("Weronika could not read the open page.") from exc
        cleaned = " ".join(str(text or "").split())
        return PageReading(
            url=page.url,
            title=title,
            text=cleaned[:MAX_READ_CHARS],
        )

    # ------------------------------------------------------------------- media

    def play(self, query: str, *, context: str = "") -> tuple[str, str]:
        """Open YouTube, take the first result the site shows, and start playback."""
        target = clean_query(resolve_target(Step("play_video", query), context) or query)
        if not target:
            raise TaskError("Which video or song should Weronika play?")
        page = self._doc()
        search = f"https://www.youtube.com/results?search_query={quote_plus(target)}"
        try:
            page.goto(search, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1_200)
        except Exception as exc:
            raise TaskError("Weronika could not open YouTube search.") from exc

        video = None
        for selector in (
            "ytd-video-renderer a#video-title",
            "a#video-title-link",
            "ytd-video-renderer a[href*='/watch']",
            "a.yt-lockup-metadata-view-model-wiz__title",
        ):
            try:
                locator = page.locator(selector)
                if locator.count() and locator.first.is_visible():
                    video = locator.first
                    break
            except Exception:
                continue
        if video is None:
            raise TaskError(
                f"YouTube did not show a playable result for “{target}”. Weronika stopped; nothing was played."
            )
        try:
            label = " ".join(video.inner_text(timeout=1_500).split())[:160] or target
        except Exception:
            label = target
        try:
            video.click(timeout=8_000)
            page.wait_for_timeout(1_500)
        except Exception as exc:
            href = ""
            try:
                href = video.get_attribute("href", timeout=800) or ""
            except Exception:
                href = ""
            if not href:
                raise TaskError("Weronika could not start that YouTube video.") from exc
            page.goto(f"https://www.youtube.com{href}", wait_until="domcontentloaded", timeout=45_000)
        detail = f"Playing on YouTube: “{label}”"
        if _AD_SELECTOR:
            detail += self._skip_ad(page)
        return detail, page.url

    def _skip_ad(self, page) -> str:
        for _ in range(8):
            try:
                button = page.locator(".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button")
                if button.count() and button.first.is_visible():
                    button.first.click(timeout=1_500)
                    return " (skipped a pre-roll ad)"
            except Exception:
                pass
            try:
                page.wait_for_timeout(600)
            except Exception:
                break
        return ""

    def play_url(self, value: str) -> tuple[str, str]:
        if not any(host in value for host in _YOUTUBE_HOSTS):
            raise TaskError("That link is not a YouTube video link.")
        url = self._open(value)
        detail = "Playing the requested YouTube link."
        if _AD_SELECTOR:
            detail += self._skip_ad(self._doc())
        return detail, url

    # ------------------------------------------------------- account actions

    def prepare_account_action(self, action: str, text: str, context: str) -> str:
        """Find the composer for a comment/reply/like/subscribe without submitting."""
        page = self._doc()
        if not any(host in page.url for host in _YOUTUBE_HOSTS + ("instagram.com", "facebook.com", "x.com", "linkedin.com")):
            raise TaskError(
                f"A {action} only works on a page that is already open, and the current page is "
                f"“{page.url}”. Open the video or post first, then ask again."
            )
        if action in {"comment", "reply"}:
            composer = self._comment_composer(page)
            if composer is None:
                raise TaskError(
                    "Weronika could not find the comment box on this page. Sign in and scroll to the "
                    "comments, then try again. Nothing was typed."
                )
            try:
                composer.click(timeout=5_000)
                composer.fill(text, timeout=6_000)
                typed = ""
                try:
                    typed = composer.input_value(timeout=1_000)
                except Exception:
                    typed = composer.inner_text(timeout=1_000)
                if " ".join(str(typed or "").split()) != text:
                    raise TaskError("The comment box did not keep the exact text. Weronika stopped before submitting.")
            except TaskError:
                raise
            except Exception as exc:
                raise TaskError("Weronika could not type the comment. Nothing was submitted.") from exc
            return f"Comment typed into the box on “{page.title()[:80]}” · not submitted"
        if action in {"like", "subscribe"}:
            return f"Ready to press {action} on “{page.title()[:80]}” · waiting for approval"
        raise TaskError(f"“{action}” is not a supported account action.")

    def submit_account_action(self, action: str, text: str) -> SubmitOutcome:
        page = self._doc()
        if action in {"comment", "reply"}:
            for selector in (
                "ytd-comment-dialog #submit-button",
                "#submit-button",
                "ytd-button-renderer#submit-button button",
                "div[contenteditable='true'] ~ div button",
            ):
                try:
                    button = page.locator(selector)
                    if button.count() and button.first.is_visible():
                        button.first.click(timeout=5_000)
                        page.wait_for_timeout(1_500)
                        return SubmitOutcome(True, "Comment submitted; check the page to confirm it appears.")
                except Exception:
                    continue
            raise TaskError(
                "Weronika could not find the Submit button. The text is still in the box; nothing was submitted."
            )
        if action in {"like", "subscribe"}:
            selector = (
                "button[aria-label*='like' i]"
                if action == "like"
                else "button[aria-label*='Subscribe' i], ytd-subscribe-button-renderer button"
            )
            try:
                button = page.locator(selector)
                if button.count() and button.first.is_visible():
                    button.first.click(timeout=5_000)
                    page.wait_for_timeout(800)
                    return SubmitOutcome(True, f"Pressed {action}. Check the page to confirm the state.")
            except Exception:
                pass
            raise TaskError(f"Weronika could not press {action}. Nothing was changed.")
        raise TaskError(f"“{action}” is not a supported account action.")

    def _comment_composer(self, page):
        for selector in (
            "#contenteditable-root",
            "ytd-comment-simplebox-renderer #contenteditable-root",
            "div[contenteditable='true'][aria-label*='comment' i]",
            "textarea[placeholder*='comment' i]",
            "div[contenteditable='true'][role='textbox']",
            "textarea[aria-label*='comment' i]",
        ):
            try:
                locator = page.locator(selector)
                count = min(locator.count(), 10)
            except Exception:
                continue
            for index in range(count):
                candidate = locator.nth(index)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        return None

    # ------------------------------------------------------------ system open

    def open_in_system_browser(self, url: str, preferred: str = "") -> str:
        """Open a URL in Edge/Chrome/Firefox without taking over the session."""
        if not is_public_url(url):
            raise TaskError("Only public http(s) addresses can be opened in your own browser.")
        found = self.launcher(preferred)
        if found is None:
            raise TaskError(
                "Weronika could not find Microsoft Edge, Google Chrome, or Firefox on this computer. "
                f"Open this address yourself instead: {url}"
            )
        name, executable = found
        try:
            kwargs: dict[str, Any] = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = 0x00000008  # DETACHED_PROCESS
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen([executable, url], **kwargs)
        except Exception as exc:
            raise MessagingError(f"Weronika found {name} but could not start it.") from exc
        return f"Opened in {name}: {url}"

    def close(self) -> None:
        self.page = None


_AD_SELECTOR = ".ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button"
