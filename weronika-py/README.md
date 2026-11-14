# Weronika local automation worker

This package is the local Python worker behind Weronika's **existing animated orb UI**. It does not replace the orb with a second chat page. On Windows, `start.bat` starts a loopback-only server that serves the existing `public/weronika.html`, its public assets, and the local automation API on the same origin. The orb continues to use the hosted cloud brain for conversation and task planning; supported plans are then handed to the local Python worker and progress is streamed back into the orb chat.

## Request flow

1. You ask Weronika for an action in the orb text or voice chat.
2. The hosted brain classifies the request and returns a structured plan. The orb shows its acknowledgement and step list.
3. The local worker validates the plan and runs an allow-listed messaging workflow using the visible app website. Progress appears in the same orb chat.
4. Weronika searches for the intended contact. Similar or duplicate names require your selection.
5. The worker opens and verifies the chat, prepares the exact message, and shows it in the orb. It does not send during preparation.
6. Sending requires your separate `confirm send` / `send it` reply. The worker reports whether the send was verified.

Simple commands skip the cloud brain altogether: “open Notepad”, “open Chrome and VS Code”, “play Kesariya on Spotify” and “tell me the news” are understood in the orb page and handed straight to the worker (see [Opening apps, music, headlines](#opening-apps-music-headlines)).

The orb exposes direct messaging on WhatsApp Web, Telegram Web, Instagram Direct, Facebook Messenger, and X, reply watch for WhatsApp Web and Telegram Web, plus four dedicated feature panels — BLUEPRINT and WORKSPACE on the main screen, REPLY WATCH and SKILLS under SETTINGS → Tools. Workspace is a code editor in the shape of VS Code: a statement typed there goes to the orb, the orb passes it to the hosted cloud brain, and up to ten code/text files come back into the editor as unsaved drafts; files are written only when you choose SAVE or SAVE ALL. The general-purpose browser tab UI has been removed. Chromium remains an internal requirement for visible messaging automation.

## Reply watch

The orb's **◎ REPLY WATCH** panel answers the everyday problem: someone messages
you, you are busy or away, and the chat sits unanswered. Weronika watches only the
chats you name, tells you when a message is still waiting, and asks: **“Should I
reply, or will you?”** If you choose her, she writes the reply, opens the chat, sends
it and shows you the exact text. Otherwise she can prepare your own words for you to
approve.

1. **Name the chat.** In the panel, choose WhatsApp or Telegram, type the contact or
   group name (or tick _Watch every visible chat_), pick a mode and how long to wait.
   You can also just say it: “Watch my WhatsApp chat with Boss.”
2. **Weronika reads only that chat.** Every few seconds she opens the chat you named
   in the Weronika browser window and looks at the newest bubbles. The conversation
   that existed when you started watching is history, not a new request for a reply.
3. **She stops when you have answered.** If the newest bubble in that chat is yours,
   nothing is reported. If the other person wrote last and the wait time has passed
   (one minute from the orb chat, unless you say “immediately” or “after 5 minutes”),
   the chat becomes a _waiting_ item for you. The orb keeps checking while its tab is
   in the background, says the question aloud, and shows a desktop notification if
   you allowed notifications.
4. **Two modes:** _Ask me: Weronika or me?_ shows the message and the question;
   _…and show the reply she would send_ also shows her wording next to the question.
5. **“Weronika replies” / “you reply”.** `POST /api/watch/delegate`. She reads the
   chat again and sends nothing if you answered in the meantime. The wording is the
   suggestion you already saw, or else a new one from the cloud brain's `reply-draft`
   task: a short, neutral message in your name, without her own personality. Then
   the usual path runs: the chat is found and verified, the exact text is typed and
   checked, and it is sent once. Your choice covers that one message only. If several
   chats match the name she asks for the number first.
6. **“I'll reply”** closes the item without sending. `reply: your words` prepares your
   own text, which is sent only when you answer `confirm send` / `send it`.
   `leave it`, `cancel`, `hold on`, `who is waiting` and `stop watching` all work in
   the chat box.

Weronika sends wording you have not seen only when the brain itself confirms that it
wrote a message in your name (the response header `X-Weronika-Task: reply-draft`). A
hosted brain that is older than this worker answers the same request as ordinary
chat, in Weronika's own voice, and confirms nothing; that text is prepared and shown,
and waits for `confirm send`. The few built-in phrases that stand in for a suggestion
when the brain is offline are only ever shown, never sent unseen.

Phrases that turn it on: “watch my WhatsApp chat with Boss”, “watch all my Telegram
chats”, “keep an eye on Telegram chat with Rahul and reply for me if I can’t”, “watch
the Family group on WhatsApp and you can suggest a reply”. Delay words are understood:
_immediately_, _after 5 minutes_, _after an hour_. Urgent-only watching is available
with _only if it’s urgent_. A plain request of this kind is understood in the orb page
and needs no cloud planner.

Replies beyond a plain answer can use the same flow: files inside
`~/.weronika/workspace` (for example a leave policy) can be read to answer a question
in the chat, and one-time codes can be shown to you before you decide to forward one.

**Honest limits.** Reply watch is visible-UI automation on WhatsApp Web and Telegram
Web only, with the browser window open. Instagram's web app has no dependable message
list, so the worker refuses to read it instead of guessing (sending a prepared draft
there still works). There is no personal-account WhatsApp API and Telegram user
accounts should be automated through the official Bot API, so this worker reads what
you already signed in to and keeps that session on this device. Nothing is sent
unless you confirm the exact text or choose “Weronika replies” for that one message.
A reply she writes is a short general answer: she knows what the other person wrote,
not your plans, so check what she sent. Calls are not handled at all.

## Opening apps, music, headlines

| Route                                                                          | What it does                                                                                                                                                     |
| ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/open` `{targets: ["notepad", {"name": "calendar", "kind": "app"}]}` | Opens each name as a desktop program or as a site. Every name is decided first, and one unknown name opens nothing. Up to 10 targets and 5 programs per request. |
| `POST /api/apps/music` `{service: "spotify", query}`                           | Opens Spotify (the installed program, else the web player) on a search for the song. Spotify does not let another program press play.                            |
| `GET /api/news?topic=&lang=&country=`                                          | Headlines from the public Google News feed, read-only.                                                                                                           |

How a program is started (`weronika_agent/apps.py`):

- The Windows tools (Notepad, Calculator, Paint, File Explorer, Command Prompt,
  PowerShell, Task Manager, Settings, Control Panel, Snipping Tool, Camera, Clock…)
  start through `cmd /c start "" <fixed name>` or a fixed `ms-…:` address. macOS uses
  `open -a`, Linux the first installed program of a short list.
- Installed programs (Chrome, Edge, VS Code, Word, Spotify, Discord…) are found in the
  Start menu shortcuts and the system's app list, by exact name first and by a unique
  partial match otherwise.
- Photos, Calendar, Mail, Maps and Store mean the Google site unless you say “app”
  (“open the calendar app”). “Open WhatsApp” / “open Telegram” show Weronika's own
  signed-in window for that service, which is also how the account is connected.
- What you say is never passed to a command line. Only fixed commands and shortcut
  files found on this computer are started, and names with path or shell characters
  are refused. These routes answer only requests addressed to the loopback host.

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
- Weronika's conversation memory is mirrored to one private file, `~/.weronika/memory/weronika-memory.json` (owner-only permissions, at most 2 MB, replaced atomically), so she still knows the conversation after the computer was shut down, even in a browser whose own storage is empty. The orb reads and writes it through `GET`/`POST /api/memory`, which answer only same-device requests addressed to the loopback host. The file holds what you said to Weronika by chat, by voice, and from the Workspace, plus her replies and short long-term notes. Names and message text from messaging and reply watch are never in it, and neither is anything from Gmail. Switching memory off or choosing CLEAR MEMORY AND CHAT in SETTINGS → Memory empties the file as well. Use those controls to make Weronika forget: deleting only the file does not, because the browser's own copy writes it again.
- Workspace files use `~/.weronika/workspace/` when opened with `start.bat`. If the local worker is unavailable, files can still be saved to browser-local storage on that device/browser; those files do not sync to the PC workspace or other browsers. Python execution is available only through the local worker and requires a separate confirmation dialog. It is not a sandbox: confirmed code can access this device and its files, so inspect code before running it.
- VRM uploads and photos are handled locally and are not saved to the workspace. Blueprint reports CPU/RAM and NVIDIA GPU details through a loopback-only preflight. Photo relief remains an instant browser-only preview; optional TripoSR can generate an actual single-image mesh on the local CPU after separate setup. The generated GLB and temporary input are not retained by the worker.
- Reply-watch state (which chats you watch, the last message that triggered an item, the draft) stays in worker memory. Message bodies are not written to local files or request logs.
- Reply watch pauses automatically while an older draft is still open in the orb, so it cannot overwrite or send your prepared text. Alerts never click or send anything. A reply goes out without a typed confirmation only after you chose “Weronika replies” for that one message, and only with wording you saw or wording the cloud brain confirmed as a reply draft.
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
instead. With the brain off, “Weronika replies” can only send a suggestion you were
shown. The chat text that is sent for a suggestion is the watched message only (up to
the last three waiting messages).

The existing hosted orb URL remains available for ordinary cloud chat. To use local automation, open the orb served locally by this worker; the hosted page cannot access your computer's loopback service. The hosted cloud-brain deployment must include the `automation-plan` task added in this change; until that version is deployed, the local worker will reject incomplete or non-JSON plans rather than guess.

## Tests

```sh
python -m unittest discover -s tests -v
```

OpenDroid (`https://github.com/yashab-cyber/opendroid`) informed the contact-resolution and stepwise UI-verification ideas. It is an Android/Kotlin project; no OpenDroid source code is copied here.
