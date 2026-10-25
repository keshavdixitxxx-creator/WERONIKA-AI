# Weronika local messaging automation

A standalone Python package beside (not inside) the hosted cloud-brain implementation. It uses the visible web UI in a persistent local Chromium profile for WhatsApp first, with adapters planned/started for Telegram, Instagram Direct, Facebook Messenger, and X. It does not call private messaging APIs.

## Safety model

- A request is parsed into one explicit platform, recipient, and exact message text.
- The app's visible search results are ranked conservatively. Fuzzy matches, multiple matches, and duplicate display names require the user to choose a result; the automation does not guess.
- A selected chat must have a matching visible header before the message is typed.
- Preparation only fills the composer. It does not click Send.
- The exact recipient and message are shown in the local UI. Sending requires a separate **Confirm & send** click or the explicit text `confirm send` / `send it`.
- Before sending, the composer is checked against the approved text. After clicking Send, a failed check is reported as unverified and is never automatically retried.
- Cancel tries to clear the composer only when its current text still exactly matches the original draft.

This is still UI automation, not a supported platform integration. Social networks may change their layouts or limit automated access; the adapter then stops and asks the user to check the page. Keep platform use compliant with each platform's terms and applicable law.

## Run locally

Python 3.10+ is required. From this folder:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python start.py
```

Open `http://127.0.0.1:8765/`. The API server binds only to loopback and serves this local UI; it is not the hosted website or cloud brain. On the first request for an app, Weronika opens a visible browser window. Sign in to that service yourself, then return and retry. Use the same computer and browser session that runs the local service.

To use another port, run `python start.py --port 8766`. You may choose another local browser-profile directory with `--profile-dir PATH`.

## Browser sessions and private data

Each platform has a separate persistent profile beneath `~/.weronika/messaging-profiles/` by default. This keeps sign-in state on the local device; it also means session cookies are stored there by the browser. Do not share that directory. Close Weronika and remove the platform's profile directory if you want to sign out/reset that browser profile. The request text and drafts are held in memory for up to ten minutes and are not written to a local database or logs.

The local app does not proxy messages to the hosted brain. The existing hosted cloud-brain chat remains separate and unchanged.

## Current coverage

- **WhatsApp Web:** first-priority implementation.
- **Telegram Web, Instagram Direct, Facebook Messenger, X:** visible UI adapters and common workflow; the sites' live selectors may need adjustment and should be verified against the user's current account before relying on them.
- Contact parsing/matching and the confirmation-first workflow are covered by unit tests using local fakes; the tests do not log into or send messages on real platforms.

## Tests

```sh
python -m unittest discover -s tests -v
```

## Reference

OpenDroid (`https://github.com/yashab-cyber/opendroid`) is an Android/Kotlin accessibility agent. Its ideas around contact resolution, safe UI interaction, and post-action verification informed this package; no OpenDroid source code is copied here.
