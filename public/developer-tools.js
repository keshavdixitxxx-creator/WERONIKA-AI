// Weronika Workspace: the code editor that opens over the orb.
//
// It looks and works like VS Code, in neon blue: a title bar with a command centre, an
// activity bar, an Explorer and a Search side bar, editor tabs over a syntax-coloured
// editor, an output panel, a live preview, a chat side bar, and a status bar.
//
// A statement typed in the chat side bar is handed to the orb (`onPrompt`). The orb shows
// it, passes it to the cloud brain together with the open files, and remembers it. The
// files the brain writes come back through `openDraftFiles` and open here as unsaved
// drafts. Nothing is written to disk or run until the user chooses SAVE or RUN.
import { HIGHLIGHT_LIMIT, highlightCode, languageForPath } from "./workspace-syntax.js";

const WORKSPACE_STYLE = `
  /* Weronika Workspace: a VS Code layout in neon blue. Title bar with macOS traffic
     lights and a command centre, activity bar, side bar, editor tabs over a coloured
     editor, an output panel, a chat side bar, and a status bar. */
  .devtools-panel { --neon:#35c5ff; --neon-hi:#7fe3ff; --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace; position:fixed; z-index:70; inset:2.4vh 1.6vw; display:flex; flex-direction:column; min-width:320px; color:#cfe9f8; background:#061020; border:1px solid #1d5f8f; border-radius:10px; box-shadow:0 28px 80px #000d,0 0 46px #00a6ff33,0 0 130px #0090ff1c,inset 0 0 0 1px #0b3a5a; font:12px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",ui-sans-serif,system-ui,sans-serif; letter-spacing:normal; text-align:left; -webkit-text-size-adjust:100%; text-size-adjust:100%; overflow:hidden; outline:none; }
  .devtools-panel[hidden] { display:none; }
  .devtools-panel [hidden] { display:none !important; }
  .devtools-panel *, .devtools-panel *::before, .devtools-panel *::after { box-sizing:border-box; }
  .devtools-panel :where(button, input, textarea) { margin:0; font:inherit; color:inherit; letter-spacing:inherit; }
  .devtools-panel :where(button) { cursor:pointer; }
  .devtools-panel svg { width:1em; height:1em; flex:0 0 auto; pointer-events:none; }
  .devtools-panel ::-webkit-scrollbar { width:10px; height:10px; }
  .devtools-panel ::-webkit-scrollbar-thumb { background:#1a5a8580; border-radius:6px; border:2px solid transparent; background-clip:content-box; }
  .devtools-panel ::-webkit-scrollbar-thumb:hover { background:#35c5ff99; background-clip:content-box; }
  .devtools-panel ::-webkit-scrollbar-corner { background:transparent; }
  .devtools-panel :focus-visible { outline:1px solid var(--neon); outline-offset:-1px; }
  .devtools-panel.zoomed { inset:0; border-radius:0; border-color:transparent; }
  .devtools-panel.minimised { bottom:auto; }
  .devtools-panel.minimised .devtools-body, .devtools-panel.minimised .workspace-statusbar { display:none; }
  /* The Workspace keeps its neon blue whatever the orb's theme colour is; it only
     follows the brightness setting. */
  html[data-weronika-dim] .devtools-panel { filter:brightness(var(--weronika-brightness,1)); }

  /* ---- title bar ---- */
  .devtools-top { position:relative; display:flex; align-items:center; gap:10px; flex:0 0 auto; height:36px; padding:0 8px 0 12px; background:linear-gradient(180deg,#0b2a44,#081d31); border-bottom:1px solid #12527a; user-select:none; -webkit-user-select:none; }
  .devtools-lights { display:flex; gap:7px; flex:0 0 auto; }
  .devtools-light { width:12px; height:12px; border-radius:50%; border:0; padding:0; }
  .devtools-light.close { background:#ff5f57; }
  .devtools-light.min { background:#febc2e; }
  .devtools-light.max { background:#28c840; }
  .devtools-light:hover { filter:brightness(1.25); }
  .devtools-menubar { display:flex; gap:1px; margin-left:6px; }
  .devtools-menu { border:0; border-radius:4px; padding:3px 8px; background:transparent; color:#a9cfe4; font-size:12px; }
  .devtools-menu:hover, .devtools-menu[aria-expanded="true"] { background:#11405f; color:#fff; }
  .devtools-command { position:absolute; left:50%; top:6px; transform:translateX(-50%); display:flex; align-items:center; justify-content:center; gap:7px; width:min(420px,38%); height:24px; padding:0 12px; border:1px solid #1b587f; border-radius:6px; background:#06182899; color:#8fc3de; font-size:11.5px; white-space:nowrap; overflow:hidden; }
  .devtools-command:hover { border-color:var(--neon); color:#e6f8ff; box-shadow:0 0 12px #35c5ff44; }
  .devtools-subtitle { overflow:hidden; text-overflow:ellipsis; letter-spacing:.03em; }
  .devtools-layout { display:flex; gap:2px; margin-left:auto; }
  .devtools-layout-btn { display:grid; place-items:center; width:26px; height:24px; border:0; border-radius:4px; padding:0; background:transparent; color:#527f9b; font-size:15px; }
  .devtools-layout-btn:hover { background:#11405f; color:#fff; }
  .devtools-layout-btn[aria-pressed="true"] { color:var(--neon-hi); }
  .devtools-close { border:0; border-radius:4px; padding:0; color:#a8d9f2; background:transparent; width:28px; height:24px; font-size:17px; line-height:1; }
  .devtools-close:hover { background:#c42b1c; color:#fff; }

  .devtools-body { flex:1; min-height:0; display:flex; }

  /* ---- activity bar ---- */
  .workspace-activity { display:flex; flex-direction:column; align-items:center; flex:0 0 46px; padding:4px 0; background:#050e1b; border-right:1px solid #0d3550; }
  .workspace-activity-btn { position:relative; display:grid; place-items:center; flex:0 0 auto; width:46px; height:44px; border:0; padding:0; background:transparent; color:#4f7f9c; font-size:22px; }
  .workspace-activity-btn:hover { color:#d7f3ff; }
  .workspace-activity-btn.active, .workspace-activity-btn[aria-pressed="true"] { color:var(--neon-hi); filter:drop-shadow(0 0 5px #35c5ffaa); }
  .workspace-activity-btn.active::before { content:""; position:absolute; left:0; top:8px; bottom:8px; width:2px; background:var(--neon); box-shadow:0 0 8px var(--neon); }
  .workspace-activity-btn:disabled { opacity:.5; cursor:wait; }
  .workspace-activity-badge { position:absolute; right:7px; bottom:7px; min-width:15px; height:15px; padding:0 4px; border-radius:8px; background:var(--neon); color:#03121f; font:700 9px/15px var(--mono); text-align:center; box-shadow:0 0 8px #35c5ffaa; }
  .workspace-activity-spacer { flex:1; }

  .workspace-main { position:relative; flex:1; min-width:0; min-height:0; display:flex; }

  /* ---- side bar ---- */
  .workspace-explorer { display:flex; flex-direction:column; flex:0 0 252px; min-width:0; min-height:0; background:#071625; border-right:1px solid #103f5e; }
  .devtools-panel.side-closed .workspace-explorer { display:none; }
  .workspace-view { display:flex; flex-direction:column; flex:1; min-height:0; }
  .workspace-pane-heading { display:flex; align-items:center; justify-content:space-between; flex:0 0 auto; height:30px; padding:0 12px 0 16px; color:#8fc3de; font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; }
  .workspace-section { display:flex; flex-direction:column; flex:0 0 auto; min-height:0; border-top:1px solid #0d3550; }
  .workspace-project { flex:1 1 0; }
  .workspace-section.collapsed { flex:0 0 auto; }
  .workspace-section.collapsed .workspace-section-body { display:none; }
  .workspace-section-head { display:flex; align-items:center; flex:0 0 auto; height:22px; padding-right:6px; }
  .workspace-section-toggle { display:flex; align-items:center; gap:4px; flex:1; min-width:0; height:22px; padding:0 4px; border:0; background:transparent; color:#cfe9f8; font-size:10.5px; font-weight:700; letter-spacing:.03em; text-align:left; text-transform:uppercase; }
  .devtools-chev { display:inline-block; flex:0 0 14px; width:14px; text-align:center; color:#6f9fba; font-size:10px; line-height:1; transition:transform .12s; }
  .workspace-section.collapsed .devtools-chev, .devtools-folder[aria-expanded="false"] .devtools-chev { transform:rotate(-90deg); }
  .workspace-project-title { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .workspace-count { flex:0 0 auto; padding:0 6px; border-radius:8px; background:#0e3a58; color:#a9dcf3; font-size:9.5px; font-weight:600; line-height:15px; }
  .workspace-section-actions { display:flex; flex:0 0 auto; gap:1px; }
  .devtools-icon-btn { display:grid; place-items:center; width:22px; height:20px; border:0; border-radius:4px; padding:0; background:transparent; color:#8fc3de; font-size:14px; line-height:1; }
  .devtools-icon-btn:hover { background:#11405f; color:#fff; }
  .devtools-icon-btn[aria-pressed="true"] { color:var(--neon-hi); background:#0e3a58; }
  .workspace-open-list { max-height:132px; overflow:auto; padding-bottom:3px; }
  .devtools-files { flex:1 1 0; min-height:0; overflow:auto; padding:1px 0 12px; }
  .devtools-file { position:relative; display:flex; align-items:center; gap:6px; width:100%; height:22px; border:0; padding:0 8px 0 0; color:#a5c7dc; background:transparent; font-size:12px; text-align:left; white-space:nowrap; cursor:pointer; }
  .devtools-file:hover { background:#0b2c45; color:#e2f6ff; }
  .devtools-file.active { background:#0e3a58; color:#fff; box-shadow:inset 1px 0 0 var(--neon),inset 0 0 0 1px #1d6a9a66; }
  .devtools-file-name { flex:1 1 auto; min-width:0; overflow:hidden; text-overflow:ellipsis; }
  .devtools-file.new .devtools-file-name { color:#7ff0b6; }
  .devtools-file.modified .devtools-file-name { color:#ffd590; }
  .devtools-folder { color:#cfe9f8; }
  .devtools-file-badge { flex:0 0 18px; width:18px; text-align:center; font:700 8.5px/1 var(--mono); letter-spacing:-.02em; }
  .devtools-file-state { flex:0 0 12px; width:12px; text-align:center; font:700 10px/1 var(--mono); }
  .devtools-file.new .devtools-file-state { color:#59e0a0; }
  .devtools-file.modified .devtools-file-state { color:#ffc46b; }
  .devtools-row-close { display:grid; place-items:center; flex:0 0 18px; width:18px; height:18px; border:0; border-radius:3px; padding:0; background:transparent; color:#a5c7dc; font-size:14px; line-height:1; visibility:hidden; }
  .devtools-file:hover .devtools-row-close, .devtools-row-close:focus-visible { visibility:visible; }
  .devtools-row-close:hover { background:#17557c; color:#fff; }
  .workspace-empty { padding:8px 16px; color:#5f8aa3; font-size:11px; line-height:1.5; white-space:normal; }
  .workspace-empty.error { color:#ff9c88; }
  .workspace-search-box { flex:0 0 auto; padding:2px 12px 8px; }
  .workspace-search-input, .devtools-quickopen input { display:block; width:100%; height:26px; padding:0 8px; border:1px solid #17425e; border-radius:3px; background:#040d18; color:#d8f3ff; font-size:12px; outline:none; }
  .workspace-search-input:focus, .devtools-quickopen input:focus { border-color:var(--neon); box-shadow:0 0 0 1px #35c5ff44,0 0 14px #35c5ff33; }
  .workspace-search-input::placeholder, .devtools-quickopen input::placeholder { color:#4f7892; }
  .workspace-search-summary { flex:0 0 auto; padding:0 12px 6px; color:#6f9fba; font-size:10.5px; line-height:1.5; }
  .workspace-search-results { flex:1 1 0; min-height:0; overflow:auto; padding-bottom:10px; }
  .workspace-search-file { display:flex; align-items:center; gap:6px; height:22px; padding:0 8px 0 10px; color:#cfe9f8; font-size:11.5px; font-weight:600; white-space:nowrap; }
  .workspace-search-file span:last-child { min-width:0; overflow:hidden; text-overflow:ellipsis; }
  .workspace-search-hit { display:block; width:100%; height:20px; padding:0 8px 0 34px; border:0; background:transparent; color:#93b9d0; font:11px/20px var(--mono); text-align:left; white-space:pre; overflow:hidden; text-overflow:ellipsis; }
  .workspace-search-hit:hover { background:#0b2c45; color:#fff; }
  .workspace-search-hit b { color:#fff; background:#1f7fc266; font-weight:400; }

  /* ---- editor group ---- */
  .workspace-editor-pane { position:relative; display:flex; flex-direction:column; flex:1 1 0; min-width:0; min-height:0; background:#050d19; }
  .devtools-tabs-row { display:flex; align-items:stretch; flex:0 0 auto; height:34px; background:#071625; border-bottom:1px solid #0f3c58; }
  .devtools-editor-tabs { position:relative; display:flex; flex:1 1 0; min-width:0; overflow-x:auto; overflow-y:hidden; scrollbar-width:none; }
  .devtools-editor-tabs::-webkit-scrollbar { display:none; }
  .devtools-file-tab { position:relative; display:flex; align-items:center; gap:6px; flex:0 0 auto; max-width:230px; padding:0 6px 0 10px; color:#84a9bf; background:#071625; border-right:1px solid #0f3c58; font-size:12px; cursor:pointer; }
  .devtools-file-tab:hover { color:#d7f3ff; }
  .devtools-file-tab.active { color:#fff; background:#050d19; }
  .devtools-file-tab.active::before { content:""; position:absolute; left:0; right:0; top:0; height:2px; background:var(--neon); box-shadow:0 0 10px var(--neon); }
  .devtools-file-tab.active::after { content:""; position:absolute; left:0; right:0; bottom:-1px; height:1px; background:#050d19; }
  .devtools-tab-name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; border:0; padding:0; background:transparent; font-size:12px; }
  .devtools-tab-name small { margin-left:6px; color:#5f8aa3; font-size:10.5px; }
  .devtools-file-tab.new .devtools-tab-name { color:#7ff0b6; }
  .devtools-file-tab.modified .devtools-tab-name { color:#ffd590; }
  .devtools-tab-close { display:grid; place-items:center; flex:0 0 18px; width:18px; height:18px; border:0; border-radius:4px; padding:0; background:transparent; color:transparent; font-size:14px; line-height:1; }
  .devtools-tab-close::before { content:"×"; }
  .devtools-file-tab:hover .devtools-tab-close, .devtools-file-tab.active .devtools-tab-close, .devtools-tab-close:focus-visible { color:#9cc4da; }
  .devtools-file-tab.dirty .devtools-tab-close { color:#e8f6ff; }
  .devtools-file-tab.dirty .devtools-tab-close::before { content:"●"; font-size:10px; }
  .devtools-file-tab.dirty .devtools-tab-close:hover::before { content:"×"; font-size:14px; }
  .devtools-tab-close:hover { background:#17557c; color:#fff; }
  .devtools-editor-actions { display:flex; align-items:center; gap:5px; flex:0 0 auto; padding:0 8px; border-left:1px solid #0f3c58; }
  .devtools-btn { border:1px solid #1e5478; color:#a9dcf3; background:#0a2236; border-radius:3px; padding:0 8px; height:22px; font-size:10.5px; letter-spacing:.04em; white-space:nowrap; }
  .devtools-btn:hover { background:#124466; border-color:#42bdff; color:#fff; box-shadow:0 0 10px #35c5ff44; }
  .devtools-btn:disabled { opacity:.5; cursor:default; box-shadow:none; }
  .devtools-btn.run-file { color:#9ff5c4; border-color:#1f7a58; }
  .devtools-btn.attention { color:#fff; border-color:var(--neon); background:#0b5c8a; box-shadow:0 0 12px #35c5ff66; }
  .devtools-btn[aria-pressed="true"] { color:#fff; border-color:var(--neon); background:#0e3a58; }
  .devtools-toolbar { display:flex; align-items:center; gap:6px; flex:0 0 auto; height:24px; padding:0 12px 0 14px; background:#050d19; color:#6f9fba; font-size:11.5px; white-space:nowrap; overflow:hidden; }
  .devtools-crumbs { display:flex; align-items:center; gap:6px; min-width:0; overflow:hidden; }
  .devtools-crumbs span:last-child { color:#cfe9f8; }
  .devtools-crumbs i { color:#3f6883; font-style:normal; }
  .devtools-crumb-note { margin-left:auto; flex:0 0 auto; padding:0 7px; border:1px solid #1f7a58; border-radius:9px; color:#7ff0b6; font-size:9.5px; letter-spacing:.06em; line-height:15px; }
  .devtools-crumb-note.modified { border-color:#8a6a2a; color:#ffd590; }
  .devtools-editor-column { position:relative; display:flex; flex:1 1 0; flex-direction:column; min-width:0; min-height:0; }
  .devtools-editor-wrap { display:flex; flex:1 1 0; min-width:0; min-height:0; background:#050d19; overflow:hidden; }
  .devtools-gutter { position:relative; flex:0 0 auto; min-width:48px; overflow:hidden; color:#35607c; text-align:right; user-select:none; -webkit-user-select:none; font:12.5px/19px var(--mono); }
  .devtools-gutter-inner { padding:8px 12px 8px 14px; white-space:pre; will-change:transform; }
  .devtools-gutter-current { position:absolute; right:0; left:0; top:8px; height:19px; padding-right:12px; color:#d7f3ff; background:#050d19; will-change:transform; }
  .devtools-code { position:relative; flex:1 1 0; min-width:0; min-height:0; overflow:hidden; }
  /* The coloured layer and the text area use exactly the same metrics, so every
     character sits under the caret that edits it. No bold or italic in here. */
  .devtools-highlight, .devtools-editor { margin:0; border:0; padding:8px 14px 8px 4px; font:12.5px/19px var(--mono); letter-spacing:0; font-variant-ligatures:none; font-kerning:none; tab-size:4; -moz-tab-size:4; white-space:pre; overflow-wrap:normal; word-break:normal; text-align:left; text-indent:0; text-transform:none; }
  .devtools-highlight { position:absolute; left:0; top:0; min-width:100%; color:#c2e4f5; background:transparent; pointer-events:none; will-change:transform; }
  .devtools-highlight code { font:inherit; }
  .devtools-editor { position:absolute; inset:0; display:block; width:100%; height:100%; resize:none; outline:0; border-radius:0; color:transparent; background:transparent; caret-color:#7fe3ff; overflow:auto; }
  /* The caret and the current-line bar show where the keyboard is; no frame around the code. */
  .devtools-panel .devtools-editor:focus-visible { outline:0; }
  .devtools-editor::selection { background:#1f7fc277; color:transparent; }
  .devtools-code.plain .devtools-highlight { display:none; }
  .devtools-code.plain .devtools-editor { color:#c2e4f5; }
  .devtools-code.plain .devtools-editor::selection { color:#fff; }
  .devtools-active-line { position:absolute; left:0; right:0; top:8px; height:19px; background:#0b2a4270; box-shadow:inset 0 1px 0 #12466a80,inset 0 -1px 0 #12466a80; pointer-events:none; will-change:transform; }
  .tk-c { color:#4d7b98; }
  .tk-k { color:#56b6ff; }
  .tk-s { color:#ffb48a; }
  .tk-n { color:#b9f18c; }
  .tk-f { color:#ffe38a; }
  .tk-t { color:#3fe0d0; }
  .tk-a { color:#8fd3ff; }
  .tk-b { color:#c39bff; }
  .tk-v { color:#ff9ad5; }
  .tk-o { color:#7fa9c4; }
  .tk-r { color:#ff7a90; }
  .tk-h { color:#56b6ff; text-shadow:0 0 8px #35c5ff66; }
  .tk-e { color:#ffffff; }
  .tk-i { color:#a5d8ff; }
  .devtools-welcome { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px; padding:20px; background:#050d19; color:#5f8aa3; text-align:center; overflow:auto; }
  .devtools-welcome-mark { font-size:30px; font-weight:200; letter-spacing:.34em; margin-right:-.34em; color:#1a5f8c; text-shadow:0 0 26px #35c5ff55; }
  .devtools-welcome-sub { margin-top:-10px; color:#3f6883; font-size:10.5px; letter-spacing:.3em; }
  .devtools-welcome-keys { display:grid; grid-template-columns:auto auto; gap:7px 14px; font-size:12px; text-align:right; }
  .devtools-welcome-keys kbd { justify-self:start; padding:1px 6px; border:1px solid #17425e; border-radius:4px; background:#071625; color:#a9dcf3; font:11px var(--mono); }
  .devtools-welcome-actions { display:flex; flex-wrap:wrap; justify-content:center; gap:8px; }

  /* ---- output panel ---- */
  .workspace-panel { display:flex; flex-direction:column; flex:0 0 34%; min-height:110px; border-top:1px solid #1d5f8f; background:#050d19; }
  .workspace-panel-head { display:flex; align-items:center; flex:0 0 auto; height:30px; padding:0 8px 0 14px; }
  .workspace-panel-tab { padding:6px 0 4px; border-bottom:1px solid var(--neon); color:#e6f8ff; font-size:10.5px; letter-spacing:.09em; }
  .workspace-panel-actions { display:flex; gap:2px; margin-left:auto; }
  .workspace-output { flex:1 1 0; min-height:0; margin:0; padding:4px 14px 10px; overflow:auto; color:#b7d5e6; font:12px/1.55 var(--mono); white-space:pre-wrap; overflow-wrap:anywhere; user-select:text; -webkit-user-select:text; }
  .workspace-output .error { color:#ff9c88; }
  .workspace-output .stamp { color:#3f6883; }

  /* ---- preview ---- */
  .workspace-preview-pane { display:none; flex-direction:column; flex:1 1 0; min-width:0; min-height:0; border-left:1px solid #103f5e; background:#05101b; }
  .devtools-panel.preview-open .workspace-preview-pane { display:flex; }
  .workspace-preview-head { display:flex; align-items:center; gap:8px; flex:0 0 auto; height:34px; padding:0 8px 0 12px; border-bottom:1px solid #0f3c58; background:#071625; color:#8fc9e6; font-size:10.5px; letter-spacing:.09em; white-space:nowrap; }
  .workspace-preview-head .preview-empty { color:#5f8aa3; letter-spacing:.02em; }
  .workspace-preview-head .preview-refresh { margin-left:auto; }
  .workspace-preview-frame { flex:1 1 0; min-height:0; width:100%; border:0; background:#fff; }

  /* ---- chat side bar ---- */
  .workspace-agent-pane { display:flex; flex-direction:column; flex:0 0 330px; min-width:0; min-height:0; background:#071625; border-left:1px solid #103f5e; }
  .devtools-panel.agent-closed .workspace-agent-pane { display:none; }
  .workspace-agent-head { display:flex; align-items:center; gap:8px; flex:0 0 auto; height:34px; padding:0 12px; border-bottom:1px solid #0f3c58; color:#d6f2ff; font-size:10.5px; font-weight:700; letter-spacing:.09em; }
  .workspace-agent-dot { width:7px; height:7px; border-radius:50%; background:#35d3ff; box-shadow:0 0 8px #35caff; }
  .workspace-agent-tag { margin-left:auto; color:#70a8c3; font-size:9.5px; font-weight:400; }
  .workspace-route { display:flex; align-items:center; justify-content:center; gap:5px; flex:0 0 auto; height:28px; border-bottom:1px solid #0d3550; background:#06121f; color:#3f6883; font-size:9px; font-weight:700; letter-spacing:.1em; white-space:nowrap; }
  .workspace-route span { padding:1px 7px; border:1px solid #12405c; border-radius:9px; line-height:14px; transition:color .2s,border-color .2s,box-shadow .2s; }
  .workspace-route span.lit { color:#e6f8ff; border-color:var(--neon); box-shadow:0 0 10px #35c5ff77,inset 0 0 8px #35c5ff33; }
  .workspace-route span.busy { animation:workspace-pulse 1s ease-in-out infinite; }
  .workspace-route i { font-style:normal; }
  .workspace-route i.lit { color:var(--neon-hi); }
  @keyframes workspace-pulse { 50% { box-shadow:0 0 18px #35c5ffcc,inset 0 0 10px #35c5ff66; } }
  .workspace-chat-messages { flex:1 1 0; min-height:0; overflow:auto; padding:10px; display:flex; flex-direction:column; gap:8px; user-select:text; -webkit-user-select:text; }
  .workspace-chat-message { flex:0 0 auto; padding:7px 9px; border-radius:6px; white-space:pre-wrap; overflow-wrap:anywhere; color:#b7d5e6; background:#0a2437; border:1px solid #123f5c; font-size:12px; line-height:1.5; }
  .workspace-chat-message.user { color:#e8f9ff; background:#0b3450; box-shadow:inset 2px 0 0 #34c5ff; }
  .workspace-chat-message.assistant { box-shadow:inset 2px 0 0 #2b9cd8; }
  .workspace-chat-message.system { color:#6b95ad; background:transparent; border:0; padding:1px 3px; font-size:10.5px; }
  .workspace-chat-message.earlier { opacity:.76; }
  .workspace-chat-welcome { color:#7ba4bb; padding:2px 3px; font-size:11.5px; line-height:1.6; }
  .devtools-status { flex:0 0 auto; padding:3px 10px; color:#6ba0bd; background:#071827; font-size:10px; line-height:1.45; }
  .devtools-status.error { color:#ff9c88; }
  .workspace-chat-composer { flex:0 0 auto; padding:8px; border-top:1px solid #0f3c58; background:#071827; }
  .workspace-prompt { display:block; width:100%; min-height:62px; max-height:150px; resize:vertical; padding:7px 8px; border:1px solid #17425e; border-radius:5px; color:#d8f3ff; background:#05101b; font-size:12px; line-height:1.45; outline:none; }
  .workspace-prompt:focus { border-color:#35c5ff; box-shadow:0 0 0 1px #149bd655,0 0 16px #35c5ff33; }
  .workspace-prompt::placeholder { color:#4f7892; }
  .workspace-composer-footer { display:flex; align-items:center; justify-content:space-between; gap:8px; padding-top:6px; }
  .workspace-chat-hint { color:#5f869c; font-size:10px; }
  .workspace-build { color:#f2fcff; border-color:#2f9fd4; background:#086b99; }
  .workspace-build:hover { background:#0b86bd; }
  .workspace-build:disabled { opacity:.55; cursor:wait; }

  /* ---- status bar ---- */
  .workspace-statusbar { display:flex; align-items:stretch; flex:0 0 auto; height:22px; color:#f2fbff; background:linear-gradient(180deg,#0b86cf,#0a6aab); border-top:1px solid #35c5ff; box-shadow:0 -1px 14px #35c5ff55; font-size:11px; line-height:21px; white-space:nowrap; }
  .workspace-status-item { display:flex; align-items:center; gap:5px; flex:0 0 auto; padding:0 8px; border:0; background:transparent; color:inherit; font-size:11px; }
  button.workspace-status-item:hover { background:#ffffff26; }
  .devtools-connection { background:#35c5ff; color:#03121f; font-weight:700; letter-spacing:.04em; }
  button.devtools-connection:hover { background:#7fe3ff; }
  .devtools-drafts { background:#ffffff1f; font-weight:600; }
  .workspace-statusbar .workspace-status { flex:1 1 0; min-width:0; display:block; padding:0 10px; background:transparent; color:#e4f6ff; font-size:11px; line-height:21px; overflow:hidden; text-overflow:ellipsis; }
  .workspace-statusbar .workspace-status.error { color:#fff; background:#b3261e; }
  .devtools-stage.live { background:#ffffff26; }

  /* ---- quick open and menus ---- */
  .devtools-quickopen { position:absolute; z-index:6; left:50%; top:40px; transform:translateX(-50%); width:min(560px,82%); padding:8px; border:1px solid var(--neon); border-radius:8px; background:#071625; box-shadow:0 18px 50px #000c,0 0 28px #35c5ff44; }
  .devtools-quickopen-list { position:relative; max-height:300px; margin-top:6px; overflow:auto; }
  .devtools-quickopen-list .workspace-empty { padding:4px 8px; }
  .devtools-quickopen-item { display:flex; align-items:center; gap:8px; width:100%; height:24px; padding:0 8px; border:0; border-radius:4px; background:transparent; color:#b7d5e6; font-size:12px; text-align:left; white-space:nowrap; }
  .devtools-quickopen-item.selected, .devtools-quickopen-item:hover { background:#0e3a58; color:#fff; }
  .devtools-quickopen-item small { margin-left:auto; min-width:0; color:#5f8aa3; font-size:10.5px; overflow:hidden; text-overflow:ellipsis; }
  .devtools-menu-popup { position:absolute; z-index:6; top:34px; min-width:230px; padding:4px; border:1px solid #1d5f8f; border-radius:6px; background:#071625; box-shadow:0 14px 40px #000c,0 0 20px #35c5ff33; }
  .devtools-menu-item { display:flex; align-items:center; gap:18px; width:100%; height:24px; padding:0 10px; border:0; border-radius:4px; background:transparent; color:#cfe9f8; font-size:12px; text-align:left; white-space:nowrap; }
  .devtools-menu-item:hover, .devtools-menu-item:focus-visible { background:#0e4a73; color:#fff; outline:none; }
  .devtools-menu-item small { margin-left:auto; color:#6f9fba; font-size:11px; }
  .devtools-menu-item:disabled { opacity:.45; cursor:default; background:transparent; }
  .devtools-menu-rule { height:1px; margin:4px 6px; background:#12405c; }

  @media(max-width:1180px) { .workspace-explorer { flex-basis:214px; } .workspace-agent-pane { flex-basis:290px; } .devtools-command { width:min(300px,28%); } }
  @media(max-width:980px) { .devtools-menubar { display:none; } }
  @media(max-width:820px) {
    .devtools-panel { inset:1vh 1vw; }
    .workspace-main { flex-direction:column; }
    .workspace-explorer { position:absolute; z-index:4; left:0; top:0; bottom:0; width:min(260px,82%); box-shadow:12px 0 30px #000b; }
    .workspace-agent-pane { flex:0 0 42%; border-left:0; border-top:1px solid #1d5f8f; }
    .workspace-preview-pane { position:absolute; inset:0; z-index:3; border-left:0; }
    .devtools-command { position:static; transform:none; flex:1 1 0; min-width:0; width:auto; }
    .devtools-layout { margin-left:0; }
    .workspace-route, .workspace-statusbar .optional, .devtools-crumb-note { display:none; }
  }
  @media(max-width:520px) {
    .workspace-activity { flex-basis:38px; }
    .workspace-activity-btn { width:38px; height:38px; font-size:19px; }
    .devtools-toolbar { display:none; }
    .devtools-editor-actions { padding:0 5px; gap:4px; }
    .devtools-editor-actions .preview-toggle, .workspace-statusbar .optional-small, .workspace-statusbar .devtools-line-count { display:none; }
    /* On a phone the message gets a row of its own above the status items. */
    .workspace-statusbar { flex-wrap:wrap; height:auto; }
    .workspace-statusbar .workspace-status { order:-1; flex:1 0 100%; border-bottom:1px solid #ffffff2b; }
    .workspace-statusbar .workspace-status-item { height:21px; }
    .workspace-statusbar .devtools-language { margin-left:auto; }
  }
  @media(prefers-reduced-motion:reduce) { .devtools-panel * { transition:none !important; animation:none !important; } }
`;

