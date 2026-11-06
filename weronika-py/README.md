# Weronika local automation worker

This package is the local Python worker behind Weronika's **existing animated orb UI**. It does not replace the orb with a second chat page. On Windows, `start.bat` starts a loopback-only server that serves the existing `public/weronika.html`, its public assets, and the local automation API on the same origin. The orb continues to use the hosted cloud brain for conversation and task planning; supported plans are then handed to the local Python worker and progress is streamed back into the orb chat.

## Request flow

1. You ask Weronika for an action in the orb text or voice chat.
2. The hosted brain classifies the request and returns a structured plan. The orb shows its acknowledgement and step list.
3. The local worker validates the plan and runs an allow-listed messaging workflow using the visible app website. Progress appears in the same orb chat.
4. Weronika searches for the intended contact. Similar or duplicate names require your selection.
5. The worker opens and verifies the chat, prepares the exact message, and shows it in the orb. It does not send during preparation.
6. Sending requires your separate `confirm send` / `send it` reply. The worker reports whether the send was verified.

The orb exposes direct messaging on WhatsApp Web, Telegram Web, Instagram Direct, Facebook Messenger, and X, reply watch for WhatsApp Web and Telegram Web, plus four dedicated feature panels: BLUEPRINT, WORKSPACE, REPLY WATCH and SKILLS. Workspace accepts a natural-language build prompt through the hosted cloud brain, then opens up to ten multilingual code/text files as unsaved editor drafts; files are written only when you choose Save. The general-purpose browser tab UI has been removed. Chromium remains an internal requirement for visible messaging automation.

## Reply watch (new)

The orb's **◎ REPLY WATCH** panel answers the everyday problem: someone messages
you, you are busy or away, and the chat sits unanswered. Weronika watches only the
chats you name, tells you when a message is still waiting, and can prepare a reply
for you to approve.

1. **Name the chat.** In the panel, choose WhatsApp or Telegram, type the contact or
   group name (or tick _Watch every visible chat_), pick a mode and how long to wait.
   You can also just say it: “Watch my WhatsApp chat with Boss.”
2. **Weronika reads only that chat.** Every few seconds she opens the chat you named
   in the Weronika browser window and looks at the newest bubbles. The conversation
   that existed when you started watching is history, not a new request for a reply.
3. **She stops when you have answered.** If the newest bubble in that chat is yours,
   nothing is reported. If the other person wrote last and the wait time has passed,
   the chat becomes a _waiting_ item for you.
4. **Two modes:** _Ask me what to reply_ tells you and waits for your words;
   _Suggest a reply_ also drafts wording in your language. Either way the suggestion
   is text in the orb, never a send.
5. **Approval is the same as before.** The exact text is typed into the chat only
   after you give it, and the visible draft is sent only when you answer
   `confirm send` / `send it`. `leave it`, `cancel`, `hold on`, `who is waiting`
   and `stop watching` all work in the chat box.

Phrases that turn it on: “watch my WhatsApp chat with Boss”, “keep an eye on Telegram
chat with Rahul and reply for me if I can’t”, “watch the Family group on WhatsApp and
you can suggest a reply”. Delay words are understood: _in 10 minutes_, _after an hour_.
Urgent-only watching is available with _only if it’s urgent_.

Replies beyond a plain answer can use the same flow: files inside
`~/.weronika/workspace` (for example a leave policy) can be read to answer a question
in the chat, and one-time codes can be shown to you before you decide to forward one.

**Honest limits.** Reply watch is visible-UI automation on WhatsApp Web and Telegram
Web only, with the browser window open. Instagram's web app has no dependable message
list, so the worker refuses to read it instead of guessing (sending a prepared draft
there still works). There is no personal-account WhatsApp API and Telegram user
accounts should be automated through the official Bot API, so this worker reads what
you already signed in to and keeps that session on this device. Nothing is ever sent
without your confirmation.

## Browser tasks (search, open, play, post)

The worker can also run a browser plan instead of a single message. The orb sends
the request to the cloud brain, which is asked for **ordered steps**, and the worker
executes them one at a time in the visible Chromium window:

| Step                 | What it does                                                                                                      | Approval            |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------- |
| `search`             | Searches the web for the exact words you said                                                                     | none                |
| `open_result`        | Opens the top result already shown on the search page                                                             | none                |
| `open_url`           | Opens a specific public http(s) address                                                                           | none                |
| `read_page`          | Reads the visible text of the open page back to the orb                                                           | none                |
| `play_video`         | Opens YouTube, picks the first result for your words, starts playback, skips a pre-roll ad if a Skip button shows | none                |
| `comment` / `reply`  | Types your exact comment into the comment box                                                                     | **yes** — `confirm` |
| `like` / `subscribe` | Presses that account control                                                                                      | **yes** — `confirm` |

Examples:

- “Search for today’s weather in Ghaziabad and open the first result.”
- “Play Kesariya on YouTube.” — any description works; YouTube’s own first result is used.
- “Open the first result and summarize it.” — `open_result`, then `read_page`.
- “Comment on this video: great explanation.” — typed, shown, then submitted only after `confirm`.
- “Open github in chrome.” — opens in **your own** Edge/Chrome/Firefox instead of the worker window.

