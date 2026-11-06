"""Visible-browser adapters for supported messaging websites.

Only accessible UI is used. There are no private API calls, password handling,
message-history scraping, or automatic send-on-prepare behavior.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from .models import Platform, RecipientCandidate, VisibleContact
from .workflow import LoginRequired, MessagingError, UnsupportedAppUi


@dataclass(frozen=True)
class PlatformSpec:
    url: str
    search_selectors: tuple[str, ...]
    result_selectors: tuple[str, ...]
    composer_selectors: tuple[str, ...]
    send_selectors: tuple[str, ...]
    header_selectors: tuple[str, ...]
    login_markers: tuple[str, ...]


SPECS: dict[Platform, PlatformSpec] = {
    Platform.WHATSAPP: PlatformSpec(
        url="https://web.whatsapp.com/",
        search_selectors=(
            "[data-testid='chat-list-search']",
            "input[placeholder*='Search or start a new chat' i]",
            "[role='searchbox']",
            "input[placeholder*='Search' i]",
        ),
        result_selectors=(
            "[data-testid='cell-frame-container']",
            "[role='listitem']",
            "[role='row']",
        ),
        composer_selectors=(
            "footer [data-testid='conversation-compose-box-input']",
            "footer [contenteditable='true'][role='textbox']",
            "footer [contenteditable='true']",
        ),
        send_selectors=(
            "[data-testid='send']",
            "button[aria-label*='Send' i]",
            "[role='button'][aria-label*='Send' i]",
        ),
        header_selectors=("[data-testid='conversation-info-header']",),
        login_markers=("Use WhatsApp on your computer", "Link with phone number", "Scan the QR code"),
    ),
    Platform.TELEGRAM: PlatformSpec(
        url="https://web.telegram.org/k/",
        search_selectors=(
            "#telegram-search-input",
            "input[placeholder*='Search' i]",
            "[role='searchbox']",
        ),
        result_selectors=("[role='listitem']", ".ListItem", "[role='option']"),
        composer_selectors=(
            "[contenteditable='true'][role='textbox']",
            "div[contenteditable='true']",
            "textarea[placeholder*='Message' i]",
        ),
        send_selectors=("button[aria-label*='Send' i]", "[role='button'][aria-label*='Send' i]"),
        header_selectors=("#column-center header", "#column-center [role='heading']"),
        login_markers=("Your Phone Number", "Log in to Telegram", "Confirmation code"),
    ),
    Platform.INSTAGRAM: PlatformSpec(
        url="https://www.instagram.com/direct/inbox/",
        search_selectors=(
            "input[placeholder*='Search' i]",
            "input[aria-label*='Search' i]",
            "[role='searchbox']",
        ),
        result_selectors=("[role='option']", "[role='listitem']", "[role='button']"),
        composer_selectors=(
            "textarea[placeholder*='Message' i]",
            "[contenteditable='true'][role='textbox']",
            "div[contenteditable='true']",
        ),
        send_selectors=("button[aria-label*='Send' i]", "[role='button'][aria-label*='Send' i]"),
        header_selectors=("[role='main'] header", "[role='main'] [role='heading']"),
        login_markers=("Log in to Instagram", "Forgot password?", "Sign up"),
    ),
    Platform.FACEBOOK: PlatformSpec(
        url="https://www.messenger.com/",
        search_selectors=(
            "input[placeholder*='Search' i]",
            "input[aria-label*='Search' i]",
            "[role='searchbox']",
        ),
        result_selectors=("[role='option']", "[role='row']", "[role='listitem']"),
        composer_selectors=(
            "[contenteditable='true'][role='textbox']",
            "div[contenteditable='true'][aria-label*='Message' i]",
            "textarea[placeholder*='Message' i]",
        ),
        send_selectors=("button[aria-label*='Send' i]", "[role='button'][aria-label*='Send' i]"),
        header_selectors=("[role='main'] header", "[role='main'] [role='heading']"),
        login_markers=("Log into Facebook", "Create new account", "Forgot password?"),
    ),
    Platform.X: PlatformSpec(
        url="https://x.com/messages",
        search_selectors=(
            "input[placeholder*='Search' i]",
            "input[aria-label*='Search' i]",
            "[role='searchbox']",
        ),
        result_selectors=("[role='option']", "[role='listitem']", "[data-testid*='UserCell']"),
        composer_selectors=(
            "[data-testid='dmComposerTextInput']",
            "[contenteditable='true'][role='textbox']",
            "div[contenteditable='true'][aria-label*='Message' i]",
        ),
        send_selectors=(
            "[data-testid='dmComposerSendButton']",
            "button[aria-label*='Send' i]",
            "[role='button'][aria-label*='Send' i]",
        ),
        header_selectors=("[data-testid='DmActivityViewport'] header", "[data-testid='DmActivityViewport'] [role='heading']"),
        login_markers=("Sign in to X", "Create your account", "Log in"),
    ),
}


class BrowserManager:
    """Own one persistent, visible browser profile per messaging platform."""

    def __init__(self, profile_root: Path | None = None) -> None:
        self.profile_root = profile_root or (Path.home() / ".weronika" / "messaging-profiles")
        self._playwright = None
        self._contexts: dict[Platform, object] = {}
        self._workspace_context = None
        self._workspace_page_ids: dict[int, str] = {}

    def page_for(self, platform: Platform):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise MessagingError(
                "Browser automation needs Playwright. Install the Python requirements, "
                "then run ‘python -m playwright install chromium’."
            ) from exc

        if self._playwright is None:
            self._playwright = sync_playwright().start()
        if platform not in self._contexts:
            profile = self.profile_root / platform.value
            self.profile_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                self.profile_root.chmod(0o700)
            except OSError:
                pass
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                profile.chmod(0o700)
            except OSError:
                pass
            try:
                self._contexts[platform] = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile),
                    headless=False,
                    viewport={"width": 1280, "height": 900},
                    args=["--disable-session-crashed-bubble"],
                )
            except Exception as exc:
                raise MessagingError(
                    f"Could not open the {platform.value.title()} browser profile. "
                    "Close any Weronika-controlled browser windows and try again."
                ) from exc
        context = self._contexts[platform]
        pages = context.pages
        return pages[0] if pages else context.new_page()

    def workspace_browser(self):
        """Public accessor for the user-visible managed browser."""
        return self._workspace_browser()

    def _workspace_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise MessagingError(
                "Managed browsing needs Playwright. Install the Python requirements, "
                "then run ‘python -m playwright install chromium’."
            ) from exc
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        if self._workspace_context is None:
            profile = self.profile_root.parent / "workspace-browser"
            profile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                profile.chmod(0o700)
            except OSError:
                pass
            try:
                self._workspace_context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile),
                    headless=False,
                    viewport={"width": 1440, "height": 960},
                    args=["--disable-session-crashed-bubble"],
                )
            except Exception as exc:
                raise MessagingError(
                    "Could not open Weronika's managed browser. Close any existing "
                    "Weronika-controlled browser window and try again."
                ) from exc
        return self._workspace_context

    @staticmethod
    def _normalize_web_url(value: str) -> str:
        value = value.strip()
        if not value or len(value) > 2048 or any(char.isspace() for char in value):
            raise ValueError("Each address must be a valid web URL (maximum 2048 characters).")
        if not re.match(r"^https?://", value, re.IGNORECASE):
            local_address = re.match(r"^(?:localhost|127\.0\.0\.1|\[::1\])(?::|/|$)", value, re.IGNORECASE)
            if not local_address and re.match(r"^[a-z][a-z0-9+.-]*:", value, re.IGNORECASE):
                raise ValueError("Only http:// and https:// website addresses are allowed.")
            value = ("http://" if local_address else "https://") + value
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only http:// and https:// website addresses are allowed.")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("That website address has an invalid port.") from exc
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Website addresses must not contain embedded credentials.")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, parsed.fragment))

    def open_workspace_urls(self, urls: list[str]) -> list[dict[str, str]]:
        if not isinstance(urls, list) or not urls or len(urls) > 10:
            raise ValueError("Choose between 1 and 10 website addresses.")
        normalized = [self._normalize_web_url(value) for value in urls if isinstance(value, str)]
        if len(normalized) != len(urls):
            raise ValueError("Every website address must be text.")
        context = self._workspace_browser()
        results: list[dict[str, str]] = []
        for url in normalized:
            page = context.new_page()
            tab_id = uuid.uuid4().hex[:12]
            self._workspace_page_ids[id(page)] = tab_id
            state = "opened"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=12_000)
            except Exception as exc:
                state = "tab opened; page did not finish loading"
                if exc.__class__.__name__ not in {"TimeoutError", "Error"}:
                    state = "tab opened; navigation needs attention"
            results.append({"id": tab_id, "url": url, "status": state})
        return results

    def workspace_tabs(self) -> list[dict[str, str]]:
        if self._workspace_context is None:
            return []
        tabs: list[dict[str, str]] = []
        for page in list(self._workspace_context.pages):
            tab_id = self._workspace_page_ids.setdefault(id(page), uuid.uuid4().hex[:12])
            try:
                title = page.title()[:160]
            except Exception:
                title = ""
            try:
                url = page.url[:2048]
            except Exception:
                url = ""
            tabs.append({"id": tab_id, "title": title, "url": url})
        return tabs

    def activate_workspace_tab(self, tab_id: str) -> bool:
        if self._workspace_context is None:
            return False
        for page in list(self._workspace_context.pages):
            if self._workspace_page_ids.get(id(page)) == tab_id:
                try:
                    page.bring_to_front()
                    return True
                except Exception:
                    return False
        return False

    def close_workspace_tab(self, tab_id: str) -> bool:
        if self._workspace_context is None:
            return False
        for page in list(self._workspace_context.pages):
            if self._workspace_page_ids.get(id(page)) == tab_id:
                try:
                    page.close()
                except Exception:
                    return False
                self._workspace_page_ids.pop(id(page), None)
                return True
        return False

    def close(self) -> None:
        if self._workspace_context is not None:
            try:
                self._workspace_context.close()
            except Exception:
                pass
            self._workspace_context = None
        self._workspace_page_ids.clear()
        for context in list(self._contexts.values()):
            try:
                context.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None


class PlaywrightMessagingAdapter:
    def __init__(self, platform: Platform, browser: BrowserManager) -> None:
        self.platform = platform
        self.spec = SPECS[platform]
        self.browser = browser
        self.page = None

    def _page(self):
        if self.page is None:
            self.page = self.browser.page_for(self.platform)
        if self.spec.url.rstrip("/") not in self.page.url:
            self.page.goto(self.spec.url, wait_until="domcontentloaded", timeout=45_000)
        return self.page

    @staticmethod
    def _first_visible(page, selectors: Iterable[str]):
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = min(locator.count(), 30)
                for index in range(count):
                    candidate = locator.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                continue
        return None

    def _login_required(self, page) -> bool:
        try:
            if page.locator("input[type='password']").count() and page.locator("input[type='password']").first.is_visible():
                return True
        except Exception:
            pass
        for marker in self.spec.login_markers:
            try:
                if page.get_by_text(marker, exact=False).first.is_visible():
                    return True
            except Exception:
                continue
        return False

    def find_recipients(self, query: str) -> list[VisibleContact]:
        page = self._page()
        search_error = None
        for attempt in range(2):
            search_filled = False
            for selector in self.spec.search_selectors:
                locator = page.locator(selector)
                try:
                    count = min(locator.count(), 10)
                except Exception:
                    continue
                for index in range(count):
                    field = locator.nth(index)
                    try:
                        if field.is_visible():
                            field.fill(query, timeout=2_000)
                            search_filled = True
                            break
                    except Exception as exc:
                        search_error = exc
                if search_filled:
                    break
            if search_filled:
                page.wait_for_timeout(900)
                break
            if attempt == 0:
                for label in ("Search", "Search chats", "New chat", "New message"):
                    try:
                        toggle = page.get_by_role("button", name=re.compile(re.escape(label), re.I)).first
                        if toggle.is_visible():
                            toggle.click(timeout=2_000)
                            page.wait_for_timeout(250)
                            break
                    except Exception:
                        continue
        else:
            if self._login_required(page):
                raise LoginRequired(
                    f"Please sign in to {self.platform.value.title()} in its open browser window, then retry. "
                    "Weronika never asks you to share your password."
                )
            raise UnsupportedAppUi(
                f"I couldn't use {self.platform.value.title()}'s search field. "
                "The site may have changed its layout; nothing was typed or sent."
            ) from search_error

        rows: list[VisibleContact] = []
        for selector_index, selector in enumerate(self.spec.result_selectors):
            locator = page.locator(selector)
            try:
                count = min(locator.count(), 100)
            except Exception:
                continue
            for index in range(count):
                row = locator.nth(index)
                try:
                    if not row.is_visible():
                        continue
                    text = row.inner_text(timeout=1_000).strip()
                except Exception:
                    continue
                first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
                if first_line:
                    rows.append(VisibleContact(source_id=f"{selector_index}:{index}", display_name=first_line))
            if rows:
                break
        return rows

    def _row_for_contact(self, candidate: RecipientCandidate):
        page = self._page()
        try:
            selector_index, row_index = (int(value) for value in candidate.source_id.split(":", 1))
            selector = self.spec.result_selectors[selector_index]
            row = page.locator(selector).nth(row_index)
            text = row.inner_text(timeout=1_000).strip() if row.is_visible() else ""
            first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
            if _name_key(first_line) == _name_key(candidate.display_name):
                return row
        except (ValueError, IndexError, Exception):
            pass
        raise MessagingError("That contact result changed or is no longer visible. Search again; nothing was sent.")

    def open_chat_and_draft(self, candidate: RecipientCandidate, message: str) -> None:
        page = self._page()
        contact_name = candidate.display_name
        row = self._row_for_contact(candidate)
        try:
            row.click(timeout=5_000)
            page.wait_for_timeout(500)
        except Exception as exc:
            raise MessagingError("I couldn't open that contact's chat. Nothing was sent.") from exc

        if not self._verify_chat_header(contact_name):
            raise MessagingError(
                f"I couldn't verify that the open chat is ‘{contact_name}’. "
                "I stopped before typing anything."
            )
        composer = self._first_visible(page, self.spec.composer_selectors)
        if composer is None:
            if self._login_required(page):
                raise LoginRequired(f"Please sign in to {self.platform.value.title()} and retry.")
            raise UnsupportedAppUi("I couldn't safely identify the message composer. Nothing was typed or sent.")
        try:
            composer.fill(message, timeout=5_000)
            if self._composer_text(composer) != message:
                raise MessagingError("The draft text did not match exactly; I cleared nothing and did not send it.")
        except MessagingError:
            raise
        except Exception as exc:
            raise UnsupportedAppUi("I couldn't prepare the draft in the message box. Nothing was sent.") from exc

    def _verify_chat_header(self, contact_name: str) -> bool:
        page = self._page()
        wanted = _name_key(contact_name)
        for selector in self.spec.header_selectors:
            locator = page.locator(selector)
            try:
                count = min(locator.count(), 20)
            except Exception:
                continue
            for index in range(count):
                element = locator.nth(index)
                try:
                    if not element.is_visible():
                        continue
                    text = element.inner_text(timeout=800)
                except Exception:
                    continue
                normalized_header = _name_key(text)
                if wanted and f" {wanted} " in f" {normalized_header} ":
                    return True
        return False

    @staticmethod
    def _composer_text(composer) -> str:
        try:
            return composer.input_value(timeout=1_000).strip()
        except Exception:
            try:
                return composer.inner_text(timeout=1_000).strip()
            except Exception:
                return ""

    def send_and_verify(self, message: str) -> bool:
        page = self._page()
        composer = self._first_visible(page, self.spec.composer_selectors)
        if composer is None or self._composer_text(composer) != message:
            raise MessagingError(
                "The message box no longer contains the exact approved text. "
                "Nothing was sent; please review the chat."
            )
        before_count = 0
        try:
            before_count = page.get_by_text(message, exact=True).count()
        except Exception:
            pass
        button = self._first_visible(page, self.spec.send_selectors)
        if button is None:
            raise UnsupportedAppUi("I couldn't verify the app's Send button. The draft remains unsent.")
        try:
            button.click(timeout=5_000)
            page.wait_for_timeout(800)
        except Exception as exc:
            # The click may have reached the app; the workflow marks this as
            # unverified and never retries automatically.
            raise MessagingError("The Send action timed out. Check the chat before trying again.") from exc

        composer_after = self._first_visible(page, self.spec.composer_selectors)
        emptied = composer_after is not None and not self._composer_text(composer_after)
        after_count = before_count
        try:
            after_count = page.get_by_text(message, exact=True).count()
        except Exception:
            pass
        return emptied and after_count > before_count

    def clear_draft_if_unchanged(self, message: str) -> bool:
        page = self._page()
        composer = self._first_visible(page, self.spec.composer_selectors)
        if composer is None or self._composer_text(composer) != message:
            return False
        try:
            composer.fill("")
            return True
        except Exception:
            return False


def _name_key(value: str) -> str:
    return " ".join(re.sub(r"[^\w@]+", " ", value.casefold(), flags=re.UNICODE).split())
