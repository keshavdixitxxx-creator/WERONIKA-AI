#!/usr/bin/env python3
"""
Weronika - same-browser launcher (replaces start.bat)
- No separate "chrome test" browser required; uses your current browser
- Optional Playwright is only needed for fallback/local Chromium mode
- For full same-browser control, run Chrome with --remote-debugging-port=9222
"""
import os, sys, subprocess, webbrowser, time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

print("="*60)
print(" Weronika AI - local agent (same-browser mode)")
print("="*60)

# Check python
print(f" Python: {sys.version.split()[0]}")

# Install deps (quiet, no forced chromium install)
print(" Checking Python packages (first run may take a moment)...")
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", "requirements.txt"], check=False)
    print("  → packages ready")
except Exception as e:
    print(f"  ⚠ pip install skipped: {e}")

# Chromium install is now OPTIONAL — only if you want fallback local browser
try:
    import playwright
    print("  → Playwright available (local browser fallback ready)")
    # Do NOT auto-install chromium aggressively; user can run: playwright install chromium
    # We try to check if chromium is installed, if not, hint
    from pathlib import Path
    # simple hint
    print("  → If you want local-Chromium fallback, run: python -m playwright install chromium")
except ImportError:
    print("  → Playwright not installed (ok for same-browser mode). Frontend automation still works.")
    print("     To enable app-browser fallback: pip install playwright && python -m playwright install chromium")

print("")
print(" Ollama (optional): for private email/DM summaries, keep Ollama running (default model: llama3.2).")
print(" Same-browser tip: to let Weronika control your open Chrome tabs directly,")
print("   start Chrome with: chrome --remote-debugging-port=9222")
print("   (otherwise Weronika opens new tabs in your current profile — also works, just less seamless).")
print("")
time.sleep(1)

# Open browser after slight delay (agent will start)
import threading
def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:8765/"
    try:
        webbrowser.open(url)
        print(f" Opened {url}")
    except Exception as e:
        print(f" Please open manually: {url} ({e})")

threading.Thread(target=open_browser, daemon=True).start()

# Start agent
print(" Starting Weronika agent on http://127.0.0.1:8765/ ...")
print(" Chat, Gmail, Calendar, Drive, Telegram/WhatsApp/Instagram, YouTube/Spotify ready.")
print(" Press Ctrl+C to stop. Your conversation will be saved and resumes next time.")
print("="*60)
try:
    import weronika_agent
    weronika_agent.main()
except KeyboardInterrupt:
    print("\n[weronika] bye — conversation saved. Run python start.py again to continue where you left off.")
except Exception as e:
    print(f"\n[weronika] failed to start: {e}")
    sys.exit(1)
