# weronika-py — Weronika's local agent

This folder is **Weronika's own brain running on your PC**. The web app in `../src`
and `../public` is the hosted/cloud version. This folder is the local version that
can control your Windows machine, run apps, and talk to the cloud brain without
you ever pasting an API key.

Everything the local agent needs is in this one folder, so you can copy
`weronika-py/` to a Windows PC and run it on its own.

```
weronika-py/
├── weronika_agent.py        # the local HTTP server (port 8765) — start here
├── weronika_brain.py        # CLOUD BRAIN client (no API key needed)
├── weronika_automation.py   # OS control, browser automation, file ops, live logs
├── weronika_apps.py         # signed-in app automation (visible Chromium profile)
├── weronika_calls.py        # WhatsApp call assistant (detect + confirm only)
├── weronika_upgrade.py      # self-upgrade proposals (never auto-applies)
├── config.json              # model names, hosted brain URL, power-command switch
├── requirements.txt         # Python packages
├── start.bat                # Windows one-click launcher
├── weronika.html            # the standalone UI (portable copy)
├── public/
│   ├── weronika.html        # the UI the agent serves at http://127.0.0.1:8765/
│   ├── weronika-workspace.js
│   ├── weronika-commands.js
│   ├── weronika-local-prompts.js
│   ├── weronika-media-intent.js
│   ├── technical-models.js
│   ├── technical-viewer.js
│   ├── favicon.ico
│   └── robots.txt
└── tests/                   # test_assistant.py, test_weronika_apps.py
```

## Run it on Windows

1. Install Python 3.11+ and tick **Add to PATH**.
2. Double-click **`start.bat`**.
3. Your browser opens at <http://127.0.0.1:8765/> — that is Weronika, local.

The agent also serves the hosted app's API shape at `/api/public/brain`, so the
same HTML works online and offline.

## Run it anywhere (macOS / Linux / CI)

```bash
cd weronika-py
python -m pip install -r requirements.txt
python weronika_agent.py
```

Then open <http://127.0.0.1:8765/>.

## Cloud brain

`weronika_brain.py` is the cloud brain. It sends the conversation to the hosted
Weronika app (`config.json → hosted_brain`) and streams the reply back. **The API
key stays on the server** — nothing secret is stored in this folder.

Related cloud-brain code that must stay in the web app (because it _is_ the
server that holds the key):

| File                                | Role                                |
| ----------------------------------- | ----------------------------------- |
| `../src/routes/api/public/brain.ts` | hosted `/api/public/brain` endpoint |
| `../src/lib/brain-stream.server.ts` | streaming + prompt/creator identity |
| `../src/lib/relay.server.ts`        | gateway relay + API-key redaction   |
| `../src/lib/ai-gateway.server.ts`   | gateway fetch helper                |

## Safety defaults (on purpose)

- Private app text never leaves the PC: `/api/local/brain` uses Ollama only, no
  cloud fallback.
- `weronika-calls.py` never answers a call without explicit confirmation.
- `weronika_upgrade.py` returns a diff and **writes nothing** until approved.
- Power commands (shutdown/restart/sleep) are gated by `allow_power_commands`
  in `config.json`.

## Tests

```bash
# from the repo root
python -m unittest discover -s weronika-py/tests -p "test_*.py"
```

## Keeping `weronika.html` in sync

`../public/weronika.html` is the **source of truth** for the UI. The two copies
here (`weronika.html` and `public/weronika.html`) are generated from it. After
editing the UI, run from the repo root:

```bash
npm run sync:standalone
```
