# Weronika local automation worker

This package is the local Python worker behind Weronika's **existing animated orb UI**. It does not replace the orb with a second chat page. On Windows, `start.bat` starts a loopback-only server that serves the existing `public/weronika.html`, its public assets, and the local automation API on the same origin. The orb continues to use the hosted cloud brain for conversation and task planning; supported plans are then handed to the local Python worker and progress is streamed back into the orb chat.

## Request flow

1. You ask Weronika for an action in the orb text or voice chat.
2. The hosted brain classifies the request and returns a structured plan. The orb shows its acknowledgement and step list.
3. The local worker validates the plan and runs an allow-listed messaging workflow using the visible app website. Progress appears in the same orb chat.
4. Weronika searches for the intended contact. Similar or duplicate names require your selection.
5. The worker opens and verifies the chat, prepares the exact message, and shows it in the orb. It does not send during preparation.
6. Sending requires your separate `confirm send` / `send it` reply. The worker reports whether the send was verified.

The orb exposes direct messaging on WhatsApp Web, Telegram Web, Instagram Direct, Facebook Messenger, and X, plus two dedicated feature panels: BLUEPRINT and WORKSPACE. Workspace accepts a natural-language build prompt through the hosted cloud brain, then opens up to ten multilingual code/text files as unsaved editor drafts; files are written only when you choose Save. The general-purpose browser tab UI has been removed. Chromium remains an internal requirement for visible messaging automation.

## Safety and privacy

- The worker binds only to `127.0.0.1`; orb pages call its local APIs through same-origin routes. A hosted web page cannot call the local worker directly.
- Similar-name contacts are never silently selected. The open chat header and exact composer text are checked before any send action.
- The local worker only clicks Send after explicit approval. An uncertain result is reported and never automatically retried.
- Each messaging platform uses a local persistent browser profile under `~/.weronika/`; session cookies stay on this device. Do not share those profile directories.
- Workspace code/text files are stored under `~/.weronika/workspace/`. Python files can be run only after a separate confirmation dialog. This is not a sandbox: confirmed code can access this device and its files, so inspect code before running it.
- VRM uploads and photos are handled in the browser and are not saved to the workspace. Blueprint can report local CPU/RAM and NVIDIA GPU details through a loopback-only preflight, but it does not download or run a model. A photo is currently converted into a shallow brightness-map relief, not a full 3D object reconstruction.
- Message drafts are held in memory for up to ten minutes. Message bodies are not written to local files or request logs.
- Messaging is visible-UI automation, not an official platform integration. Website selectors may change; when the worker cannot verify the right UI, it stops safely.

## Windows quick start

Install Python 3.10+ and enable **Add Python to PATH**, then double-click `start.bat` in this folder. The first run creates `.venv`, installs the Python requirements and Playwright Chromium, then opens the existing orb UI at `http://127.0.0.1:8765/`. Later runs skip installation and start the orb and worker. Keep the command window open while using Weronika; press Ctrl+C there to stop it.

If setup is interrupted or dependencies need reinstalling, delete `.venv` and run `start.bat` again. Sign in to messaging services yourself in the visible browser window opened when the first action needs that app.

## Manual start (macOS/Linux or Windows)

From this folder:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python start.py --open-browser
```

The existing hosted orb URL remains available for ordinary cloud chat. To use local automation, open the orb served locally by this worker; the hosted page cannot access your computer's loopback service. The hosted cloud-brain deployment must include the `automation-plan` task added in this change; until that version is deployed, the local worker will reject incomplete or non-JSON plans rather than guess.

## Tests

```sh
python -m unittest discover -s tests -v
```

OpenDroid (`https://github.com/yashab-cyber/opendroid`) informed the contact-resolution and stepwise UI-verification ideas. It is an Android/Kotlin project; no OpenDroid source code is copied here.
