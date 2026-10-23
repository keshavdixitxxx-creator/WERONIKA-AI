#!/usr/bin/env python3
"""
Weronika single-entry launcher — starts all local brains together.

User asked: "make one py file in py folder when which i start so it make other py file start to like automation cloud and other tooo"
This file is that single entry point: it launches:

  - weronika_agent.py (HTTP server on 8765, serves UI, handles Gmail/Calendar/Drive, automation, memory)
  - (optional) watches Ollama availability
  - (optional) same-browser helper hint

You can start it with:
  python weronika_launcher.py
  python weronika_launcher.py --no-browser
  bun run dev:py  (package.json also proxies here)

It replaces the old start.bat (which forced chromium install + separate chrome test).
Now everything runs in one Python process and opens a new tab in YOUR current browser.
"""
import argparse, os, subprocess, sys, time, threading, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def check_python():
    print(f"[weronika-launcher] Python {sys.version.split()[0]} on {sys.platform}")

def install_deps_if_needed():
    # Only if requests missing
    try:
        import requests  # noqa: F401
    except ImportError:
        print("[weronika-launcher] Installing requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", "requirements.txt"], check=False)
    else:
        print("[weronika-launcher] Dependencies OK (requests found)")

def open_browser_delayed(delay=1.6):
    def _do():
        time.sleep(delay)
        url = "http://127.0.0.1:8765/"
        try:
            webbrowser.open(url)
            print(f"[weronika-launcher] Opened {url} in your current browser (new tab)")
        except Exception as e:
            print(f"[weronika-launcher] Please open manually: {url} ({e})")
    threading.Thread(target=_do, daemon=True).start()

def main():
    parser = argparse.ArgumentParser(description="Weronika single launcher")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print("="*64)
    print(" Weronika — single launcher (same-browser, no chrome test)")
    print("="*64)
    check_python()
    install_deps_if_needed()

    if not args.no_browser:
        open_browser_delayed()

    print(f"[weronika-launcher] Starting unified agent on http://127.0.0.1:{args.port}/")
    print("[weronika-launcher] Components: HTTP agent + Google (Gmail/Drive/Calendar) + same-browser automation + persistent memory + cloud brain")
    print("[weronika-launcher] Tips:")
    print("  • All automation opens new tabs in YOUR Chrome (no separate Chromium)")
    print("  • For direct tab control: chrome --remote-debugging-port=9222")
    print("  • Gmail/Calendar/Drive: Settings → Google → paste OAuth Client ID/Secret → Connect")
    print("  • Ollama optional: if offline, private summaries use cloud brain (friendly, not error)")
    print("  • Say: 'open youtube and play Barsaat', 'play Sahiba on spotify', 'check my inbox'")
    print("="*64)

    # Import and run the main agent (it already hosts all services)
    # Override port if needed via env
    if args.port != 8765:
        os.environ["WERONIKA_PORT"] = str(args.port)
        # weronika_agent reads PORT constant; monkey-patch before import
        import weronika_agent as agent
        agent.PORT = args.port
        agent.main()
    else:
        import weronika_agent
        weronika_agent.main()

if __name__ == "__main__":
    main()
