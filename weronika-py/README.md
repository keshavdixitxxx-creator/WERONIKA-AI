# weronika-py — Weronika's local agent

This folder is **Weronika's own brain running on your PC**. The web app in `../src`
and `../public` is the hosted/cloud version. This folder is the local version that
can control your machine, talk to Gmail/Calendar/Drive, and automate Telegram/WhatsApp/Instagram/YouTube/Spotify
without you ever pasting an API key.

Everything the local agent needs is in one folder — copy `weronika-py/` to any PC (Windows/macOS/Linux) and run it.

```
weronika-py/
├── weronika_agent.py         # local HTTP server on :8765 — start here
├── weronika_brain.py         # cloud brain client (no API key needed)
├── weronika_automation.py    # OS control, file ops, browser helper, live logs
├── weronika_apps.py          # signed-in app automation (same-browser + fallback Chromium)
├── weronika_calls.py         # WhatsApp/Telegram call assistant (confirm-only)
├── weronika_upgrade.py       # self-upgrade proposals (never auto-applies)
├── weronika_google.py        # Gmail + Calendar + Drive via Google APIs (OAuth)
├── weronika_memory.py        # persistent chat — survives shutdowns
├── weronika_intent.py        # universal intent parser (any language, any app)
├── weronika_same_browser.py  # same-browser automation (no separate Chrome test)
├── config.json               # models, hosted brain URL, power commands
├── requirements.txt          # python deps
├── start.py                  # cross-platform launcher (recommended)
├── start.sh                  # macOS/Linux launcher
├── start.bat                 # Windows one-click (wraps start.py, no forced Chromium install)
├── weronika.html             # standalone UI (portable)
├── public/                   # UI the agent serves at http://127.0.0.1:8765/
│   ├── weronika.html
│   ├── weronika-workspace.js / weronika-commands.js etc
│   ├── weronika-google.js    # Gmail/Calendar/Drive UI
│   ├── weronika-memory.js    # persistent chat UI
│   ├── weronika-same-browser.js
│   └── weronika-automation.js
└── tests/
```

## Run it

**Recommended (any OS):**
```bash
cd weronika-py
pip install -r requirements.txt
python start.py
# or: python weronika_agent.py
```
Then open http://127.0.0.1:8765/

**Windows double-click:** double-click `start.bat` (now same-browser, no forced Chromium install).

**macOS/Linux:**
```bash
./start.sh
```

The agent also serves the hosted app's API at `/api/public/brain`, so the same HTML works online and offline.

## Same-browser automation (no "chrome test")

Old launcher forced `playwright install chromium` and opened a separate test browser.  
Now automation runs in **your current browser/profile** — where you already logged in:

- Weronika opens targets in new tabs via `window.open()` (keeps your cookies).
- For YouTube/Spotify it navigates to search URLs with query prefilled: e.g. `https://open.spotify.com/search/Barsaat`.
- For Telegram/WhatsApp/Instagram it opens `web.telegram.org/k/`, `web.whatsapp.com`, `instagram.com/direct/inbox/`.

For **full tab control** (let Python drive your open Chrome tabs), start Chrome with:
```
chrome --remote-debugging-port=9222
# or on macOS: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
# then set: export WERONIKA_SAME_BROWSER=1   or   export WERONIKA_CDP_ENDPOINT=http://127.0.0.1:9222
python start.py
```
Fallback local Chromium profile still works if you run `python -m playwright install chromium`.

## Google: Gmail + Calendar + Drive

Weronika can now **read, write, organize, delete** via official Google APIs:

1. In Google Cloud Console → APIs & Services → Credentials → Create **OAuth 2.0 Client ID** (Web app).
   - Add Authorized redirect URI: `http://127.0.0.1:8765/api/google/callback`
   - Enable APIs: **Gmail API, Google Calendar API, Google Drive API**.

2. In Weronika → Settings → **Google** panel, paste Client ID + Secret → **Save Google Config** → **Connect Google**.

3. Try:
   - “check my gmail” / “send email to boss@… saying on leave today”
   - “plan my day” (Calendar → day plan) / “recognize me through calendar” (inferred patterns)
   - “organize my Drive” / “list Drive files” / “delete report.pdf from Drive” / “show storage”

Tokens are stored locally (`~/.weronika/google_tokens.json` base64) and refreshed automatically.
Disconnect anytime with **Disconnect** button or `POST /api/google/disconnect`.

**Direct API:**
```
GET  /api/google/status
POST /api/google/config   {client_id, client_secret}
GET  /api/google/auth?service=all|gmail|calendar|drive
GET  /api/google/callback?code=...
POST /api/google/action   {service:"gmail"|"calendar"|"drive", action:"list"|"send"|"plan"|"organize"|"delete"|"storage", params:{}}
POST /api/google/disconnect
```

## Persistent chat (shutdown → continue)

Your conversation now **survives refreshes and shutdowns**:
- Saved to `weronika-py/memory/conversation.json` and `localStorage: weronika.conversationHistory.v2`
- On next launch, Weronika resumes where you left off.
- Clear via Settings → **Clear Chat History** (also calls `POST /api/memory/clear`).

APIs:
```
GET  /api/memory/history   → {history, context}
POST /api/memory/history   {history:[...]}
POST /api/memory/append    {role, content}
GET  /api/context/whoami   → calendar-based recognition + profile
GET  /api/same-browser/status
```

## Universal automation (every chat & channel)

Say in **any language**:

- Telegram/WhatsApp/Instagram:
  `open telegram and make a message to boss that I am on leave today and send him`
  `send whatsapp message to mom saying happy birthday`
  `check instagram messages from rahul`
  → Opens web app, finds contact, drafts message, asks confirmation before sending. Reading is available for all chats/channels.

- YouTube:
  `open youtube and play the song Barsaat` / `play Believer on youtube`
  `play a video of Techno Gamer where he was playing GTA 5 and make a comment there that it is great`

- Spotify:
  `play the Sahiba` / `play Barsaat` / `play Believer`
  → Any song name without platform defaults to **Spotify** (user request). Explicit “on youtube” goes to YouTube.

All via `POST /api/automation/universal {message}` which returns intent + `spec:{url, steps}` that the frontend opens in same browser.

Private reading (Gmail/DMs/Calendar) defaults to **Ollama** when available (`ollama run llama3.2`), no cloud fallback for private text.

## Cloud brain

`weronika_brain.py` streams to the hosted Weronika app (`config.json → hosted_brain`). API key stays on server.

## Safety defaults

- Private app text never leaves PC: `/api/local/brain` uses Ollama only.
- Send/EventSave/CallAnswer need **confirmation**.
- Upgrade proposals are diff-only until approved.
- Power commands gated by `allow_power_commands`.

## Tests

```bash
python -m unittest discover -s weronika-py/tests -p "test_*.py"
npm run test:js
```

## Syncing UI

`../public/weronika.html` is source of truth. After editing UI:
```bash
npm run sync:standalone
```