export function createStoredZip(files) {
  const text = new TextEncoder();
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let value = n;
    for (let bit = 0; bit < 8; bit += 1)
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    table[n] = value >>> 0;
  }
  const crc32 = (bytes) => {
    let crc = 0xffffffff;
    for (const byte of bytes) crc = table[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  };
  const localParts = [];
  const centralParts = [];
  let localOffset = 0;
  let totalSize = 0;
  if (!Array.isArray(files) || files.length > 1000)
    throw new Error("The workspace ZIP contains too many files.");
  for (const file of files) {
    if (!file || typeof file.path !== "string" || typeof file.content !== "string") continue;
    const zipPath = file.path.replaceAll("\\", "/");
    if (
      zipPath.startsWith("/") ||
      zipPath.split("/").some((part) => !part || part === "." || part === "..")
    ) {
      throw new Error("A workspace file has an unsafe path and cannot be added to the ZIP.");
    }
    const name = text.encode(zipPath);
    const data = text.encode(file.content);
    totalSize += data.length;
    if (totalSize > 50 * 1024 * 1024) throw new Error("The workspace ZIP is larger than 50 MB.");
    const crc = crc32(data);
    const local = new Uint8Array(30 + name.length);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034b50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0x0800, true);
    localView.setUint16(8, 0, true);
    localView.setUint16(10, 0, true);
    localView.setUint16(12, 0x21, true);
    localView.setUint32(14, crc, true);
    localView.setUint32(18, data.length, true);
    localView.setUint32(22, data.length, true);
    localView.setUint16(26, name.length, true);
    localView.setUint16(28, 0, true);
    local.set(name, 30);
    localParts.push(local, data);

    const central = new Uint8Array(46 + name.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014b50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0x0800, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint16(12, 0, true);
    centralView.setUint16(14, 0x21, true);
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, data.length, true);
    centralView.setUint32(24, data.length, true);
    centralView.setUint16(28, name.length, true);
    centralView.setUint16(30, 0, true);
    centralView.setUint16(32, 0, true);
    centralView.setUint16(34, 0, true);
    centralView.setUint16(36, 0, true);
    centralView.setUint32(38, 0, true);
    centralView.setUint32(42, localOffset, true);
    central.set(name, 46);
    centralParts.push(central);
    localOffset += local.length + data.length;
  }
  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, centralParts.length, true);
  endView.setUint16(10, centralParts.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, localOffset, true);
  endView.setUint16(20, 0, true);
  return new Blob([...localParts, ...centralParts, end], { type: "application/zip" });
}