Plans are limited to 8 steps and the action names are fixed, so a model cannot invent
a step the worker will not understand. Every plan is listed before it runs, a failed
step stops the plan, and a task expires after 15 minutes without submitting anything
pending.

**Honest limits.** “Search” opens a real search page and reads the results; it is not a
hidden answer engine, so a summary is only as good as the page it opened. YouTube
decides what “play this” means, so an ambiguous description may play something else —
the orb shows exactly which title was started. Comments, likes, and subscriptions need
you to be signed in to that site in the Weronika browser window, and a site that changes
its buttons makes the worker stop instead of guessing. Edge/Chrome/Firefox opening
launches the browser you already have installed; it does not script that browser the way
the worker window is scripted.

## Safety and privacy

- The worker binds only to `127.0.0.1`; orb pages call its local APIs through same-origin routes. A hosted web page cannot call the local worker directly.
- Similar-name contacts are never silently selected. The open chat header and exact composer text are checked before any send action.
- The local worker only clicks Send after explicit approval. An uncertain result is reported and never automatically retried.
- Each messaging platform uses a local persistent browser profile under `~/.weronika/`; session cookies stay on this device. Do not share those profile directories.
- Workspace files use `~/.weronika/workspace/` when opened with `start.bat`. If the local worker is unavailable, files can still be saved to browser-local storage on that device/browser; those files do not sync to the PC workspace or other browsers. Python execution is available only through the local worker and requires a separate confirmation dialog. It is not a sandbox: confirmed code can access this device and its files, so inspect code before running it.
- VRM uploads and photos are handled locally and are not saved to the workspace. Blueprint reports CPU/RAM and NVIDIA GPU details through a loopback-only preflight. Photo relief remains an instant browser-only preview; optional TripoSR can generate an actual single-image mesh on the local CPU after separate setup. The generated GLB and temporary input are not retained by the worker.
- Reply-watch state (which chats you watch, the last message that triggered an item, the draft) stays in worker memory. Message bodies are not written to local files or request logs.
- Reply watch pauses automatically while an older draft is still open in the orb, so it cannot overwrite or send your prepared text. Alerts never click or send anything.
- Message drafts are held in memory for up to ten minutes. Message bodies are not written to local files or request logs.
- Messaging is visible-UI automation, not an official platform integration. Website selectors may change; when the worker cannot verify the right UI, it stops safely. Direct text messaging is supported across WhatsApp, Telegram, Instagram, Messenger, and X; incoming call detection, answering, live call audio, and call summaries are not implemented. Never infer permission to answer a call from a prior preference; any future call flow must ask about each call and tell the other participant they are speaking with an AI.

## Windows quick start

Install Python 3.10+ and enable **Add Python to PATH**, then double-click `start.bat` in this folder. The first run creates `.venv`, installs the Python requirements and Playwright Chromium, then opens the existing orb UI at `http://127.0.0.1:8765/`. Later runs skip installation and start the orb and worker. Keep the command window open while using Weronika; press Ctrl+C there to stop it.

If setup is interrupted or dependencies need reinstalling, delete `.venv` and run `start.bat` again. Sign in to messaging services yourself in the visible browser window opened when the first action needs that app.

## Optional local AI photo-to-3D

The default photo action is a browser-based relief preview. To generate an actual mesh locally, first run `start.bat` once, then run `setup-blueprint.bat` and type `YES` at its confirmation prompt. This installs CPU-only PyTorch and the MIT-licensed TripoSR source in the Weronika Python environment; the model weights download from Hugging Face on first generation. Photos are sent only to the loopback worker and are removed with the temporary job directory.

CPU inference may take several minutes per image and can use substantial system memory. A C++ build toolchain may be required for `torchmcubes` on Windows; if compilation fails, install Visual Studio Build Tools with the C++ workload and retry. TripoSR produces a real single-view mesh/GLB, but unseen sides are inferred and its output is not guaranteed to match Meshy AI's quality. The browser provides **GENERATE 3D MODEL** only when the local worker detects a completed setup; **RELIEF PREVIEW** remains available separately.

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

Suggestion wording in reply watch uses the hosted brain (`--brain-endpoint`, default
the public Weronika route) only to draft a sentence; pass `--brain-endpoint off` to
keep every suggestion on this device, where a small built-in phrase set is used
instead. The chat text that is sent for a suggestion is the watched message only.

The existing hosted orb URL remains available for ordinary cloud chat. To use local automation, open the orb served locally by this worker; the hosted page cannot access your computer's loopback service. The hosted cloud-brain deployment must include the `automation-plan` task added in this change; until that version is deployed, the local worker will reject incomplete or non-JSON plans rather than guess.

## Tests

```sh
python -m unittest discover -s tests -v
```

OpenDroid (`https://github.com/yashab-cyber/opendroid`) informed the contact-resolution and stepwise UI-verification ideas. It is an Android/Kotlin project; no OpenDroid source code is copied here.
