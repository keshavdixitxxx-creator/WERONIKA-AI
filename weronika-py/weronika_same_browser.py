"""
Same-browser automation for Weronika.

User wants automation in the SAME browser where Weronika is running,
not a separate "chrome test" (playwright persistent profile).

We support two modes:

1. Frontend-driven same-tab automation (no Playwright needed):
   - Frontend's weronika-same-browser.js opens target URLs in new tabs via window.open()
     and drives them via injected helpers that use DOM queries + fetch.
   - This works for sites that allow window.opener access (same-browser, same profile cookies).

2. Backend CDP-attach mode (when Chrome is started with --remote-debugging-port=9222):
   - Instead of launching a fresh Chromium, we connect to the existing browser
     via Playwright's connect_over_cdp().
   - This lets python automate the user's real browser tabs.
   - Env: WERONIKA_CDP_ENDPOINT=http://127.0.0.1:9222  or  WERONIKA_SAME_BROWSER=1

If neither is available, we fall back to the old persistent profile but warn.

This module provides backend helpers for CDP mode and exposes endpoint hints for frontend.
"""
from __future__ import annotations
import os, json, time
from typing import Any

CDP_ENDPOINT = os.environ.get("WERONIKA_CDP_ENDPOINT") or os.environ.get("WERONIKA_SAME_BROWSER_ENDPOINT") or "http://127.0.0.1:9222"
SAME_BROWSER_ENV = os.environ.get("WERONIKA_SAME_BROWSER") in ("1","true","yes")

def cdp_available() -> bool:
    if not SAME_BROWSER_ENV:
        # also check if we have playwright and endpoint responds
        pass
    try:
        import requests
        r = requests.get(CDP_ENDPOINT + "/json/version", timeout=2)
        return r.ok
    except Exception:
        return False

def use_cdp() -> bool:
    return SAME_BROWSER_ENV or cdp_available()

def get_browser_context_config():
    """Returns config hint for frontend: how to automate."""
    return {
        "mode": "cdp" if use_cdp() else "frontend",
        "cdp_endpoint": CDP_ENDPOINT if use_cdp() else None,
        "frontend_helper": "/weronika-same-browser.js",
        "message": "Same-browser mode: automation runs in your current browser profile. Start Chrome with --remote-debugging-port=9222 for full CDP control, or let Weronika drive via frontend tabs."
    }

# Backend CDP helpers (optional Playwright)

def _playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception as e:
        raise RuntimeError(f"Playwright needed for CDP mode: {e}")

def connect_to_existing_browser():
    """Returns playwright page connected to user's browser."""
    pw = _playwright()
    p = pw().start()
    try:
        # Try CDP endpoint
        browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
        # first context
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        return p, browser, ctx, page
    except Exception as e:
        try:
            p.stop()
        except: pass
        raise RuntimeError(f"Could not connect to browser at {CDP_ENDPOINT}. Start Chrome with --remote-debugging-port=9222: {e}")

def frontend_automation_spec(action: dict) -> dict:
    """
    Convert backend intent to frontend automation spec that weronika-same-browser.js understands.
    Returns {url, steps:[{type, selector, value}], method}
    """
    app = action.get("app","")
    act = action.get("action","")
    payload = action.get("payload",{})

    if app == "spotify":
        q = payload.get("query","")
        return {
            "url": f"https://open.spotify.com/search/{q.replace(' ','%20')}" if q else "https://open.spotify.com/",
            "steps": [
                {"type":"wait","value":"2000"},
                {"type":"evaluate","code": f"document.querySelector('[data-testid=\"search-input\"]')?.focus(); document.querySelector('[data-testid=\"search-input\"]')&&(document.querySelector('[data-testid=\"search-input\"]').value={json.dumps(q)}, document.querySelector('[data-testid=\"search-input\"]').dispatchEvent(new KeyboardEvent('keydown',{{\"key\":\"Enter\"}})))"},
                {"type":"wait","value":"2500"},
                {"type":"evalClickFirst","selector":"[data-testid*='track'] button, button[data-testid='play-button']"},
            ],
            "frontend": True
        }
    if app == "youtube":
        q = payload.get("query","")
        comment = payload.get("comment")
        steps = [{"type":"goto","value": f"https://www.youtube.com/results?search_query={q.replace(' ','+')}" }]
        steps.append({"type":"wait","value":"2000"})
        steps.append({"type":"click","selector":"a#video-title"})
        steps.append({"type":"wait","value":"1500"})
        if comment:
            steps.extend([
                {"type":"scroll","value":"500"},
                {"type":"click","selector":"#placeholder-area"},
                {"type":"fill","selector":"#contenteditable-root","value": comment},
                {"type":"click","selector":"#submit-button button"},
            ])
        else:
            steps.append({"type":"click","selector":"button.ytp-play-button"})
        return {"url": f"https://www.youtube.com/results?search_query={q}", "steps": steps, "frontend": True}
    if app in ("telegram","whatsapp","instagram"):
        target = payload.get("target") or payload.get("contact") or ""
        msg = payload.get("message") or payload.get("text") or ""
        # frontend will open web app and search target
        base = {"telegram":"https://web.telegram.org/k/","whatsapp":"https://web.whatsapp.com/","instagram":"https://www.instagram.com/direct/inbox/"}[app]
        return {"url": base, "steps": [{"type":"searchContact","value": target}, {"type":"fill","selector":"div[contenteditable=true]","value": msg}, {"type":"press","value":"Enter"}], "frontend": True}
    # fallback: just open app URL
    import weronika_apps
    url = weronika_apps.APPS.get(app,{}).get("url","")
    return {"url": url or f"https://{app}.com", "steps": [], "frontend": True}