const icon = (body) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
const ICONS = {
  files: icon(
    '<path d="M14.5 3H7.5A1.5 1.5 0 0 0 6 4.5V17"/><path d="M10.5 7h6l3.5 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 9 19.5v-11A1.5 1.5 0 0 1 10.5 7z"/><path d="M16.5 7v3.5H20"/>',
  ),
  search: icon('<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/>'),
  preview: icon(
    '<rect x="3" y="4.5" width="18" height="15" rx="1.8"/><path d="M3 8.5h18"/><path d="M10 11.5l5 2.75-5 2.75z"/>',
  ),
  chat: icon(
    '<path d="M4.5 5h15A1.5 1.5 0 0 1 21 6.5v9a1.5 1.5 0 0 1-1.5 1.5H11l-4.5 3.5V17h-2A1.5 1.5 0 0 1 3 15.5v-9A1.5 1.5 0 0 1 4.5 5z"/><path d="M8 9.5h8M8 12.5h5"/>',
  ),
  download: icon('<path d="M12 4v11"/><path d="M7.5 11L12 15.5 16.5 11"/><path d="M4.5 19.5h15"/>'),
  newFile: icon(
    '<path d="M13 3.5H7A1.5 1.5 0 0 0 5.5 5v14A1.5 1.5 0 0 0 7 20.5h5"/><path d="M13 3.5l5.5 5.5V12"/><path d="M13 3.5V9h5.5"/><path d="M18 15v6M15 18h6"/>',
  ),
  refresh: icon('<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4v4.5H15"/>'),
  collapse: icon(
    '<rect x="4" y="8" width="12" height="12" rx="1.5"/><path d="M8 4.5h10.5A1.5 1.5 0 0 1 20 6v10.5"/><path d="M7.5 14h5"/>',
  ),
  sideLeft: icon('<rect x="3" y="4.5" width="18" height="15" rx="1.8"/><path d="M9 4.5v15"/>'),
  panelBottom: icon('<rect x="3" y="4.5" width="18" height="15" rx="1.8"/><path d="M3 14h18"/>'),
  sideRight: icon('<rect x="3" y="4.5" width="18" height="15" rx="1.8"/><path d="M15 4.5v15"/>'),
  clear: icon('<path d="M4 6.5h10M4 11.5h8M4 16.5h6"/><path d="M15.5 13.5l5 5M20.5 13.5l-5 5"/>'),
};

// A two-letter badge per file type, in the colour that type usually has.
const FILE_BADGES = new Map(
  [
    ["JS", "#f4df62", "js mjs cjs"],
    ["JX", "#61dafb", "jsx"],
    ["TS", "#4aa8ff", "ts"],
    ["TX", "#4aa8ff", "tsx"],
    ["PY", "#6cc4ff", "py"],
    ["<>", "#ff9a5c", "html xml"],
    ["V", "#59e0a0", "vue"],
    ["S", "#ff8f6b", "svelte"],
    ["#", "#58b6ff", "css scss"],
    ["{}", "#f4df62", "json"],
    ["MD", "#8fd3ff", "md"],
    ["YM", "#c39bff", "yaml yml"],
    ["TM", "#9fb6c6", "toml"],
    ["JV", "#ff8f6b", "java"],
    ["KT", "#c39bff", "kt kts"],
    ["C#", "#7ef0c8", "cs"],
    ["C", "#6cc4ff", "c h"],
    ["C+", "#6cc4ff", "cpp hpp"],
    ["GO", "#5fe0e6", "go"],
    ["RS", "#ffb38a", "rs"],
    ["RB", "#ff7a8a", "rb"],
    ["PH", "#a9a2ff", "php"],
    ["SQ", "#ffc46b", "sql"],
    ["$", "#7ef0c8", "sh bash ps1 bat"],
    ["SW", "#ff9a5c", "swift"],
    ["DT", "#5fe0e6", "dart"],
    ["LU", "#8f9bff", "lua"],
    ["R", "#6cc4ff", "r"],
    ["SC", "#ff7a8a", "scala"],
    ["GQ", "#ff9ad5", "graphql"],
    ["PB", "#9fb6c6", "proto"],
    ["EX", "#c39bff", "ex exs"],
    ["PL", "#8fd3ff", "pl"],
  ].flatMap(([label, colour, extensions]) =>
    extensions.split(" ").map((extension) => [extension, [label, colour]]),
  ),
);

// Files that look like credentials are never sent to the brain as context.
const SECRET_PATH =
  /(?:^|\/)(?:\.env(?:\.[^/]*)?|secrets?(?:\.[^/]*)?|credentials?(?:\.[^/]*)?)(?:\/|$)/i;
// Colouring a very large file on every keystroke would lag; it is edited as plain text.
const LIVE_HIGHLIGHT_LIMIT = Math.min(HIGHLIGHT_LIMIT, 80_000);
const LINE_HEIGHT = 19; // px, the editor line height in the style sheet
// Unsaved drafts are kept in this browser, so they survive a restart like the chat does.
const SESSION_KEY = "weronika.workspace.session.v1";
const SESSION_CHAR_LIMIT = 1_200_000;
const STAGES = ["statement", "orb", "brain", "workspace"];

const baseName = (path) => path.slice(path.lastIndexOf("/") + 1);
const dirName = (path) => (path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "");
const isUnsaved = (state) => !state.existing || state.content !== state.savedContent;
const countLines = (text) => {
  let lines = 1;
  for (let at = text.indexOf("\n"); at !== -1; at = text.indexOf("\n", at + 1)) lines += 1;
  return lines;
};
const isSubsequence = (needle, haystack) => {
  let at = 0;
  for (const character of needle) {
    at = haystack.indexOf(character, at);
    if (at < 0) return false;
    at += 1;
  }
  return true;
};

