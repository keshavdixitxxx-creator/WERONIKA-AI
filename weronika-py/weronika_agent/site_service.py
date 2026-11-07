"""Open, close, focus, and operate website tabs on the user's behalf.

This sits between the site registry (which turns "radio garden" into a URL) and
the managed Chromium window (which owns the real tabs). It never bypasses a
login, a paywall, or a site's terms: it navigates and it can operate a page with
the same visible, approval-gated actions the rest of the worker already uses.
"""

from __future__ import annotations

from typing import Any

from .site_registry import find_site, refusal_for, resolve_target, search_sites, site_catalog
from .tasks import TaskError, clean_text


class SiteError(TaskError):
    """A user-actionable site operation error."""


class SiteService:
    """Registry-backed tab control over the managed browser."""

    def __init__(self, browser) -> None:
        self.browser = browser

    # ------------------------------------------------------------------ read
    def catalog(self) -> dict[str, Any]:
        payload = site_catalog()
        payload["tabs"] = self.tabs()
        return payload

    def tabs(self) -> list[dict[str, str]]:
        try:
            return self.browser.workspace_tabs()
        except Exception:
            return []

    def search(self, query: str) -> list[dict[str, str]]:
        return search_sites(query)

    def resolve(self, name: str) -> dict[str, Any]:
        url, site = resolve_target(name)
        return {
            "url": url,
            "name": site.name if site else url,
            "id": site.id if site else "",
            "known": site is not None,
        }

    # ------------------------------------------------------------- open/close
    def open(self, names: list[str] | str) -> dict[str, Any]:
        """Open one or more named sites, returning the tab ids it created."""
        raw_names = [names] if isinstance(names, str) else list(names or [])
        cleaned = [clean_text(value) for value in raw_names if clean_text(value)]
        if not cleaned:
            raise SiteError("Which website should Weronika open?")
        if len(cleaned) > 10:
            raise SiteError("Weronika opens up to 10 websites at a time.")

        refused = [refusal_for(name) for name in cleaned]
        blocked = [reason for reason in refused if reason]
        if blocked:
            raise SiteError(blocked[0])

        urls: list[str] = []
        labels: dict[str, str] = {}
        for name in cleaned:
            url, site = resolve_target(name)
            if url not in urls:
                urls.append(url)
                labels[url] = site.name if site else url

        try:
            opened = self.browser.open_workspace_urls(urls)
        except Exception as exc:
            raise SiteError(
                "Weronika could not reach her managed browser. Start the worker with "
                "start.bat, then try again. Nothing was opened."
            ) from exc

        tabs = []
        for entry in opened:
            url = str(entry.get("url") or "")
            tabs.append(
                {
                    "id": str(entry.get("id") or ""),
                    "url": url,
                    "name": labels.get(url, url),
                    "status": str(entry.get("status") or ""),
                }
            )
        names_opened = ", ".join(tab["name"] for tab in tabs)
        return {
            "opened": tabs,
            "count": len(tabs),
            "message": f"Opened {names_opened} in the Weronika browser window.",
        }

    def close(self, tab_id: str = "", name: str = "") -> dict[str, Any]:
        """Close one tab by id, or every tab matching a site name."""
        target = clean_text(tab_id)
        label = clean_text(name)

        if not target and label:
            url, site = resolve_target(label)
            wanted_host = _host_of(url)
            matches = [
                tab for tab in self.tabs() if _host_of(str(tab.get("url") or "")) == wanted_host
            ]
            if not matches:
                raise SiteError(f"No open tab is showing {site.name if site else label}.")
            closed = [tab for tab in matches if self.browser.close_workspace_tab(str(tab.get("id") or ""))]
            return {
                "closed": closed,
                "count": len(closed),
                "message": f"Closed {len(closed)} tab(s) for {site.name if site else label}.",
            }

        if not target:
            raise SiteError("Which tab should Weronika close?")
        if not self.browser.close_workspace_tab(target):
            raise SiteError("That tab is already closed or does not belong to Weronika.")
        return {"closed": [{"id": target}], "count": 1, "message": "Closed that tab."}

    def close_all(self) -> dict[str, Any]:
        closed: list[dict[str, str]] = []
        for tab in self.tabs():
            if self.browser.close_workspace_tab(str(tab.get("id") or "")):
                closed.append(tab)
        return {
            "closed": closed,
            "count": len(closed),
            "message": f"Closed {len(closed)} tab(s).",
        }

    def focus(self, tab_id: str = "", name: str = "") -> dict[str, Any]:
        """Bring a tab to the front."""
        target = clean_text(tab_id)
        if not target and clean_text(name):
            url, _ = resolve_target(name)
            wanted_host = _host_of(url)
            matches = [
                tab for tab in self.tabs() if _host_of(str(tab.get("url") or "")) == wanted_host
            ]
            if not matches:
                raise SiteError(f"No open tab is showing {name}.")
            target = str(matches[0].get("id") or "")
        if not target:
            raise SiteError("Which tab should Weronika switch to?")
        if not self.browser.activate_workspace_tab(target):
            raise SiteError("That tab is no longer open.")
        return {"focused": target, "message": "Switched to that tab."}

    def describe(self, name: str) -> dict[str, Any]:
        """Look a name up without opening anything."""
        url, site = resolve_target(name)
        return {
            "url": url,
            "name": site.name if site else url,
            "category": site.category if site else "",
            "note": site.note if site else "",
            "known": find_site(name) is not None,
        }


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.casefold().removeprefix("www.")
