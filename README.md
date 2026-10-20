# Weronika AI

Weronika is a voice + text assistant with two halves that share one UI:

| Half            | Where              | What it does                                                                                     |
| --------------- | ------------------ | ------------------------------------------------------------------------------------------------ |
| **Web app**     | `src/` + `public/` | TanStack Start + React site. Streams the cloud brain, serves the orb UI.                         |
| **Local agent** | `weronika-py/`     | Python server on `127.0.0.1:8765` that can actually control your PC, run apps, and manage files. |

The same `weronika.html` powers both, so it works online **and** offline.

---

## Repository map

```
WERONIKA-AI/
├── src/                     ← TypeScript app (routes, components, lib)
│   ├── routes/              ← file-based pages + API endpoints
│   │   ├── index.tsx        ← "/" — embeds the Weronika UI full-screen
│   │   └── api/public/      ← brain, answer, image, song, video endpoints
│   ├── components/ui/       ← shadcn/ui building blocks
│   ├── lib/                 ← brain stream, relay, media-only guards
│   └── README.md            ← routing conventions for this folder
│
├── public/                  ← static files served at the site root
│   ├── weronika.html        ← THE UI (source of truth, ~1 MB single file)
│   ├── weronika-workspace.js
│   ├── weronika-commands.js
│   ├── weronika-local-prompts.js
│   ├── weronika-media-intent.js
│   ├── technical-models.js
│   ├── technical-viewer.js
│   ├── media/               ← photos & videos go here (see media/README.md)
│   ├── favicon.ico
│   └── robots.txt
│
├── weronika-py/             ← Python local agent (self-contained, see its README)
│   ├── weronika_agent.py
│   ├── weronika_brain.py        ← cloud brain client
│   ├── weronika_automation.py
│   ├── weronika_apps.py
│   ├── weronika_calls.py
│   ├── weronika_upgrade.py
│   ├── config.json
│   ├── requirements.txt
│   ├── start.bat                ← Windows one-click launcher
│   ├── weronika.html            ← standalone UI (portable copy)
│   ├── public/                  ← UI + JS modules the agent serves
│   └── tests/
│
├── tests/                   ← JavaScript/TypeScript checks (.mjs)
├── archive/                 ← zipped snapshots, not used at runtime
├── scripts/                 ← maintenance helpers
├── package.json             ← web app config + npm scripts
├── vite.config.ts
├── tsconfig.json
└── AGENTS.md
```

---

## Two ways to run Weronika

### 1. Web app (browser, cloud brain)

```bash
npm install
npm run dev          # http://localhost:3000
```

`npm run build` produces the production bundle.

### 2. Local agent (your PC, full control)

**Windows:** double-click `weronika-py/start.bat`.

**macOS / Linux:**

```bash
cd weronika-py
python -m pip install -r requirements.txt
python weronika_agent.py     # http://127.0.0.1:8765/
```

Full details: [`weronika-py/README.md`](weronika-py/README.md).

---

## Tests

```bash
npm run test         # everything
npm run test:js      # tests/*.mjs  (6 suites)
npm run test:py      # weronika-py/tests (25 tests)
```

No test hits the network — media routes are asserted to stay local.

---

## Editing the UI

`public/weronika.html` is the only place to edit. The copies inside
`weronika-py/` are generated from it:

```bash
npm run sync:standalone
```

Run that after any UI change so the local agent ships the same version.

---

## A note on branches

`arena/0f54208f-weronika-ai` and the other `arena/*` names are **git branches on
GitHub**, not folders. The folder you are reading (`WERONIKA-AI/`) is the
repository root for every branch. To see an older branch's files:

```bash
git checkout arena/0f54208f-weronika-ai
```

Everything that was in that branch has already been merged into `main`, so this
layout contains all of it — just organised.