export function mountDeveloperTools({ onPrompt = null } = {}) {
  document.querySelectorAll(".devtools-launch").forEach((button) => button.remove());
  const style = document.createElement("style");
  style.textContent = WORKSPACE_STYLE;
  document.head.append(style);
  const launch = document.getElementById("workspaceOpenBtn");
  const mac = /Mac|iPhone|iPad/i.test(navigator.platform || "");
  const keyLabel = (key, shift = false) =>
    mac ? `${shift ? "⇧" : ""}⌘${key}` : `Ctrl+${shift ? "Shift+" : ""}${key}`;
  const matches = (query) => Boolean(window.matchMedia && window.matchMedia(query).matches);
  const finePointer = () => !window.matchMedia || matches("(pointer: fine)");
  const narrow = () => matches("(max-width: 820px)");

  const panel = document.createElement("section");
  panel.className = "devtools-panel";
  panel.hidden = true;
  panel.tabIndex = -1;
  panel.setAttribute("aria-label", "Weronika Workspace");
  panel.innerHTML = `
    <header class="devtools-top">
      <span class="devtools-lights"><button class="devtools-light close" type="button" aria-label="Close Workspace" title="Close"></button><button class="devtools-light min" type="button" aria-label="Minimise Workspace" title="Minimise"></button><button class="devtools-light max" type="button" aria-label="Zoom Workspace" title="Zoom"></button></span>
      <nav class="devtools-menubar" aria-label="Workspace menu"><button class="devtools-menu" type="button" data-menu="file" aria-haspopup="menu" aria-expanded="false">File</button><button class="devtools-menu" type="button" data-menu="edit" aria-haspopup="menu" aria-expanded="false">Edit</button><button class="devtools-menu" type="button" data-menu="view" aria-haspopup="menu" aria-expanded="false">View</button><button class="devtools-menu" type="button" data-menu="run" aria-haspopup="menu" aria-expanded="false">Run</button></nav>
      <button class="devtools-command" type="button" title="Go to file (${keyLabel("P")})">${ICONS.search}<span class="devtools-subtitle">weronika-workspace — WERONIKA AI</span></button>
      <span class="devtools-layout"><button class="devtools-layout-btn toggle-side" type="button" aria-pressed="true" aria-label="Toggle side bar" title="Toggle side bar (${keyLabel("B")})">${ICONS.sideLeft}</button><button class="devtools-layout-btn toggle-panel" type="button" aria-pressed="false" aria-label="Toggle output panel" title="Toggle output panel (${keyLabel("J")})">${ICONS.panelBottom}</button><button class="devtools-layout-btn toggle-agent" type="button" aria-pressed="true" aria-label="Toggle Weronika chat" title="Toggle Weronika chat">${ICONS.sideRight}</button></span>
      <button class="devtools-close" type="button" aria-label="Close Workspace">×</button>
    </header>
    <div class="devtools-body">
      <nav class="workspace-activity" aria-label="Workspace views">
        <button class="workspace-activity-btn active" type="button" data-view="explorer" aria-label="Explorer" title="Explorer (${keyLabel("E", true)})">${ICONS.files}<span class="workspace-activity-badge" hidden></span></button>
        <button class="workspace-activity-btn" type="button" data-view="search" aria-label="Search" title="Search (${keyLabel("F", true)})">${ICONS.search}</button>
        <button class="workspace-activity-btn preview-toggle" type="button" aria-pressed="false" aria-label="Live preview" title="Show the live preview">${ICONS.preview}</button>
        <button class="workspace-activity-btn toggle-agent" type="button" aria-pressed="true" aria-label="Weronika chat" title="Toggle Weronika chat">${ICONS.chat}</button>
        <span class="workspace-activity-spacer"></span>
        <button class="workspace-activity-btn download-zip" type="button" aria-label="Download project as ZIP" title="Download project as ZIP">${ICONS.download}</button>
      </nav>
      <div class="workspace-main">
        <aside class="workspace-explorer" aria-label="Project Explorer">
          <div class="workspace-view" data-view="explorer">
            <div class="workspace-pane-heading"><span>EXPLORER</span></div>
            <div class="workspace-section workspace-open-editors">
              <div class="workspace-section-head"><button class="workspace-section-toggle" type="button" aria-expanded="true"><span class="devtools-chev">⌄</span><span class="workspace-project-title">OPEN EDITORS</span></button><span class="workspace-count open-count">0</span></div>
              <div class="workspace-section-body workspace-open-list"></div>
            </div>
            <div class="workspace-section workspace-project">
              <div class="workspace-section-head"><button class="workspace-section-toggle" type="button" aria-expanded="true"><span class="devtools-chev">⌄</span><span class="workspace-project-title">weronika-workspace</span></button><span class="workspace-section-actions"><button class="devtools-icon-btn new-file" type="button" aria-label="New file" title="New file…">${ICONS.newFile}</button><button class="devtools-icon-btn refresh-files" type="button" aria-label="Refresh workspace files" title="Refresh workspace files">${ICONS.refresh}</button><button class="devtools-icon-btn collapse-folders" type="button" aria-label="Collapse folders" title="Collapse folders">${ICONS.collapse}</button></span></div>
              <div class="workspace-section-body devtools-files" aria-label="Workspace files"></div>
            </div>
          </div>
          <div class="workspace-view" data-view="search" hidden>
            <div class="workspace-pane-heading"><span>SEARCH</span></div>
            <div class="workspace-search-box"><input class="workspace-search-input" type="search" aria-label="Search in files" placeholder="Search in files" autocomplete="off" spellcheck="false"></div>
            <div class="workspace-search-summary">Type at least two characters to search the workspace.</div>
            <div class="workspace-search-results"></div>
          </div>
        </aside>
        <section class="workspace-editor-pane" aria-label="Code editor">
          <div class="devtools-tabs-row">
            <div class="devtools-editor-tabs" role="tablist" aria-label="Open files"></div>
            <div class="devtools-editor-actions"><button class="devtools-btn save-all" type="button" title="Save every unsaved file (${keyLabel("S", true)})" hidden>SAVE ALL</button><button class="devtools-btn save-file" type="button" title="Save this file (${keyLabel("S")})">SAVE</button><button class="devtools-btn run-file" type="button" hidden>RUN PYTHON</button><button class="devtools-btn preview-toggle" type="button" aria-pressed="false" title="Show the live preview">PREVIEW</button></div>
          </div>
          <div class="devtools-toolbar"><span class="devtools-crumbs"></span><span class="devtools-crumb-note" hidden></span></div>
          <div class="devtools-editor-column">
            <div class="devtools-editor-wrap">
              <div class="devtools-gutter" aria-hidden="true"><div class="devtools-gutter-inner">1</div><div class="devtools-gutter-current">1</div></div>
              <div class="devtools-code"><div class="devtools-active-line"></div><pre class="devtools-highlight" aria-hidden="true"><code></code></pre><textarea class="devtools-editor" spellcheck="false" wrap="off" autocomplete="off" autocapitalize="off" autocorrect="off" aria-label="Code editor"></textarea></div>
            </div>
            <div class="devtools-welcome">
              <div class="devtools-welcome-mark">WERONIKA</div>
              <div class="devtools-welcome-sub">WORKSPACE</div>
              <div class="devtools-welcome-keys"><span>Go to file</span><kbd>${keyLabel("P")}</kbd><span>Save</span><kbd>${keyLabel("S")}</kbd><span>Save all</span><kbd>${keyLabel("S", true)}</kbd><span>Toggle side bar</span><kbd>${keyLabel("B")}</kbd><span>Toggle output</span><kbd>${keyLabel("J")}</kbd></div>
              <div class="devtools-welcome-actions"><button class="devtools-btn welcome-new" type="button">NEW FILE…</button><button class="devtools-btn welcome-ask" type="button">ASK WERONIKA</button></div>
            </div>
          </div>
          <section class="workspace-panel" aria-label="Output" hidden>
            <div class="workspace-panel-head"><span class="workspace-panel-tab">OUTPUT</span><span class="workspace-panel-actions"><button class="devtools-icon-btn clear-output" type="button" aria-label="Clear output" title="Clear output">${ICONS.clear}</button><button class="devtools-icon-btn close-panel" type="button" aria-label="Close output panel" title="Close output panel">×</button></span></div>
            <div class="workspace-output" role="log"></div>
          </section>
        </section>
        <section class="workspace-preview-pane" aria-label="Live preview">
          <div class="workspace-preview-head"><span>PREVIEW</span><button class="devtools-icon-btn preview-refresh" type="button" aria-label="Reload preview" title="Reload preview">${ICONS.refresh}</button><button class="devtools-icon-btn preview-close" type="button" aria-label="Close preview" title="Close preview">×</button></div>
          <iframe class="workspace-preview-frame" title="Project preview" sandbox="allow-scripts allow-forms allow-modals"></iframe>
        </section>
        <aside class="workspace-agent-pane" aria-label="Chat with Weronika">
          <header class="workspace-agent-head"><span class="workspace-agent-dot"></span><span>WERONIKA</span><span class="workspace-agent-tag">AGENT</span></header>
          <div class="workspace-route" title="A statement goes from the Workspace to the orb, the orb asks the brain, and the files come back to the editor"><span>WORKSPACE</span><i>›</i><span>ORB</span><i>›</i><span>BRAIN</span><i>›</i><span>EDITOR</span></div>
          <div class="workspace-chat-messages" role="log" aria-live="polite"></div>
          <div class="devtools-status workspace-build-status" role="status">Ready · statements go through the orb to Weronika’s cloud brain. Open-file context is included; review files before sending.</div>
          <div class="workspace-chat-composer"><textarea class="workspace-prompt" rows="3" maxlength="5000" aria-label="Message Weronika about this project" placeholder="Ask Weronika to build or edit this project…"></textarea><div class="workspace-composer-footer"><span class="workspace-chat-hint">Enter to send · Shift+Enter for a new line</span><button class="devtools-btn workspace-build" type="button">↑ Send</button></div></div>
        </aside>
      </div>
    </div>
    <footer class="workspace-statusbar">
      <button class="workspace-status-item devtools-connection" type="button" title="Refresh workspace files">● LOCAL WORKSPACE</button>
      <button class="workspace-status-item devtools-drafts" type="button" title="Save every unsaved file" hidden></button>
      <span class="devtools-status workspace-status" role="status">Connecting to local workspace…</span>
      <span class="workspace-status-item devtools-stage optional">Weronika: ready</span>
      <span class="workspace-status-item devtools-line-count">Ln 1, Col 1</span>
      <span class="workspace-status-item devtools-indent optional">Spaces: 2</span>
      <span class="workspace-status-item optional">UTF-8</span>
      <span class="workspace-status-item devtools-language">No file</span>
    </footer>
    <div class="devtools-quickopen" hidden><input type="text" aria-label="Go to file" autocomplete="off" spellcheck="false"><div class="devtools-quickopen-list"></div></div>`;
  // The Workspace is mounted beside <body>, not inside it: the orb page puts its theme
  // colour on <body> as a filter, and the Workspace keeps its own neon blue.
  document.documentElement.append(panel);

  const $ = (selector) => panel.querySelector(selector);
  const $$ = (selector) => [...panel.querySelectorAll(selector)];
  const el = (tag, className = "", text = "") => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const makeButton = (className, text = "") => {
    const node = el("button", className, text);
    node.type = "button";
    return node;
  };
  // Rows that hold their own close button cannot be <button>s; make them act like one.
  const onActivate = (node, action) => {
    node.addEventListener("click", action);
    node.addEventListener("keydown", (event) => {
      if (event.target !== node || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      action();
    });
  };

  const editor = $(".devtools-editor");
  const codeBox = $(".devtools-code");
  const highlightBox = $(".devtools-highlight");
  const highlightLayer = $(".devtools-highlight code");
  const gutterInner = $(".devtools-gutter-inner");
  const gutterCurrent = $(".devtools-gutter-current");
  const activeLine = $(".devtools-active-line");
  const welcome = $(".devtools-welcome");
  const crumbs = $(".devtools-crumbs");
  const crumbNote = $(".devtools-crumb-note");
  const fileList = $(".devtools-files");
  const openList = $(".workspace-open-list");
  const editorTabs = $(".devtools-editor-tabs");
  const codeStatus = $(".workspace-status");
  const buildStatus = $(".workspace-build-status");
  const chatMessages = $(".workspace-chat-messages");
  const promptInput = $(".workspace-prompt");
  const buildButton = $(".workspace-build");
  const outputLog = $(".workspace-output");
  const outputPanel = $(".workspace-panel");
  const searchInput = $(".workspace-search-input");
  const searchSummary = $(".workspace-search-summary");
  const searchResults = $(".workspace-search-results");
  const quick = $(".devtools-quickopen");
  const quickInput = $(".devtools-quickopen input");
  const quickList = $(".devtools-quickopen-list");
  const routeSteps = $$(".workspace-route span");
  const routeArrows = $$(".workspace-route i");
  const stageItem = $(".devtools-stage");

  // path → { content, savedContent, existing, origin?, view? }. `existing` is true once
  // the file is known to be stored; `savedContent` is what is stored.
  const openFiles = new Map();
  let activePath = "";
  let language = languageForPath("");
  let workspaceRoot = "";
  let browserStorageMode = false;
  let previewFiles = [];
  let previewUrl = "";
  let listedFiles = []; // { path, size } for every stored file
  let listedFolders = []; // folder paths, so that empty folders are shown too
  let knownPaths = new Set();
  const collapsedFolders = new Set();
  let gutterLines = 0;
  let highlightFrame = 0;
  let sessionTimer = 0;
  let searchCache = null;
  let searchTimer = 0;
  let searchToken = 0;
  let quickState = null;
  let menuPopup = null;
  let promptBusy = false;
  let stage = "idle";
  let stageTimer = 0;
  let restoredDrafts = 0;
  const browserWorkspaceKey = "weronika.workspace.files.v1";
  const supportedFilePath =
    /^(?!\/)(?!.*(?:^|\/)(?:\.|\.\.|__proto__|constructor|prototype)(?:\/|$))[^\\\u0000-\u001f]{1,200}\.(?:py|js|mjs|cjs|jsx|ts|tsx|vue|svelte|html|css|scss|json|md|txt|toml|yaml|yml|java|kt|kts|cs|c|h|cpp|hpp|go|rs|rb|php|sql|sh|bash|swift|dart|lua|r|scala|xml|graphql|proto|ex|exs|pl|ps1|bat)$/i;
  const PATH_HELP =
    "Use a relative path with a supported code or text extension, for example src/main.py.";

  function readBrowserWorkspace() {
    const files = Object.create(null);
    try {
      const stored = JSON.parse(localStorage.getItem(browserWorkspaceKey) || "{}");
      if (stored && typeof stored === "object" && !Array.isArray(stored)) {
        for (const [path, content] of Object.entries(stored)) {
          if (supportedFilePath.test(path) && typeof content === "string") files[path] = content;
        }
      }
    } catch {}
    return files;
  }

  // ---- messages -------------------------------------------------------------
  function appendWorkspaceMessage(role, message) {
    const bubble = document.createElement("div");
    bubble.className = `workspace-chat-message ${role}`;
    bubble.textContent = String(message || "");
    chatMessages.append(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
  }

  function showChatWelcome() {
    chatMessages.replaceChildren(
      el(
        "div",
        "workspace-chat-welcome",
        "Describe what you want to build, change, or debug. Your statement goes to the orb, the orb passes it to Weronika’s cloud brain with the open files, and the files she writes open here as editable drafts. Nothing is saved or run until you choose it.",
      ),
    );
  }

  // Show the Workspace part of the remembered conversation, for example after a
  // restart. An empty list clears the pane.
  function showConversation(turns) {
    const earlier = (Array.isArray(turns) ? turns : []).filter(
      (turn) =>
        turn &&
        turn.src === "workspace" &&
        turn.kind !== "private" &&
        typeof turn.content === "string" &&
        turn.content,
    );
    if (!earlier.length) {
      showChatWelcome();
      return;
    }
    chatMessages.replaceChildren();
    for (const turn of earlier.slice(-80)) {
      appendWorkspaceMessage(turn.role === "user" ? "user" : "assistant", turn.content).classList.add(
        "earlier",
      );
    }
    appendWorkspaceMessage("system", "Remembered from earlier · Weronika still knows this.");
  }

  function status(element, message, error = false) {
    element.textContent = message;
    element.title = message;
    element.classList.toggle("error", error);
  }

  function logOutput(message, error = false) {
    const line = el("div", error ? "error" : "");
    line.append(
      el("span", "stamp", `[${new Date().toLocaleTimeString([], { hour12: false })}] `),
      String(message),
    );
    outputLog.append(line);
    while (outputLog.childElementCount > 300) outputLog.firstElementChild.remove();
    outputLog.scrollTop = outputLog.scrollHeight;
  }

  // A problem is shown in the status bar and kept in the output panel.
  function fail(message) {
    status(codeStatus, message, true);
    logOutput(message, true);
  }

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(path, { cache: "no-store", ...options });
    } catch {
      const error = new Error(
        "Local worker is offline; using this browser’s private workspace storage.",
      );
      error.localApiUnavailable = true;
      throw error;
    }
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("application/json")) {
      const error = new Error(
        "Local worker API is unavailable; using this browser’s private workspace storage.",
      );
      error.localApiUnavailable = true;
      throw error;
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(
        response.status === 404
          ? "Local worker API is unavailable; using this browser’s private workspace storage."
          : result.error || "The local workspace rejected that request.",
      );
      error.localApiUnavailable = response.status === 404;
      throw error;
    }
    return result;
  }
  const post = (path, payload) =>
    request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

  // The open files Weronika may read: the file in front first, then the other tabs.
  function getWorkspaceContext() {
    const files = [];
    let total = 0;
    const ordered = [...openFiles].sort(([a], [b]) =>
      a === activePath ? -1 : b === activePath ? 1 : 0,
    );
    for (const [path, state] of ordered) {
      if (SECRET_PATH.test(path)) continue;
      const content = String(state.content || "");
      if (total + content.length > 24000) continue;
      files.push({ path, content });
      total += content.length;
      if (files.length >= 8) break;
    }
    return files;
  }

  // ---- unsaved drafts survive a restart -------------------------------------
  function persistSession() {
    sessionTimer = 0;
    const drafts = [];
    let total = 0;
    for (const [path, state] of openFiles) {
      if (!isUnsaved(state)) continue;
      const size = state.content.length + (state.existing ? state.savedContent.length : 0);
      if (total + size > SESSION_CHAR_LIMIT) continue; // too large: kept for this visit only
      total += size;
      drafts.push({
        path,
        content: state.content,
        existing: state.existing,
        savedContent: state.existing ? state.savedContent : "",
        origin: state.origin || "",
        touched: state.touched === true,
      });
    }
    try {
      if (drafts.length) {
        localStorage.setItem(
          SESSION_KEY,
          JSON.stringify({ version: 1, active: activePath, drafts }),
        );
      } else {
        localStorage.removeItem(SESSION_KEY);
      }
    } catch {
      /* storage is full or blocked: the drafts stay open for this visit only */
    }
  }
  function scheduleSession() {
    if (!sessionTimer) sessionTimer = setTimeout(persistSession, 400);
  }
  function restoreSession() {
    let stored = null;
    try {
      stored = JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
    } catch {}
    if (!stored || !Array.isArray(stored.drafts)) return;
    for (const draft of stored.drafts.slice(0, 40)) {
      if (
        !draft ||
        typeof draft.path !== "string" ||
        typeof draft.content !== "string" ||
        !supportedFilePath.test(draft.path)
      )
        continue;
      const existing = draft.existing === true && typeof draft.savedContent === "string";
      openFiles.set(draft.path, {
        content: draft.content,
        savedContent: existing ? draft.savedContent : "",
        existing,
        origin: draft.origin === "weronika" ? "weronika" : "",
        touched: draft.touched !== false, // unknown counts as the user's own typing
      });
    }
    restoredDrafts = openFiles.size;
    if (!restoredDrafts) return;
    activateFile(openFiles.has(stored.active) ? stored.active : openFiles.keys().next().value);
  }

  // ---- the editor: a text area over a coloured copy of its text --------------
  const indentUnit = () =>
    language.extension === "go" ? "\t" : language.extension === "py" ? "    " : "  ";

  function paintHighlight() {
    highlightFrame = 0;
    const text = editor.value;
    const plain = text.length > LIVE_HIGHLIGHT_LIMIT;
    codeBox.classList.toggle("plain", plain);
    highlightLayer.innerHTML = plain ? "" : highlightCode(text, language.id);
  }

  function paintEditor() {
    const text = editor.value;
    const lines = countLines(text);
    if (lines !== gutterLines) {
      gutterLines = lines;
      let numbers = "1";
      for (let line = 2; line <= lines; line += 1) numbers += `\n${line}`;
      gutterInner.textContent = numbers;
    }
    // Short files are coloured at once; long ones at most once per frame.
    if (text.length <= 20_000) {
      if (highlightFrame) cancelAnimationFrame(highlightFrame);
      paintHighlight();
    } else if (!highlightFrame) {
      highlightFrame = requestAnimationFrame(paintHighlight);
    }
    updateCaret();
  }

  function updateCaret() {
    const text = editor.value;
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const caret = editor.selectionDirection === "backward" ? start : end;
    let line = 1;
    let lineStart = 0;
    for (let at = text.indexOf("\n"); at !== -1 && at < caret; at = text.indexOf("\n", at + 1)) {
      line += 1;
      lineStart = at + 1;
    }
    const selected = end - start;
    $(".devtools-line-count").textContent =
      `Ln ${line}, Col ${caret - lineStart + 1}${selected ? ` (${selected} selected)` : ""}`;
    const offset = (line - 1) * LINE_HEIGHT - editor.scrollTop;
    activeLine.style.transform = `translateY(${offset}px)`;
    activeLine.hidden = !activePath || selected > 0;
    gutterCurrent.style.transform = `translateY(${offset}px)`;
    gutterCurrent.textContent = String(line);
    gutterCurrent.hidden = !activePath;
  }

  function syncScroll() {
    highlightBox.style.transform = `translate(${-editor.scrollLeft}px, ${-editor.scrollTop}px)`;
    gutterInner.style.transform = `translateY(${-editor.scrollTop}px)`;
    updateCaret();
  }

  function rememberView() {
    const state = openFiles.get(activePath);
    if (!state || panel.hidden) return;
    state.view = {
      top: editor.scrollTop,
      left: editor.scrollLeft,
      start: editor.selectionStart,
      end: editor.selectionEnd,
    };
  }

  function applyView(view) {
    const length = editor.value.length;
    try {
      editor.setSelectionRange(Math.min(view?.start ?? 0, length), Math.min(view?.end ?? 0, length));
    } catch {}
    editor.scrollTop = view?.top ?? 0;
    editor.scrollLeft = view?.left ?? 0;
    syncScroll();
  }

  function focusEditor() {
    if (activePath && finePointer() && !panel.hidden) editor.focus({ preventScroll: true });
  }

  // Type into the editor the way the keyboard does, so that undo keeps working.
  function insertText(text) {
    editor.focus({ preventScroll: true });
    let done = false;
    try {
      done = document.execCommand("insertText", false, text);
    } catch {}
    if (!done) {
      editor.setRangeText(text, editor.selectionStart, editor.selectionEnd, "end");
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  // Tab and Shift+Tab move the selected lines one indent step in or out.
  function indentSelection(outdent) {
    const unit = indentUnit();
    const { selectionStart: start, selectionEnd: end, value } = editor;
    if (start === end && !outdent) {
      insertText(unit);
      return;
    }
    const blockStart = value.lastIndexOf("\n", start - 1) + 1;
    // A selection that ends at the start of a line does not include that line.
    const lastChar = end > start && value[end - 1] === "\n" ? end - 1 : end;
    let blockEnd = value.indexOf("\n", lastChar);
    if (blockEnd < 0) blockEnd = value.length;
    const block = value.slice(blockStart, blockEnd);
    const step = unit === "\t" ? /^\t/ : new RegExp(`^(?:\\t| {1,${unit.length}})`);
    const changed = block
      .split("\n")
      .map((line) => (outdent ? line.replace(step, "") : line ? unit + line : line))
      .join("\n");
    if (changed === block) return;
    editor.setSelectionRange(blockStart, blockEnd);
    insertText(changed);
    if (start === end) {
      const caret = Math.max(blockStart, start - (block.length - changed.length));
      editor.setSelectionRange(caret, caret);
    } else {
      editor.setSelectionRange(blockStart, blockStart + changed.length);
    }
    updateCaret();
  }

  // Put the caret on a range and bring its line to the middle of the editor.
  function revealRange(start, end) {
    const length = editor.value.length;
    const from = Math.min(start, length);
    editor.focus({ preventScroll: true });
    editor.setSelectionRange(from, Math.min(end, length));
    const line = countLines(editor.value.slice(0, from)) - 1;
    editor.scrollTop = Math.max(0, line * LINE_HEIGHT - editor.clientHeight / 2 + LINE_HEIGHT);
    syncScroll();
  }

  // ---- open files -----------------------------------------------------------
  function showNoFile() {
    activePath = "";
    language = languageForPath("");
    editor.value = "";
    editor.readOnly = true;
    editor.tabIndex = -1;
    welcome.hidden = false;
    paintEditor();
    applyView(null);
    renderChrome();
  }

  function activateFile(path, options = {}) {
    const state = openFiles.get(path);
    if (!state) return;
    // Opening the tab that is already in front must not move the caret or the scroll.
    if (path !== activePath || editor.value !== state.content) {
      if (path !== activePath) rememberView();
      activePath = path;
      language = languageForPath(path);
      editor.readOnly = false;
      editor.tabIndex = 0;
      welcome.hidden = true;
      editor.value = state.content;
      paintEditor();
      applyView(state.view);
    }
    renderChrome();
    if (options.focus) focusEditor();
    scheduleSession();
  }

  function setEditorFile(path, content, existing) {
    openFiles.set(path, { content, savedContent: existing ? content : "", existing });
    activateFile(path, { focus: true });
  }

  function closeFileTab(path) {
    const state = openFiles.get(path);
    if (!state) return;
    if (
      state.content !== state.savedContent &&
      !window.confirm(`Discard unsaved changes in ${path}?`)
    )
      return;
    const paths = [...openFiles.keys()];
    const next = paths[paths.indexOf(path) + 1] || paths[paths.indexOf(path) - 1];
    openFiles.delete(path);
    if (activePath !== path) renderChrome();
    else if (next) activateFile(next, { focus: true });
    else showNoFile();
    scheduleSession();
  }

  // "U": a draft that is not stored yet. "M": unsaved changes to a file that is.
  function fileMark(path) {
    const state = openFiles.get(path);
    if (!state || !isUnsaved(state)) return "";
    return state.existing || knownPaths.has(path) ? "M" : "U";
  }
  const markClass = (mark) => (mark === "U" ? " new" : mark === "M" ? " modified" : "");
  const markNote = (mark) =>
    mark === "U" ? " · draft, not saved yet" : mark === "M" ? " · unsaved changes" : "";

  function fileBadge(path) {
    const [label, colour] = FILE_BADGES.get(languageForPath(path).extension) || ["≡", "#8aa9bd"];
    const badge = el("span", "devtools-file-badge", label);
    badge.style.color = colour;
    badge.setAttribute("aria-hidden", "true");
    return badge;
  }

  function renderEditorTabs() {
    const scroll = editorTabs.scrollLeft;
    editorTabs.replaceChildren();
    const names = new Map();
    for (const path of openFiles.keys())
      names.set(baseName(path), (names.get(baseName(path)) || 0) + 1);
    for (const [path, state] of openFiles) {
      const mark = fileMark(path);
      const tab = el(
        "div",
        `devtools-file-tab${path === activePath ? " active" : ""}${isUnsaved(state) ? " dirty" : ""}${markClass(mark)}`,
      );
      tab.title = `${path}${markNote(mark)}`;
      const select = makeButton("devtools-tab-name", baseName(path));
      select.setAttribute("role", "tab");
      select.setAttribute("aria-selected", String(path === activePath));
      // Two open files with the same name are told apart by their folder.
      if (names.get(baseName(path)) > 1 && dirName(path))
        select.append(el("small", "", dirName(path)));
      const close = makeButton("devtools-tab-close");
      close.setAttribute("aria-label", `Close ${path}`);
      close.addEventListener("click", (event) => {
        event.stopPropagation();
        closeFileTab(path);
      });
      tab.addEventListener("click", () => activateFile(path, { focus: true }));
      tab.addEventListener("auxclick", (event) => {
        if (event.button !== 1) return;
        event.preventDefault();
        closeFileTab(path);
      });
      tab.append(fileBadge(path), select, close);
      editorTabs.append(tab);
    }
    editorTabs.scrollLeft = scroll;
    revealActiveTab();
  }

  // Keep the tab in front inside the visible part of the tab strip.
  function revealActiveTab() {
    const tab = editorTabs.querySelector(".devtools-file-tab.active");
    if (!tab) return;
    const left = tab.offsetLeft;
    const right = left + tab.offsetWidth;
    if (left < editorTabs.scrollLeft) editorTabs.scrollLeft = left;
    else if (right > editorTabs.scrollLeft + editorTabs.clientWidth)
      editorTabs.scrollLeft = Math.min(left, right - editorTabs.clientWidth);
  }

  function renderOpenEditors() {
    const scroll = openList.scrollTop;
    openList.replaceChildren();
    for (const path of openFiles.keys()) {
      const mark = fileMark(path);
      const row = el(
        "div",
        `devtools-file${path === activePath ? " active" : ""}${markClass(mark)}`,
      );
      row.setAttribute("role", "button");
      row.tabIndex = 0;
      row.style.paddingLeft = "6px";
      row.title = `${path}${markNote(mark)}`;
      const close = makeButton("devtools-row-close", "×");
      close.setAttribute("aria-label", `Close ${path}`);
      close.addEventListener("click", (event) => {
        event.stopPropagation();
        closeFileTab(path);
      });
      row.append(close, fileBadge(path), el("span", "devtools-file-name", baseName(path)));
      if (mark) row.append(el("span", "devtools-file-state", mark));
      onActivate(row, () => activateFile(path, { focus: true }));
      openList.append(row);
    }
    if (!openFiles.size) openList.append(el("div", "workspace-empty", "No open files."));
    $(".open-count").textContent = String(openFiles.size);
    openList.scrollTop = scroll;
  }

  // Stored files and folders, plus the drafts that are not stored yet, as one tree.
  function buildTree(files, folders) {
    const root = [];
    const index = new Map([["", root]]);
    const folderFor = (path) => {
      if (index.has(path)) return index.get(path);
      const node = { kind: "directory", name: baseName(path), path, children: [] };
      folderFor(dirName(path)).push(node);
      index.set(path, node.children);
      return node.children;
    };
    for (const folder of folders) folderFor(folder);
    for (const file of files)
      folderFor(dirName(file.path)).push({ kind: "file", name: baseName(file.path), ...file });
    const order = (items) => {
      items.sort((a, b) =>
        a.kind !== b.kind
          ? a.kind === "directory"
            ? -1
            : 1
          : a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }),
      );
      for (const item of items) if (item.kind === "directory") order(item.children);
      return items;
    };
    return order(root);
  }

  function appendTree(items, depth, target) {
    for (const item of items) {
      if (item.kind === "directory") {
        const collapsed = collapsedFolders.has(item.path);
        const toggle = makeButton("devtools-file devtools-folder");
        toggle.style.paddingLeft = `${4 + depth * 12}px`;
        toggle.setAttribute("aria-expanded", String(!collapsed));
        toggle.setAttribute("aria-label", `${item.name} folder`);
        toggle.title = item.path;
        toggle.append(el("span", "devtools-chev", "⌄"), el("span", "devtools-file-name", item.name));
        const children = el("div", "devtools-folder-children");
        children.hidden = collapsed;
        appendTree(item.children, depth + 1, children);
        toggle.addEventListener("click", () => {
          const collapse = !children.hidden;
          children.hidden = collapse;
          toggle.setAttribute("aria-expanded", String(!collapse));
          if (collapse) collapsedFolders.add(item.path);
          else collapsedFolders.delete(item.path);
        });
        target.append(toggle, children);
      } else {
        const mark = fileMark(item.path);
        const row = makeButton(
          `devtools-file${item.path === activePath ? " active" : ""}${markClass(mark)}`,
        );
        row.style.paddingLeft = `${18 + depth * 12}px`;
        row.title = item.draft
          ? `${item.path} · draft, not saved yet`
          : `${item.path} (${item.size} bytes)${markNote(mark)}`;
        row.append(fileBadge(item.path), el("span", "devtools-file-name", item.name));
        if (mark) row.append(el("span", "devtools-file-state", mark));
        row.addEventListener("click", () => openFile(item.path));
        target.append(row);
      }
    }
  }

  function renderTree() {
    const scroll = fileList.scrollTop;
    const drafts = [...openFiles.keys()]
      .filter((path) => !knownPaths.has(path))
      .map((path) => ({ path, size: 0, draft: true }));
    const tree = buildTree([...listedFiles, ...drafts], listedFolders);
    fileList.replaceChildren();
    if (tree.length) appendTree(tree, 0, fileList);
    else
      fileList.append(
        el(
          "div",
          "workspace-empty",
          "No files yet. Ask Weronika to build something, or choose New File.",
        ),
      );
    fileList.scrollTop = scroll;
  }

  // The folder the files are stored in, as VS Code names its Explorer section.
  function projectName() {
    const folder = browserStorageMode ? "" : workspaceRoot.split(/[\\/]/).filter(Boolean).pop();
    return folder || "weronika-workspace";
  }

  function renderBreadcrumbs() {
    crumbs.replaceChildren();
    [projectName(), ...(activePath ? activePath.split("/") : [])].forEach((part, index) => {
      if (index) crumbs.append(el("i", "", "›"));
      crumbs.append(el("span", "", part));
    });
    const state = openFiles.get(activePath);
    const mark = fileMark(activePath);
    crumbNote.hidden = !mark;
    crumbNote.className = `devtools-crumb-note${mark === "M" ? " modified" : ""}`;
    crumbNote.textContent = !mark
      ? ""
      : state.existing
        ? "UNSAVED CHANGES"
        : `${state.origin === "weronika" ? "DRAFT FROM WERONIKA" : "NEW FILE"} · ${mark === "M" ? "REPLACES THE SAVED FILE ON SAVE" : "NOT SAVED"}`;
  }

  function renderStatusBar() {
    const unsaved = [...openFiles.values()].filter(isUnsaved).length;
    const drafts = $(".devtools-drafts");
    drafts.hidden = !unsaved;
    drafts.replaceChildren(`● ${unsaved} unsaved`, el("span", "optional-small", " · SAVE ALL"));
    const badge = $(".workspace-activity-badge");
    badge.hidden = !unsaved;
    badge.textContent = String(unsaved);
    $(".save-all").hidden = !unsaved;
    $(".save-all").classList.toggle("attention", unsaved > 0);
    $(".save-file").disabled = !activePath;
    $(".run-file").hidden = browserStorageMode || !activePath.toLowerCase().endsWith(".py");
    $(".devtools-language").textContent = activePath ? language.name : "No file";
    $(".devtools-indent").textContent =
      indentUnit() === "\t" ? "Tab Size: 4" : `Spaces: ${indentUnit().length}`;
    const title = $(".workspace-project .workspace-project-title");
    title.textContent = projectName();
    title.title = workspaceRoot;
  }

  // Redraw everything that shows which files are open and what state they are in.
  function renderChrome() {
    const hadFocus = panel.contains(document.activeElement);
    renderEditorTabs();
    renderOpenEditors();
    renderTree();
    renderBreadcrumbs();
    renderStatusBar();
    // Redrawing removes the row that was clicked; keep the keyboard inside the Workspace.
    if (hadFocus && !panel.contains(document.activeElement)) panel.focus({ preventScroll: true });
  }

  editor.addEventListener("input", () => {
    const state = openFiles.get(activePath);
    if (!state) return;
    const wasUnsaved = isUnsaved(state);
    state.content = editor.value;
    state.touched = true; // the user's own typing: never replaced without asking
    paintEditor();
    if (wasUnsaved !== isUnsaved(state)) renderChrome();
    scheduleSession();
  });
  editor.addEventListener("scroll", syncScroll);
  for (const type of ["keyup", "mouseup", "select", "focus"])
    editor.addEventListener(type, updateCaret);
  document.addEventListener("selectionchange", () => {
    if (document.activeElement === editor) updateCaret();
  });
  let releaseTab = false; // Escape, then Tab, moves the focus out of the editor
  editor.addEventListener("keydown", (event) => {
    if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "Escape") {
      releaseTab = true;
      return;
    }
    const release = releaseTab;
    releaseTab = false;
    if (event.key === "Tab" && !release) {
      event.preventDefault();
      indentSelection(event.shiftKey);
    } else if (event.key === "Enter" && !event.shiftKey) {
      // A new line starts at the indentation of the line above it, and one step
      // deeper after an opening bracket or a Python colon.
      const { selectionStart: start, selectionEnd: end, value } = editor;
      const before = value.slice(value.lastIndexOf("\n", start - 1) + 1, start);
      const indent = /^[ \t]*/.exec(before)[0];
      const last = before.trimEnd().slice(-1);
      const closer = { "{": "}", "[": "]", "(": ")" }[last] || "";
      const deeper = Boolean(closer) || (last === ":" && language.extension === "py");
      if (!indent && !deeper) return;
      event.preventDefault();
      if (closer && start === end && value[start] === closer) {
        // Between a pair of brackets: the closing one moves to a line of its own.
        const inner = `\n${indent}${indentUnit()}`;
        insertText(`${inner}\n${indent}`);
        editor.setSelectionRange(start + inner.length, start + inner.length);
        updateCaret();
      } else {
        insertText(`\n${indent}${deeper ? indentUnit() : ""}`);
      }
    }
  });

  // ---- stored files ---------------------------------------------------------
  function flattenListing(items, files = [], folders = []) {
    for (const item of items || []) {
      if (!item || typeof item.path !== "string") continue;
      if (item.kind === "directory") {
        folders.push(item.path);
        flattenListing(item.children, files, folders);
      } else if (item.kind === "file") {
        files.push({ path: item.path, size: Number(item.size) || 0 });
      }
    }
    return { files, folders };
  }

  async function refreshFiles(options = {}) {
    const quiet = options && options.quiet === true;
    searchCache = null;
    try {
      const result = await request("/api/workspace/files");
      workspaceRoot = result.root || "";
      ({ files: listedFiles, folders: listedFolders } = flattenListing(result.items));
      browserStorageMode = false;
      $(".devtools-connection").textContent = "● LOCAL WORKSPACE";
      if (!quiet)
        status(
          codeStatus,
          workspaceRoot ? `LOCAL WORKSPACE · ${workspaceRoot}` : "Local workspace connected.",
        );
    } catch (error) {
      if (!error.localApiUnavailable) {
        fail(error.message);
        return;
      }
      browserStorageMode = true;
      workspaceRoot = "Browser storage · this browser only";
      listedFiles = Object.entries(readBrowserWorkspace()).map(([path, content]) => ({
        path,
        size: new Blob([content]).size,
      }));
      listedFolders = [];
      $(".devtools-connection").textContent = "● BROWSER STORAGE";
      if (!quiet)
        status(codeStatus, `${workspaceRoot} · Python execution requires weronika-py/start.bat.`);
    }
    knownPaths = new Set(listedFiles.map((file) => file.path));
    renderChrome();
    if (restoredDrafts && !quiet) {
      status(
        codeStatus,
        `Restored ${restoredDrafts} unsaved draft${restoredDrafts === 1 ? "" : "s"} from your last visit.`,
      );
      restoredDrafts = 0;
    }
  }

  async function openFile(path) {
    try {
      const cached = openFiles.get(path);
      if (cached) {
        activateFile(path, { focus: true });
        status(codeStatus, `Opened ${path}${isUnsaved(cached) ? " · unsaved changes" : ""}`);
      } else if (browserStorageMode) {
        const content = readBrowserWorkspace()[path];
        if (typeof content !== "string")
          throw new Error(`Could not find ${path} in browser storage.`);
        setEditorFile(path, content, true);
        status(codeStatus, `Opened ${path} · ${new Blob([content]).size} bytes · browser storage`);
      } else {
        const result = await request(`/api/workspace/file?path=${encodeURIComponent(path)}`);
        // A draft may have arrived for this path while the file was loading; keep it.
        if (openFiles.has(result.path)) activateFile(result.path, { focus: true });
        else setEditorFile(result.path, result.content, true);
        status(codeStatus, `Opened ${result.path} · ${result.size} bytes`);
      }
      if (narrow()) setSideOpen(false);
    } catch (error) {
      if (error.localApiUnavailable) await refreshFiles({ quiet: true });
      fail(error.message);
    }
  }

  // Write one open file to the workspace. Returns true when it was stored.
  async function saveFile(path = activePath, options = {}) {
    const state = openFiles.get(path);
    if (!state) {
      fail("Open or create a file first, then choose SAVE.");
      return false;
    }
    const content = state.content;
    const stored = (savedPath) => {
      // Typing may have continued while the file was being written; only what was
      // written counts as saved.
      state.savedContent = content;
      state.existing = true;
      if (savedPath !== path && openFiles.get(path) === state && !openFiles.has(savedPath)) {
        openFiles.delete(path);
        openFiles.set(savedPath, state);
        if (activePath === path) activePath = savedPath;
      }
      scheduleSession();
    };
    try {
      if (browserStorageMode) {
        if (!supportedFilePath.test(path))
          throw new Error("Use a safe relative path with a supported code or text extension.");
        const files = readBrowserWorkspace();
        if (
          Object.hasOwn(files, path) &&
          !state.existing &&
          !options.overwrite &&
          !window.confirm(`“${path}” already exists in browser storage. Overwrite it?`)
        ) {
          logOutput(`${path}: left unsaved, because you chose not to overwrite the stored file.`);
          return false;
        }
        files[path] = content;
        try {
          localStorage.setItem(browserWorkspaceKey, JSON.stringify(files));
        } catch {
          throw new Error(
            "This browser’s storage is full. Download the project as a ZIP, or start weronika-py to save to disk.",
          );
        }
        stored(path);
        if (!options.batch) {
          await refreshFiles({ quiet: true });
          status(
            codeStatus,
            `Saved ${path} in this browser only · Python run requires the local worker.`,
          );
        }
      } else {
        let result;
        try {
          result = await post("/api/workspace/file", {
            path,
            content,
            overwrite: state.existing || options.overwrite === true,
          });
        } catch (error) {
          if (!/already exists/i.test(error.message)) throw error;
          if (!window.confirm(`“${path}” already exists. Overwrite it with the editor contents?`)) {
            logOutput(`${path}: left unsaved, because you chose not to overwrite the stored file.`);
            status(codeStatus, `${path} was not saved; the stored file is unchanged.`);
            return false;
          }
          result = await post("/api/workspace/file", { path, content, overwrite: true });
        }
        stored(typeof result.path === "string" && result.path ? result.path : path);
        if (!options.batch) {
          await refreshFiles({ quiet: true });
          status(codeStatus, `Saved ${result.path || path} · ${result.size} bytes`);
        }
      }
      if (!options.batch && panel.classList.contains("preview-open")) void refreshPreview();
      return true;
    } catch (error) {
      if (error.localApiUnavailable) {
        await refreshFiles({ quiet: true });
        fail(
          "The local worker went offline, so nothing was written. This browser’s storage is in use now; choose SAVE again to keep the file here.",
        );
      } else {
        fail(options.batch ? `${path}: ${error.message}` : error.message);
      }
      return false;
    }
  }

  async function saveAll() {
    const paths = [...openFiles].filter(([, state]) => isUnsaved(state)).map(([path]) => path);
    if (!paths.length) {
      status(codeStatus, "Nothing to save: every open file is already stored.");
      return;
    }
    // Drafts that would replace a stored file are confirmed together, once.
    const replacing = paths.filter((path) => !openFiles.get(path).existing && knownPaths.has(path));
    const overwrite =
      !replacing.length ||
      window.confirm(
        `SAVE ALL would replace ${replacing.length === 1 ? "this stored file" : `these ${replacing.length} stored files`} with the draft in the editor:\n\n${replacing.join("\n")}\n\nOverwrite?`,
      );
    let saved = 0;
    for (const path of paths) {
      if (replacing.includes(path)) {
        if (!overwrite) {
          logOutput(`${path}: left unsaved, because you chose not to overwrite the stored file.`);
          continue;
        }
        if (await saveFile(path, { batch: true, overwrite: true })) saved += 1;
      } else if (await saveFile(path, { batch: true })) saved += 1;
    }
    await refreshFiles({ quiet: true });
    if (panel.classList.contains("preview-open")) void refreshPreview();
    const where = browserStorageMode ? " in this browser only" : "";
    if (saved === paths.length)
      status(codeStatus, `Saved ${saved} file${saved === 1 ? "" : "s"}${where}.`);
    else
      status(
        codeStatus,
        `Saved ${saved} of ${paths.length} files${where}. The rest are still unsaved; see OUTPUT for the reason.`,
        true,
      );
    if (saved !== paths.length) setPanelOpen(true);
  }

  async function collectWorkspaceFiles() {
    let files = [];
    if (browserStorageMode) {
      files = Object.entries(readBrowserWorkspace()).map(([path, content]) => ({ path, content }));
    } else {
      try {
        const result = await request("/api/workspace/files");
        const paths = flattenListing(result.items)
          .files.map((file) => file.path)
          .filter((path) => supportedFilePath.test(path));
        if (paths.length > 500)
          throw new Error(
            "The workspace contains more than 500 files; download smaller folders separately.",
          );
        for (const path of paths) {
          const file = await request(`/api/workspace/file?path=${encodeURIComponent(path)}`);
          files.push({ path: file.path, content: file.content });
        }
      } catch (error) {
        if (!error.localApiUnavailable) throw error;
        browserStorageMode = true;
        files = Object.entries(readBrowserWorkspace()).map(([path, content]) => ({
          path,
          content,
        }));
      }
    }
    const byPath = new Map(files.map((file) => [file.path, file.content]));
    for (const [path, state] of openFiles) {
      if (supportedFilePath.test(path)) byPath.set(path, state.content);
    }
    const merged = [...byPath].map(([path, content]) => ({ path, content }));
    if (panel.classList.contains("preview-open") && merged !== previewFiles) {
      previewFiles = merged;
      queueMicrotask(() => {
        if (previewFrame) loadPreview(merged);
      });
    }
    return merged;
  }

  async function downloadWorkspaceZip() {
    const button = $(".download-zip");
    button.disabled = true;
    try {
      const files = await collectWorkspaceFiles();
      if (!files.length) throw new Error("There are no saved or open files to download yet.");
      const blob = createStoredZip(files);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `weronika-workspace-${new Date().toISOString().slice(0, 10)}.zip`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
      status(
        codeStatus,
        `Downloaded ZIP · ${files.length} file${files.length === 1 ? "" : "s"} · ${(blob.size / 1024).toFixed(1)} KB`,
      );
    } catch (error) {
      fail(error instanceof Error ? error.message : "Could not create the workspace ZIP.");
    } finally {
      button.disabled = false;
    }
  }

  async function runPython() {
    const path = activePath;
    const state = openFiles.get(path);
    if (browserStorageMode) {
      fail("Python execution needs the local worker. Run weronika-py/start.bat on this PC.");
      return;
    }
    if (!state || !path.toLowerCase().endsWith(".py")) {
      fail("Open a Python file to run it.");
      return;
    }
    if (isUnsaved(state)) {
      fail("Save the current Python file before running it.");
      return;
    }
    if (
      !window.confirm(
        `Run ${path} with the local Python interpreter? Code can access this device and your files. Continue only if you trust it.`,
      )
    )
      return;
    setPanelOpen(true);
    logOutput(`$ python ${path}`);
    status(codeStatus, `Running ${path}…`);
    try {
      const result = await post("/api/workspace/run", { path, confirmed: true });
      const failed = result.returncode !== 0 || Boolean(result.timed_out);
      const summary = `Exit ${result.returncode ?? "timeout"}${result.timed_out ? " · stopped after timeout" : ""}`;
      const output =
        [result.stdout && `stdout:\n${result.stdout}`, result.stderr && `stderr:\n${result.stderr}`]
          .filter(Boolean)
          .join("\n\n") || "(no output)";
      logOutput(`${summary}\n${output}`, failed);
      status(codeStatus, `${path} · ${summary} · the output is in the OUTPUT panel`, failed);
    } catch (error) {
      fail(error.message);
    }
  }

  // ---- search in files ------------------------------------------------------
  async function searchableFiles() {
    if (!searchCache) searchCache = await collectWorkspaceFiles();
    const byPath = new Map(searchCache.map((file) => [file.path, file.content]));
    for (const [path, state] of openFiles) byPath.set(path, state.content);
    return [...byPath].map(([path, content]) => ({ path, content }));
  }

  async function runSearch() {
    const query = searchInput.value;
    const token = ++searchToken;
    if (query.trim().length < 2) {
      searchResults.replaceChildren();
      searchSummary.textContent = "Type at least two characters to search the workspace.";
      return;
    }
    searchSummary.textContent = "Searching…";
    let files;
    try {
      files = await searchableFiles();
    } catch (error) {
      if (token === searchToken) searchSummary.textContent = error.message;
      return;
    }
    if (token !== searchToken) return;
    const pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    const LIMIT = 300;
    let hits = 0;
    let fileCount = 0;
    searchResults.replaceChildren();
    for (const file of files) {
      if (hits >= LIMIT) break;
      pattern.lastIndex = 0;
      let match = pattern.exec(file.content);
      if (!match) continue;
      fileCount += 1;
      const heading = el("div", "workspace-search-file");
      heading.title = file.path;
      heading.append(fileBadge(file.path), el("span", "", file.path));
      searchResults.append(heading);
      let line = 1;
      let counted = 0;
      while (match && hits < LIMIT) {
        const { index } = match;
        const length = match[0].length;
        for (let at = file.content.indexOf("\n", counted); at !== -1 && at < index; at = file.content.indexOf("\n", at + 1))
          line += 1;
        counted = index;
        const lineStart = file.content.lastIndexOf("\n", index - 1) + 1;
        let lineEnd = file.content.indexOf("\n", index);
        if (lineEnd < 0) lineEnd = file.content.length;
        const from = Math.max(lineStart, index - 14);
        const row = makeButton("workspace-search-hit");
        row.title = `${file.path}:${line}`;
        row.append(
          `${line}: ${from > lineStart ? "…" : ""}${file.content.slice(from, index).trimStart()}`,
          el("b", "", file.content.slice(index, index + length)),
          file.content.slice(index + length, Math.min(lineEnd, index + length + 120)),
        );
        row.addEventListener("click", async () => {
          await openFile(file.path);
          if (activePath === file.path) revealRange(index, index + length);
        });
        searchResults.append(row);
        hits += 1;
        // One row per line: go on from the start of the next line.
        pattern.lastIndex = lineEnd + 1;
        match = lineEnd + 1 <= file.content.length ? pattern.exec(file.content) : null;
      }
    }
    searchSummary.textContent = !hits
      ? "No results. Saved files and open drafts were searched."
      : `${hits} line${hits === 1 ? "" : "s"} in ${fileCount} file${fileCount === 1 ? "" : "s"}${hits >= LIMIT ? ` · first ${LIMIT} shown` : ""}`;
  }
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 220);
  });

  // ---- quick input: go to file, new file, save as ----------------------------
  function closeQuick() {
    if (quick.hidden) return false;
    quick.hidden = true;
    quickState = null;
    return true;
  }

  function renderQuick() {
    quickList.replaceChildren();
    if (quickState.kind !== "files") {
      quickList.append(
        el(
          "div",
          `workspace-empty${quickState.error ? " error" : ""}`,
          quickState.error || quickState.hint,
        ),
      );
      return;
    }
    const query = quickInput.value.trim().toLowerCase();
    const paths = [...new Set([...openFiles.keys(), ...knownPaths])];
    const ranked = [];
    for (const path of paths) {
      const lower = path.toLowerCase();
      const name = baseName(lower);
      const score = !query
        ? openFiles.has(path)
          ? 0
          : 1
        : name.startsWith(query)
          ? 0
          : name.includes(query)
            ? 1
            : lower.includes(query)
              ? 2
              : isSubsequence(query, lower)
                ? 3
                : -1;
      if (score >= 0) ranked.push([score, path]);
    }
    ranked.sort((a, b) => a[0] - b[0] || a[1].length - b[1].length || a[1].localeCompare(b[1]));
    quickState.items = ranked.slice(0, 40).map(([, path]) => path);
    quickState.selected = Math.min(quickState.selected, Math.max(0, quickState.items.length - 1));
    if (!quickState.items.length) {
      quickList.append(
        el(
          "div",
          "workspace-empty",
          paths.length ? "No matching files." : "No files yet. Choose File › New File…",
        ),
      );
      return;
    }
    quickState.items.forEach((path, index) => {
      const item = makeButton(
        `devtools-quickopen-item${index === quickState.selected ? " selected" : ""}`,
      );
      item.append(fileBadge(path), el("span", "", baseName(path)), el("small", "", dirName(path)));
      item.addEventListener("click", () => {
        closeQuick();
        void openFile(path);
      });
      quickList.append(item);
      if (index !== quickState.selected) return;
      if (item.offsetTop < quickList.scrollTop) quickList.scrollTop = item.offsetTop;
      else if (item.offsetTop + item.offsetHeight > quickList.scrollTop + quickList.clientHeight)
        quickList.scrollTop = item.offsetTop + item.offsetHeight - quickList.clientHeight;
    });
  }

  function openQuick(config) {
    unfold();
    closeMenus();
    quickState = { selected: 0, items: [], error: "", ...config };
    quick.hidden = false;
    quickInput.value = config.value || "";
    quickInput.placeholder = config.placeholder;
    quickInput.setAttribute("aria-label", config.placeholder);
    renderQuick();
    quickInput.focus({ preventScroll: true });
  }

  const goToFile = () =>
    openQuick({ kind: "files", placeholder: "Go to file: type part of a file name" });

  function promptNewFile() {
    openQuick({
      kind: "name",
      value: dirName(activePath) ? `${dirName(activePath)}/` : "",
      placeholder: "New file name, for example src/main.py",
      hint: "Enter creates the file as an unsaved draft · Esc cancels",
      accept(path) {
        if (!supportedFilePath.test(path)) return PATH_HELP;
        if (openFiles.has(path) || knownPaths.has(path)) {
          void openFile(path);
          return "";
        }
        setEditorFile(path, "", false);
        status(codeStatus, `New file ${path} · write the code, then choose SAVE.`);
        return "";
      },
    });
  }

  function promptSaveAs() {
    const from = activePath;
    const state = openFiles.get(from);
    if (!state) {
      fail("Open or create a file first, then choose SAVE.");
      return;
    }
    openQuick({
      kind: "name",
      value: from,
      placeholder: "Save as: the new path of this file",
      hint: "Enter saves the editor contents under this path · Esc cancels",
      accept(path) {
        if (!supportedFilePath.test(path)) return PATH_HELP;
        if (path !== from) {
          if (openFiles.has(path)) return `${path} is already open. Close it, or choose another name.`;
          if (openFiles.get(from) !== state) return "That file is no longer open.";
          openFiles.set(path, {
            content: state.content,
            savedContent: "",
            existing: false,
            origin: state.origin,
          });
          // The copy takes the edits; a stored original goes back to what is stored.
          if (state.existing) state.content = state.savedContent;
          else openFiles.delete(from);
          activateFile(path, { focus: true });
        }
        void saveFile(path);
        return "";
      },
    });
  }

  quickInput.addEventListener("input", () => {
    if (!quickState) return;
    quickState.selected = 0;
    quickState.error = "";
    renderQuick();
  });
  quickInput.addEventListener("keydown", (event) => {
    if (!quickState || event.isComposing) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const count = quickState.items.length;
      if (!count) return;
      quickState.selected =
        (quickState.selected + (event.key === "ArrowDown" ? 1 : count - 1)) % count;
      renderQuick();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (quickState.kind === "files") {
        const path = quickState.items[quickState.selected];
        if (!path) return;
        closeQuick();
        void openFile(path);
        return;
      }
      const current = quickState;
      const problem = current.accept(quickInput.value.trim());
      if (problem) {
        current.error = problem;
        if (quickState === current) renderQuick();
      } else if (quickState === current) {
        closeQuick();
      }
    }
  });

  // ---- layout: side bar, output panel, chat, preview --------------------------
  function setPressed(selector, pressed) {
    for (const button of $$(selector)) button.setAttribute("aria-pressed", String(pressed));
  }
  function setSideOpen(open) {
    panel.classList.toggle("side-closed", !open);
    setPressed(".toggle-side", open);
    for (const button of $$(".workspace-activity-btn[data-view]"))
      button.classList.toggle("active", open && !$(`.workspace-view[data-view="${button.dataset.view}"]`).hidden);
  }
  const sideOpen = () => !panel.classList.contains("side-closed");
  // Choosing the view that is already showing closes the side bar, as in VS Code.
  function showView(view, toggle = false) {
    const current = $(`.workspace-view[data-view="${view}"]`);
    if (toggle && sideOpen() && !current.hidden) {
      setSideOpen(false);
      return;
    }
    for (const section of $$(".workspace-view")) section.hidden = section !== current;
    setSideOpen(true);
    if (view === "search") {
      searchInput.focus({ preventScroll: true });
      searchInput.select();
    }
  }
  function setPanelOpen(open) {
    outputPanel.hidden = !open;
    setPressed(".toggle-panel", open);
    if (open) outputLog.scrollTop = outputLog.scrollHeight;
  }
  function setAgentOpen(open) {
    panel.classList.toggle("agent-closed", !open);
    setPressed(".toggle-agent", open);
  }
  function setPreviewOpen(open) {
    panel.classList.toggle("preview-open", open);
    setPressed(".preview-toggle", open);
    // The preview pane has its own close button; the tabs get the room instead.
    $(".devtools-editor-actions .preview-toggle").hidden = open;
    if (open) void refreshPreview();
  }

  function syncOpenState() {
    // The orb keeps its answer banner out of the way while the Workspace covers it.
    document.body.classList.toggle(
      "workspace-open",
      !panel.hidden && !panel.classList.contains("minimised"),
    );
  }

  function open() {
    panel.hidden = false;
    panel.classList.remove("minimised");
    syncOpenState();
    // Scroll positions cannot be set while the panel is hidden; apply them now.
    applyView(openFiles.get(activePath)?.view);
    void refreshFiles();
    if (finePointer() && !panel.contains(document.activeElement))
      (promptInput.closest(".agent-closed") ? panel : promptInput).focus({ preventScroll: true });
  }
  if (launch) launch.addEventListener("click", open);

  function closeWorkspace() {
    rememberView();
    closeMenus();
    closeQuick();
    const hadFocus = panel.contains(document.activeElement);
    panel.hidden = true;
    syncOpenState();
    if (hadFocus && launch) launch.focus({ preventScroll: true });
  }
  $(".devtools-close").addEventListener("click", closeWorkspace);
  $(".devtools-light.close").addEventListener("click", closeWorkspace);

  // macOS-style minimise: collapse to just the title bar.
  let unfoldedAt = 0;
  function unfold() {
    if (!panel.classList.contains("minimised")) return false;
    panel.classList.remove("minimised");
    unfoldedAt = performance.now();
    syncOpenState();
    applyView(openFiles.get(activePath)?.view);
    return true;
  }
  $(".devtools-light.min").addEventListener("click", () => {
    closeMenus();
    closeQuick();
    if (unfold()) return;
    rememberView();
    panel.classList.add("minimised");
    syncOpenState();
  });
  // Folded away, the whole title bar is the handle that brings the Workspace back.
  $(".devtools-top").addEventListener(
    "click",
    (event) => {
      if (!panel.classList.contains("minimised")) return;
      if (event.target instanceof Element && event.target.closest(".devtools-lights, .devtools-close")) return;
      event.preventDefault();
      event.stopPropagation();
      unfold();
    },
    true,
  );

  // macOS-style zoom: fill the viewport, or return to the floating window.
  $(".devtools-light.max").addEventListener("click", () => {
    panel.classList.toggle("zoomed");
    syncScroll();
  });

  // ---- menus ----------------------------------------------------------------
  function closeMenus() {
    if (!menuPopup) return false;
    menuPopup.remove();
    menuPopup = null;
    for (const button of $$(".devtools-menu")) button.setAttribute("aria-expanded", "false");
    return true;
  }
  const editCommand = (command) => {
    editor.focus({ preventScroll: true });
    try {
      document.execCommand(command);
    } catch {}
  };
  // [label, action, shortcut, enabled]; null draws a rule.
  const menus = {
    file: () => [
      ["New File…", promptNewFile],
      ["Go to File…", goToFile, keyLabel("P")],
      null,
      ["Save", () => void saveFile(), keyLabel("S"), Boolean(activePath)],
      ["Save As…", promptSaveAs, "", Boolean(activePath)],
      ["Save All", () => void saveAll(), keyLabel("S", true)],
      null,
      ["Download Project as ZIP", () => void downloadWorkspaceZip()],
      null,
      ["Close Editor", () => closeFileTab(activePath), "", Boolean(activePath)],
      ["Close Workspace", closeWorkspace],
    ],
    edit: () => [
      ["Undo", () => editCommand("undo"), keyLabel("Z"), Boolean(activePath)],
      ["Redo", () => editCommand("redo"), mac ? "⇧⌘Z" : "Ctrl+Y", Boolean(activePath)],
      null,
      ["Find in Files", () => showView("search"), keyLabel("F", true)],
    ],
    view: () => [
      ["Explorer", () => showView("explorer"), keyLabel("E", true)],
      ["Search", () => showView("search"), keyLabel("F", true)],
      null,
      ["Toggle Side Bar", () => setSideOpen(!sideOpen()), keyLabel("B")],
      ["Toggle Output Panel", () => setPanelOpen(outputPanel.hidden), keyLabel("J")],
      ["Toggle Weronika Chat", () => setAgentOpen(panel.classList.contains("agent-closed"))],
      ["Toggle Live Preview", () => setPreviewOpen(!panel.classList.contains("preview-open"))],
    ],
    run: () => [
      [
        "Run Python File",
        () => void runPython(),
        "",
        !browserStorageMode && activePath.toLowerCase().endsWith(".py"),
      ],
      ["Reload Live Preview", () => setPreviewOpen(true)],
    ],
  };
  function openMenu(button) {
    unfold();
    closeMenus();
    closeQuick();
    menuPopup = el("div", "devtools-menu-popup");
    menuPopup.setAttribute("role", "menu");
    for (const entry of menus[button.dataset.menu]()) {
      if (!entry) {
        menuPopup.append(el("div", "devtools-menu-rule"));
        continue;
      }
      const [label, action, shortcut = "", enabled = true] = entry;
      const item = makeButton("devtools-menu-item");
      item.setAttribute("role", "menuitem");
      item.disabled = !enabled;
      item.append(el("span", "", label));
      if (shortcut) item.append(el("small", "", shortcut));
      item.addEventListener("click", () => {
        closeMenus();
        action();
      });
      menuPopup.append(item);
    }
    menuPopup.style.left = `${Math.round(button.getBoundingClientRect().left - panel.getBoundingClientRect().left)}px`;
    button.setAttribute("aria-expanded", "true");
    panel.append(menuPopup);
  }
  for (const button of $$(".devtools-menu")) {
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-expanded") === "true") closeMenus();
      else openMenu(button);
    });
    // With one menu open, moving along the menu bar opens the others.
    button.addEventListener("mouseenter", () => {
      if (menuPopup && button.getAttribute("aria-expanded") !== "true") openMenu(button);
    });
  }
  document.addEventListener(
    "pointerdown",
    (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (menuPopup && !(target && (menuPopup.contains(target) || target.closest(".devtools-menu"))))
        closeMenus();
      if (!quick.hidden && !(target && (quick.contains(target) || target.closest(".devtools-command"))))
        closeQuick();
    },
    true,
  );

  // ---- live preview -------------------------------------------------------
  const previewFrame = $(".workspace-preview-frame");
  const previewRefresh = $(".preview-refresh");

  function previewBlobUrl(files) {
    // Render the project's own HTML in a sandboxed frame, with its CSS and JS
    // inlined, so the preview never needs a server or network access.
    const list = Array.isArray(files) ? files : [];
    const byPath = new Map(
      list.map((file) => [String(file.path || ""), String(file.content || "")]),
    );
    // The HTML page in front is previewed; otherwise the project's index page.
    const pages = [...byPath.keys()].filter((path) => /\.html?$/i.test(path));
    const entry =
      pages.find((path) => path === activePath) ||
      pages.find((path) => /^index\.html?$/i.test(path)) ||
      pages.find((path) => /(?:^|\/)index\.html?$/i.test(path)) ||
      pages[0];
    if (!entry) return "";
    // A file is looked up next to the page first, then from the project root.
    const folder = dirName(entry) ? `${dirName(entry)}/` : "";
    const find = (reference) => {
      const path = reference.replace(/^\.?\//, "");
      return byPath.get(folder + path) ?? byPath.get(path) ?? byPath.get(reference);
    };
    let html = byPath.get(entry) || "";
    html = html.replace(/<link[^>]+href=["']([^"']+\.css)["'][^>]*>/gi, (match, href) => {
      const css = find(href);
      return css ? `<style>${css.replace(/<\/style/gi, "<\\/style")}</style>` : match;
    });
    html = html.replace(
      /<script[^>]+src=["']([^"']+\.js)["'][^>]*>\s*<\/script>/gi,
      (match, src) => {
        const js = find(src);
        if (!js) return match;
        // A module stays a module, and code that mentions "</script>" must not end the tag.
        const type = /\btype=["']module["']/i.test(match) ? ' type="module"' : "";
        return `<script${type}>${js.replace(/<\/script/gi, "<\\/script")}</script>`;
      },
    );
    return URL.createObjectURL(new Blob([html], { type: "text/html" }));
  }

  function loadPreview(files) {
    if (!previewFrame) return;
    previewFiles = Array.isArray(files) ? files : previewFiles;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = previewBlobUrl(previewFiles);
    if (!previewUrl) {
      previewFrame.style.display = "none";
      const head = panel.querySelector(".workspace-preview-head");
      if (head && !head.querySelector(".preview-empty")) {
        const note = document.createElement("span");
        note.className = "preview-empty";
        note.textContent = " · no HTML file yet";
        head.insertBefore(note, previewRefresh);
      }
      return;
    }
    previewFrame.style.display = "";
    const note = panel.querySelector(".preview-empty");
    if (note) note.remove();
    previewFrame.src = previewUrl;
  }

  async function refreshPreview() {
    try {
      loadPreview(await collectWorkspaceFiles());
    } catch (error) {
      fail(error instanceof Error ? error.message : "Could not build the preview.");
    }
  }

  for (const button of $$(".preview-toggle"))
    button.addEventListener("click", () =>
      setPreviewOpen(!panel.classList.contains("preview-open")),
    );
  previewRefresh.addEventListener("click", () => void refreshPreview());
  $(".preview-close").addEventListener("click", () => setPreviewOpen(false));

  // ---- the statement relay: Workspace → orb → brain → editor ------------------
  const STAGE_LABELS = {
    statement: "Weronika: statement sent",
    orb: "Weronika: the orb has it",
    brain: "Weronika: the brain is working…",
    workspace: "Weronika: files delivered",
    answer: "Weronika: answered",
    idle: "Weronika: ready",
  };
  const STAGE_NOTES = {
    statement: "Handing your statement to the orb…",
    orb: "The orb is passing your statement to the brain…",
    brain: "The brain is working on it…",
  };
  function setStage(next) {
    stage = Object.hasOwn(STAGE_LABELS, next) ? next : "idle";
    clearTimeout(stageTimer);
    // An answer without files stops at the brain; files travel on to the editor.
    const reach = stage === "answer" ? STAGES.indexOf("brain") : STAGES.indexOf(stage);
    const working = stage === "statement" || stage === "orb" || stage === "brain";
    routeSteps.forEach((step, index) => {
      step.classList.toggle("lit", index <= reach);
      step.classList.toggle("busy", working && index === reach);
    });
    routeArrows.forEach((arrow, index) => arrow.classList.toggle("lit", index < reach));
    stageItem.textContent = STAGE_LABELS[stage];
    stageItem.classList.toggle("live", stage !== "idle");
    if (stage === "workspace" || stage === "answer")
      stageTimer = setTimeout(() => setStage("idle"), 6000);
  }

  async function submitWorkspacePrompt() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      status(buildStatus, "Describe the code or project you want Weronika to build.", true);
      promptInput.focus();
      return;
    }
    if (promptBusy) {
      status(buildStatus, "Weronika is still working on your last statement…");
      return;
    }
    if (typeof onPrompt !== "function") {
      status(buildStatus, "The cloud brain is not connected to Workspace yet.", true);
      appendWorkspaceMessage("assistant", "The cloud brain is not connected to Workspace yet.");
      return;
    }
    promptBusy = true;
    appendWorkspaceMessage("user", prompt);
    buildButton.disabled = true;
    status(buildStatus, "Weronika is working…");
    setStage("statement");
    const started = Date.now();
    const pending = appendWorkspaceMessage("system", STAGE_NOTES.statement);
    const ticker = setInterval(() => {
      pending.textContent = `${STAGE_NOTES[stage] || "Working…"} ${Math.round((Date.now() - started) / 1000)} s`;
    }, 1000);
    promptInput.value = "";
    try {
      const reply = await onPrompt(prompt, getWorkspaceContext(), { onStage: setStage });
      const message = reply || "Draft ready. Review the editor tabs, then save the files.";
      appendWorkspaceMessage("assistant", message);
      if (stage === "statement" || stage === "orb" || stage === "brain") setStage("answer");
      status(
        buildStatus,
        stage === "workspace"
          ? "Finished · review the drafts in the editor, then choose SAVE or SAVE ALL."
          : stage === "answer"
            ? "Finished · Weronika answered. Your files were not changed."
            : "Ready · statements go through the orb to Weronika’s cloud brain.",
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Weronika could not build that draft.";
      appendWorkspaceMessage("assistant", message);
      status(buildStatus, message, true);
      setStage("idle");
    } finally {
      clearInterval(ticker);
      pending.remove();
      promptBusy = false;
      buildButton.disabled = false;
      if (finePointer()) promptInput.focus({ preventScroll: true });
    }
  }
  buildButton.addEventListener("click", submitWorkspacePrompt);
  promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      submitWorkspacePrompt();
    }
  });

  // What the workspace holds for a path, or null when nothing is stored there.
  async function storedContent(path) {
    const open = openFiles.get(path);
    if (open && open.existing) return open.savedContent;
    if (!knownPaths.has(path)) return null;
    try {
      if (browserStorageMode) {
        const content = readBrowserWorkspace()[path];
        return typeof content === "string" ? content : null;
      }
      const result = await request(`/api/workspace/file?path=${encodeURIComponent(path)}`);
      return typeof result.content === "string" ? result.content : null;
    } catch {
      return null; // unknown: the file is then treated as a draft and SAVE asks first
    }
  }

  // The files the brain wrote arrive here, through the orb, as unsaved drafts.
  // A file that is identical to the stored one is opened as it is, not as a change.
  // Returns { drafts, unchanged } (lists of paths), or false when nothing was opened.
  async function openDraftFiles(files) {
    if (!Array.isArray(files) || !files.length || files.length > 10) return false;
    if (files.some((file) => !file || typeof file.path !== "string" || typeof file.content !== "string"))
      return false;
    const stored = new Map();
    await Promise.all(
      files.map(async (file) => stored.set(file.path, await storedContent(file.path))),
    );
    // A draft Weronika wrote earlier is simply replaced by her newer one. Text the
    // user typed and has not saved is only replaced after asking, once for all files.
    const ownEdits = files
      .filter((file) => {
        const current = openFiles.get(file.path);
        return (
          current &&
          current.touched === true &&
          current.content !== current.savedContent &&
          current.content !== file.content
        );
      })
      .map((file) => file.path);
    if (
      ownEdits.length &&
      !window.confirm(
        `Weronika’s new draft would replace your own unsaved edits in:\n\n${ownEdits.join("\n")}\n\nReplace them?`,
      )
    )
      return false;
    const drafts = [];
    const unchanged = [];
    for (const file of files) {
      if (stored.get(file.path) === file.content) {
        openFiles.set(file.path, {
          content: file.content,
          savedContent: file.content,
          existing: true,
        });
        unchanged.push(file.path);
        continue;
      }
      openFiles.set(file.path, {
        content: file.content,
        savedContent: "",
        existing: false,
        origin: "weronika",
      });
      drafts.push(file.path);
    }
    panel.hidden = false;
    panel.classList.remove("minimised");
    syncOpenState();
    if (!narrow()) showView("explorer");
    activateFile(drafts[0] || files[0].path);
    await refreshFiles({ quiet: true });
    const same = unchanged.length
      ? ` ${unchanged.length} returned file${unchanged.length === 1 ? " is" : "s are"} identical to the stored copy.`
      : "";
    const summary = drafts.length
      ? `Weronika drafted ${drafts.length} file${drafts.length === 1 ? "" : "s"}. Review each tab, then SAVE to write locally.${same}`
      : `Weronika returned ${unchanged.length === 1 ? "a file that is" : "files that are"} identical to the stored ${unchanged.length === 1 ? "copy" : "copies"}. Nothing to save.`;
    status(codeStatus, summary);
    logOutput(
      drafts.length
        ? `${summary} Drafts: ${drafts.join(", ")}${unchanged.length ? ` · unchanged: ${unchanged.join(", ")}` : ""}`
        : `${summary} ${unchanged.join(", ")}`,
    );
    scheduleSession();
    if (panel.classList.contains("preview-open")) void refreshPreview();
    return { drafts, unchanged };
  }

  // ---- buttons and keys -----------------------------------------------------
  $(".devtools-command").addEventListener("click", goToFile);
  $(".new-file").addEventListener("click", promptNewFile);
  $(".welcome-new").addEventListener("click", promptNewFile);
  $(".welcome-ask").addEventListener("click", () => {
    setAgentOpen(true);
    promptInput.focus({ preventScroll: true });
  });
  $(".save-file").addEventListener("click", () => void saveFile());
  $(".save-all").addEventListener("click", () => void saveAll());
  $(".devtools-drafts").addEventListener("click", () => void saveAll());
  $(".refresh-files").addEventListener("click", () => void refreshFiles());
  $(".devtools-connection").addEventListener("click", () => void refreshFiles());
  $(".download-zip").addEventListener("click", downloadWorkspaceZip);
  $(".run-file").addEventListener("click", runPython);
  $(".collapse-folders").addEventListener("click", () => {
    for (const folder of listedFolders) collapsedFolders.add(folder);
    for (const path of openFiles.keys()) {
      for (let folder = dirName(path); folder; folder = dirName(folder)) collapsedFolders.add(folder);
    }
    renderTree();
  });
  $(".clear-output").addEventListener("click", () => outputLog.replaceChildren());
  $(".close-panel").addEventListener("click", () => setPanelOpen(false));
  $(".toggle-side").addEventListener("click", () => setSideOpen(!sideOpen()));
  $(".toggle-panel").addEventListener("click", () => setPanelOpen(outputPanel.hidden));
  for (const button of $$(".toggle-agent"))
    button.addEventListener("click", () =>
      setAgentOpen(panel.classList.contains("agent-closed")),
    );
  for (const button of $$(".workspace-activity-btn[data-view]"))
    button.addEventListener("click", () => showView(button.dataset.view, true));
  for (const toggle of $$(".workspace-section-toggle"))
    toggle.addEventListener("click", () => {
      const collapsed = toggle.closest(".workspace-section").classList.toggle("collapsed");
      toggle.setAttribute("aria-expanded", String(!collapsed));
    });
  $(".devtools-top").addEventListener("dblclick", (event) => {
    // Not the double click that has just unfolded the minimised Workspace.
    if (event.target === event.currentTarget && performance.now() - unfoldedAt > 700)
      $(".devtools-light.max").click();
  });
  // The Explorer lies over the editor on a narrow screen: fold it away when the window
  // becomes narrow, and bring it back when there is room beside the editor again.
  if (window.matchMedia) {
    const narrowQuery = window.matchMedia("(max-width: 820px)");
    const onNarrowChange = (event) => setSideOpen(!event.matches);
    if (narrowQuery.addEventListener) narrowQuery.addEventListener("change", onNarrowChange);
    else if (narrowQuery.addListener) narrowQuery.addListener(onNarrowChange);
  }
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(() => {
      revealActiveTab();
      syncScroll();
    }).observe(editorTabs);
  }
  // A vertical wheel moves along the tab strip.
  editorTabs.addEventListener(
    "wheel",
    (event) => {
      if (!event.deltaY || event.deltaX || editorTabs.scrollWidth <= editorTabs.clientWidth) return;
      editorTabs.scrollLeft += event.deltaY;
      event.preventDefault();
    },
    { passive: false },
  );

  function handleShortcut(event) {
    if (event.defaultPrevented || event.isComposing) return;
    if (event.key === "Escape") {
      const closedQuick = closeQuick();
      const closedMenu = closeMenus();
      if (closedQuick || closedMenu) {
        event.preventDefault();
        focusEditor();
      }
      return;
    }
    if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
    const key = event.key.toLowerCase();
    let action = null;
    if (key === "s") action = event.shiftKey ? saveAll : saveFile;
    else if (key === "p" && !event.shiftKey) action = goToFile;
    else if (key === "b" && !event.shiftKey) action = () => setSideOpen(!sideOpen());
    else if (key === "j" && !event.shiftKey) action = () => setPanelOpen(outputPanel.hidden);
    else if (key === "e" && event.shiftKey) action = () => showView("explorer");
    else if (key === "f" && event.shiftKey) action = () => showView("search");
    if (!action) return;
    event.preventDefault();
    void action();
  }
  // Keys pressed inside the Workspace belong to it: they must not reach the orb's
  // single-key shortcuts (V for voice, G for gestures, R to reset the view).
  panel.addEventListener("keydown", (event) => {
    handleShortcut(event);
    event.stopPropagation();
  });
  document.addEventListener("keydown", (event) => {
    if (panel.hidden || panel.classList.contains("minimised")) return;
    if (event.target instanceof Node && panel.contains(event.target)) return;
    handleShortcut(event);
  });
  window.addEventListener("pagehide", () => {
    if (!sessionTimer) return;
    clearTimeout(sessionTimer);
    persistSession();
  });

  showChatWelcome();
  setSideOpen(!narrow());
  showNoFile();
  restoreSession();

  return {
    open,
    close: closeWorkspace,
    getWorkspaceContext,
    openDraftFiles,
    openDraftFile(path, content) {
      return openDraftFiles([{ path, content }]);
    },
    refreshFiles,
    showConversation,
  };
}
