const WORKSPACE_STYLE = `
  /* Compact VS Code / macOS layout, neon-blue. Dense rows, macOS traffic lights,
     a title bar, and a single 3-pane grid that collapses predictably. */
  .devtools-panel { position:fixed; z-index:55; inset:2.4vh 1.6vw; display:flex; flex-direction:column; min-width:320px; color:#cfe9f8; background:#061020; border:1px solid #1d5f8f; border-radius:10px; box-shadow:0 28px 80px #000d,0 0 44px #00a6ff1f,inset 0 0 0 1px #0b3a5a; font:12px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",ui-sans-serif,system-ui,sans-serif; overflow:hidden; }
  .devtools-panel[hidden] { display:none; }

  /* ---- title bar: macOS traffic lights + centred tab title ---- */
  .devtools-top { position:relative; display:flex; align-items:center; gap:9px; height:36px; padding:0 10px; background:linear-gradient(180deg,#0b2a44,#081d31); border-bottom:1px solid #12527a; }
  .devtools-lights { display:flex; gap:6px; flex:0 0 auto; }
  .devtools-light { width:11px; height:11px; border-radius:50%; border:0; padding:0; cursor:pointer; }
  .devtools-light.close { background:#ff5f57; }
  .devtools-light.min { background:#febc2e; }
  .devtools-light.max { background:#28c840; }
  .devtools-light:hover { filter:brightness(1.25); }
  .devtools-brand { display:none; }
  .devtools-subtitle { position:absolute; left:50%; transform:translateX(-50%); color:#6fa8c8; font-size:10.5px; letter-spacing:.09em; white-space:nowrap; pointer-events:none; }
  .devtools-close { margin-left:auto; border:1px solid #2b6d95; border-radius:4px; color:#a8d9f2; background:#0a2539; padding:2px 8px; cursor:pointer; font-size:14px; line-height:1.1; }
  .devtools-close:hover { background:#12456a; border-color:#48bdf0; color:#fff; }

  .devtools-body { flex:1; min-height:0; display:flex; }
  .workspace-main { flex:1; min-height:0; display:grid; grid-template-columns:224px minmax(0,1fr) 330px; }

  /* ---- explorer ---- */
  .workspace-explorer { display:flex; flex-direction:column; min-height:0; background:#071625; border-right:1px solid #103f5e; }
  .workspace-pane-heading { display:flex; align-items:center; justify-content:space-between; height:28px; padding:0 8px; color:#79c4e8; font-size:9.5px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; }
  .workspace-project-title { padding:3px 8px 6px; color:#90bdd6; font-size:10.5px; font-weight:600; letter-spacing:.04em; }
  .devtools-files { flex:1; overflow:auto; padding:0 4px 10px; }
  .devtools-file { display:block; width:100%; text-align:left; border:0; border-radius:3px; padding:3px 7px; color:#89aec4; background:transparent; font:11.5px/1.6 inherit; cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .devtools-file:hover { background:#0b2c45; color:#d8f0ff; }
  .devtools-file.active { background:#0e3a58; color:#eafaff; box-shadow:inset 2px 0 0 #38c6ff; }
  .devtools-folder { color:#9ccbe2; font-weight:600; }

  /* ---- editor ---- */
  .workspace-editor-pane { display:flex; flex-direction:column; min-width:0; min-height:0; background:#061321; }
  .devtools-toolbar { display:flex; gap:5px; align-items:center; height:30px; padding:0 7px; background:#081c2d; border-bottom:1px solid #0f3c58; }
  .devtools-toolbar input { min-width:60px; flex:1; height:21px; border:1px solid #16435f; background:#05101b; color:#cfeaf8; border-radius:3px; padding:0 6px; font:10.5px ui-monospace,SFMono-Regular,Consolas,monospace; }
  .devtools-toolbar input:focus { outline:1px solid #35c3ff; }
  .devtools-btn { border:1px solid #1e5478; color:#a9dcf3; background:#0a2236; border-radius:3px; padding:2px 7px; height:21px; font:10.5px inherit; cursor:pointer; white-space:nowrap; }
  .devtools-btn:hover { background:#124466; border-color:#42bdff; color:#fff; }
  .devtools-btn.warn { color:#ffb9a8; border-color:#a34a3f; }
  .devtools-status { height:18px; padding:0 8px; color:#6ba0bd; background:#071827; font-size:9.5px; line-height:18px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .devtools-status.error { color:#ff9c88; }
  .devtools-editor-column { display:flex; flex:1; flex-direction:column; min-width:0; min-height:0; }
  .devtools-editor-tabs { display:flex; height:29px; overflow-x:auto; background:#071a29; border-bottom:1px solid #0f3c58; scrollbar-width:thin; }
  .devtools-file-tab { display:flex; align-items:center; gap:8px; flex:0 0 auto; padding:0 9px; color:#84a9bf; background:#081d2e; border-right:1px solid #0f3c58; border-top:1px solid transparent; font-size:10.5px; cursor:pointer; }
  .devtools-file-tab.active { color:#e8faff; background:#061321; border-top-color:#38c6ff; }
  .devtools-tab-name { color:inherit; border:0; background:transparent; font:inherit; cursor:pointer; }
  .devtools-tab-close { color:#6b94ab; border:0; background:transparent; cursor:pointer; font:inherit; }
  .devtools-tab-close:hover { color:#fff; }
  .devtools-editor-wrap { display:flex; flex:1; min-width:0; min-height:0; background:#061321; overflow:hidden; }
  .devtools-gutter { flex:0 0 auto; width:42px; overflow:hidden; padding:8px 6px; color:#3d6076; text-align:right; white-space:pre; line-height:1.6; user-select:none; font:11.5px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace; }
  .devtools-editor { flex:1; min-width:0; min-height:0; resize:none; border:0; outline:0; padding:8px 10px; color:#c2e4f5; background:transparent; caret-color:#42d0ff; font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace; tab-size:2; white-space:pre; overflow:auto; }

  /* ---- agent pane ---- */
  .workspace-agent-pane { display:flex; flex-direction:column; min-width:0; min-height:0; background:#071625; border-left:1px solid #103f5e; }
  .workspace-agent-head { display:flex; align-items:center; gap:7px; height:30px; padding:0 10px; border-bottom:1px solid #0f3c58; color:#d6f2ff; font-size:10.5px; font-weight:700; letter-spacing:.09em; }
  .workspace-agent-dot { width:6px; height:6px; border-radius:50%; background:#35d3ff; box-shadow:0 0 7px #35caffcc; }
  .workspace-chat-messages { flex:1; min-height:0; overflow:auto; padding:9px 9px; display:flex; flex-direction:column; gap:7px; }
  .workspace-chat-message { padding:6px 8px; border-radius:5px; white-space:pre-wrap; overflow-wrap:anywhere; color:#b7d5e6; background:#0a2437; border:1px solid #123f5c; font-size:11px; line-height:1.5; }
  .workspace-chat-message.user { color:#e8f9ff; background:#0b3450; box-shadow:inset 2px 0 0 #34c5ff; }
  .workspace-chat-message.assistant { box-shadow:inset 2px 0 0 #2b9cd8; }
  .workspace-chat-message.system { color:#6b95ad; background:transparent; border:0; padding:1px 3px; font-size:9.5px; }
  .workspace-chat-welcome { color:#7ba4bb; padding:2px 3px; font-size:10.5px; line-height:1.55; }
  .workspace-chat-composer { padding:8px; border-top:1px solid #0f3c58; background:#071827; }
  .workspace-prompt { width:100%; min-height:62px; max-height:150px; resize:vertical; padding:7px 8px; border:1px solid #17425e; border-radius:5px; color:#d8f3ff; background:#05101b; font:11.5px/1.45 inherit; outline:none; }
  .workspace-prompt:focus { border-color:#35c5ff; box-shadow:0 0 0 1px #149bd655; }
  .workspace-composer-footer { display:flex; align-items:center; justify-content:space-between; gap:8px; padding-top:6px; }
  .workspace-chat-hint { color:#5f869c; font-size:9px; }
  .workspace-build { color:#f2fcff; border-color:#2f9fd4; background:#086b99; }
  .workspace-build:hover { background:#0b86bd; }
  .workspace-build:disabled { opacity:.55; cursor:wait; }

  /* ---- status bar ---- */
  .workspace-statusbar { display:flex; gap:12px; align-items:center; height:20px; padding:0 10px; color:#cbeaff; background:#0a3d5e; border-top:1px solid #18658f; font-size:9.5px; }
  .workspace-statusbar span:last-child { margin-left:auto; }

  /* ---- preview pane (toggled) ---- */
  .workspace-preview-pane { display:none; flex-direction:column; min-width:0; min-height:0; border-left:1px solid #103f5e; background:#05101b; }
  .devtools-panel.preview-open .workspace-preview-pane { display:flex; }
  .devtools-panel.preview-open .workspace-main { grid-template-columns:224px minmax(0,1fr) minmax(0,1fr) 300px; }
  .workspace-preview-head { display:flex; align-items:center; gap:8px; height:30px; padding:0 9px; border-bottom:1px solid #0f3c58; color:#8fc9e6; font-size:9.5px; letter-spacing:.09em; }
  .workspace-preview-head .devtools-btn { margin-left:auto; }
  .workspace-preview-frame { flex:1; min-height:0; width:100%; border:0; background:#fff; }

  @media(max-width:1100px) { .workspace-main { grid-template-columns:200px minmax(0,1fr) 290px; } .devtools-panel.preview-open .workspace-main { grid-template-columns:200px minmax(0,1fr) minmax(0,1fr) 260px; } }
  @media(max-width:820px) {
    .devtools-panel { inset:1vh 1vw; }
    .workspace-main { grid-template-columns:160px minmax(0,1fr); grid-template-rows:minmax(0,1fr) 230px; }
    .workspace-explorer { grid-row:1 / 3; }
    .workspace-editor-pane { grid-column:2; grid-row:1; }
    .workspace-agent-pane { grid-column:2; grid-row:2; border-left:0; border-top:1px solid #103f5e; }
    .workspace-preview-pane { display:none !important; }
    .devtools-subtitle { display:none; }
  }
  @media(max-width:520px) { .workspace-main { grid-template-columns:118px minmax(0,1fr); } .devtools-toolbar .run-file { display:none; } .workspace-statusbar { gap:6px; } }
  @media(prefers-reduced-motion:reduce) { .devtools-btn,.devtools-close { transition:none; } }
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

export function mountDeveloperTools({ onPrompt = null } = {}) {
  document.querySelectorAll(".devtools-launch").forEach((button) => button.remove());
  const style = document.createElement("style");
  style.textContent = WORKSPACE_STYLE;
  document.head.append(style);
  const launch = document.getElementById("workspaceOpenBtn");
  const panel = document.createElement("section");
  panel.className = "devtools-panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", "Weronika Workspace");
  panel.innerHTML = `
    <header class="devtools-top">
      <span class="devtools-lights"><button class="devtools-light close" type="button" aria-label="Close Workspace"></button><button class="devtools-light min" type="button" aria-label="Minimise Workspace"></button><button class="devtools-light max" type="button" aria-label="Expand Workspace"></button></span>
      <span class="devtools-subtitle">weronika-workspace — WERONIKA AI</span>
      <button class="devtools-close" type="button" aria-label="Close Workspace">×</button>
    </header>
    <div class="devtools-body">
      <div class="workspace-main">
        <aside class="workspace-explorer" aria-label="Project Explorer">
          <div class="workspace-pane-heading"><span>EXPLORER</span><button class="devtools-btn download-zip" type="button" title="Download project as ZIP">ZIP ↓</button></div>
          <div class="workspace-project-title">⌄ WERONIKA WORKSPACE</div>
          <div class="devtools-files" aria-label="Workspace files"></div>
        </aside>
        <section class="workspace-editor-pane" aria-label="Code editor">
          <div class="devtools-toolbar"><input class="devtools-path" aria-label="Workspace file path" placeholder="src / main.py" autocomplete="off"><button class="devtools-btn new-file" type="button">＋ FILE</button><button class="devtools-btn save-file" type="button">SAVE</button><button class="devtools-btn run-file" type="button" hidden>RUN PYTHON</button><button class="devtools-btn refresh-files" type="button" title="Refresh workspace files">⟳</button><button class="devtools-btn preview-toggle" type="button" aria-pressed="false" title="Show the live preview">PREVIEW</button></div>
          <div class="devtools-status workspace-status" role="status">Connecting to local workspace…</div>
          <div class="devtools-editor-column"><div class="devtools-editor-tabs" role="tablist" aria-label="Open files"></div><div class="devtools-editor-wrap"><pre class="devtools-gutter" aria-hidden="true">1</pre><textarea class="devtools-editor" spellcheck="false" aria-label="Code editor" placeholder="Open a file or ask Weronika to create one…"></textarea></div></div>
        </section>
        <section class="workspace-preview-pane" aria-label="Live preview">
          <div class="workspace-preview-head"><span>PREVIEW</span><button class="devtools-btn preview-refresh" type="button" title="Reload preview">⟳</button></div>
          <iframe class="workspace-preview-frame" title="Project preview" sandbox="allow-scripts allow-forms allow-modals"></iframe>
        </section>
        <aside class="workspace-agent-pane" aria-label="Chat with Weronika">
          <header class="workspace-agent-head"><span class="workspace-agent-dot"></span><span>WERONIKA</span><span style="margin-left:auto;color:#70a8c3;font-size:10px;font-weight:400">AGENT</span></header>
          <div class="workspace-chat-messages" role="log" aria-live="polite"><div class="workspace-chat-welcome">Describe what you want to build, change, or debug. Weronika can draft and revise files across common programming languages. Generated changes open as editable drafts.</div></div>
          <div class="devtools-status workspace-build-status" role="status">Ready · prompts are sent to Weronika’s cloud brain. Open-file context is included; review files before sending.</div>
          <div class="workspace-chat-composer"><textarea class="workspace-prompt" rows="3" maxlength="5000" aria-label="Message Weronika about this project" placeholder="Ask Weronika to build or edit this project…"></textarea><div class="workspace-composer-footer"><span class="workspace-chat-hint">Enter to send · Shift+Enter for a new line</span><button class="devtools-btn workspace-build" type="button">↑ Send</button></div></div>
        </aside>
      </div>
    </div>
    <footer class="workspace-statusbar"><span class="devtools-connection">● LOCAL WORKSPACE</span><span class="devtools-line-count">Ln 1, Col 1</span><span class="devtools-language">Plain Text</span><span>UTF-8</span><span>Spaces: 2</span></footer>`;
  document.body.append(panel);

  const $ = (selector) => panel.querySelector(selector);
  const editor = $(".devtools-editor");
  const pathInput = $(".devtools-path");
  const fileList = $(".devtools-files");
  const editorTabs = $(".devtools-editor-tabs");
  const codeStatus = $(".workspace-status");
  const buildStatus = $(".workspace-build-status");
  const chatMessages = $(".workspace-chat-messages");
  const promptInput = $(".workspace-prompt");
  const buildButton = $(".workspace-build");
  const openFiles = new Map();
  let activePath = "";
  let savedContent = "";
  let loadedExisting = false;
  let workspaceRoot = "";
  let browserStorageMode = false;
  let previewFiles = [];
  let previewUrl = "";
  const browserWorkspaceKey = "weronika.workspace.files.v1";
  const supportedFilePath =
    /^(?!\/)(?!.*(?:^|\/)(?:\.|\.\.|__proto__|constructor|prototype)(?:\/|$))[^\\\u0000-\u001f]{1,200}\.(?:py|js|mjs|cjs|jsx|ts|tsx|vue|svelte|html|css|scss|json|md|txt|toml|yaml|yml|java|kt|kts|cs|c|h|cpp|hpp|go|rs|rb|php|sql|sh|bash|swift|dart|lua|r|scala|xml|graphql|proto|ex|exs|pl|ps1|bat)$/i;

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

  function browserWorkspaceTree(files) {
    const root = [];
    for (const [path, content] of Object.entries(files)) {
      const parts = path.split("/");
      let items = root;
      for (let index = 0; index < parts.length - 1; index += 1) {
        const name = parts[index];
        let folder = items.find((item) => item.kind === "directory" && item.name === name);
        if (!folder) {
          folder = { kind: "directory", name, children: [] };
          items.push(folder);
        }
        items = folder.children;
      }
      const name = parts.at(-1);
      items.push({
        kind: "file",
        name,
        path,
        size: new Blob([content]).size,
      });
    }
    return root;
  }

  function appendWorkspaceMessage(role, message) {
    const bubble = document.createElement("div");
    bubble.className = `workspace-chat-message ${role}`;
    bubble.textContent = String(message || "");
    chatMessages.append(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
  }

  function status(element, message, error = false) {
    element.textContent = message;
    element.classList.toggle("error", error);
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
  function rememberActiveFile() {
    if (!activePath) return;
    const state = openFiles.get(activePath);
    if (state) state.content = editor.value;
  }
  function getWorkspaceContext() {
    rememberActiveFile();
    const files = [];
    let total = 0;
    for (const [path, state] of openFiles) {
      if (
        /(?:^|\/)(?:\.env(?:\.[^/]*)?|secrets?(?:\.[^/]*)?|credentials?(?:\.[^/]*)?)(?:\/|$)/i.test(
          path,
        )
      )
        continue;
      const content = String(state.content || "");
      if (total + content.length > 24000) break;
      files.push({ path, content });
      total += content.length;
      if (files.length >= 8) break;
    }
    return files;
  }
  function renderEditorTabs() {
    editorTabs.replaceChildren();
    for (const [path, state] of openFiles) {
      const tab = document.createElement("div");
      tab.className = `devtools-file-tab${path === activePath ? " active" : ""}`;
      const select = document.createElement("button");
      select.type = "button";
      select.className = "devtools-tab-name";
      select.setAttribute("role", "tab");
      select.setAttribute("aria-selected", String(path === activePath));
      select.textContent = `${state.content !== state.savedContent ? "● " : ""}${path.split("/").at(-1)}`;
      select.title = path;
      select.addEventListener("click", () => activateFile(path, state));
      const close = document.createElement("button");
      close.type = "button";
      close.className = "devtools-tab-close";
      close.textContent = "×";
      close.setAttribute("aria-label", `Close ${path}`);
      close.addEventListener("click", (event) => {
        event.stopPropagation();
        closeFileTab(path);
      });
      tab.append(select, close);
      editorTabs.append(tab);
    }
  }
  function activateFile(path, state) {
    if (activePath !== path) rememberActiveFile();
    activePath = path;
    pathInput.value = path;
    editor.value = state.content;
    savedContent = state.savedContent;
    loadedExisting = state.existing;
    $(".run-file").hidden = browserStorageMode || !path.toLowerCase().endsWith(".py");
    renderEditorTabs();
    updateGutter();
  }
  function setEditorFile(path, content, existing) {
    rememberActiveFile();
    if (!path) {
      activePath = "";
      pathInput.value = "";
      editor.value = content;
      savedContent = "";
      loadedExisting = false;
      $(".run-file").hidden = true;
      renderEditorTabs();
      updateGutter();
      return;
    }
    const state = {
      content,
      savedContent: existing ? content : "",
      existing,
    };
    openFiles.set(path, state);
    activateFile(path, state);
  }
  function closeFileTab(path) {
    const state = openFiles.get(path);
    if (
      state?.content !== state?.savedContent &&
      !window.confirm(`Discard unsaved changes in ${path}?`)
    )
      return;
    openFiles.delete(path);
    if (activePath === path) {
      const next = openFiles.entries().next().value;
      if (next) activateFile(next[0], next[1]);
      else setEditorFile("", "", false);
    } else {
      renderEditorTabs();
    }
  }
  function updateGutter() {
    const lines = Math.max(1, editor.value.split("\n").length);
    $(".devtools-gutter").textContent = Array.from({ length: lines }, (_, i) => String(i + 1)).join(
      "\n",
    );
    $(".devtools-gutter").scrollTop = editor.scrollTop;
    const lineCount = $(".devtools-line-count");
    if (lineCount) {
      const beforeCaret = editor.value.slice(0, editor.selectionStart);
      const currentLine = beforeCaret.split("\n").length;
      const currentColumn = beforeCaret.length - beforeCaret.lastIndexOf("\n");
      lineCount.textContent = `Ln ${currentLine}, Col ${currentColumn}`;
    }
    const language = $(".devtools-language");
    if (language) {
      const extension = activePath.split(".").pop()?.toLowerCase();
      const names = {
        py: "Python",
        js: "JavaScript",
        mjs: "JavaScript",
        jsx: "React JSX",
        ts: "TypeScript",
        tsx: "React TSX",
        html: "HTML",
        css: "CSS",
        scss: "SCSS",
        json: "JSON",
        md: "Markdown",
        java: "Java",
        kt: "Kotlin",
        cs: "C#",
        c: "C",
        cpp: "C++",
        h: "C Header",
        hpp: "C++ Header",
        go: "Go",
        rs: "Rust",
        rb: "Ruby",
        php: "PHP",
        sql: "SQL",
        sh: "Shell",
        swift: "Swift",
        dart: "Dart",
        vue: "Vue",
        svelte: "Svelte",
        xml: "XML",
        yaml: "YAML",
      };
      language.textContent = names[extension] || "Plain Text";
    }
  }
  editor.addEventListener("input", () => {
    if (activePath && openFiles.has(activePath)) openFiles.get(activePath).content = editor.value;
    updateGutter();
    renderEditorTabs();
  });
  editor.addEventListener("scroll", updateGutter);
  pathInput.addEventListener("input", () => {
    if (activePath && pathInput.value.trim() !== activePath) {
      rememberActiveFile();
      activePath = "";
      savedContent = "";
      loadedExisting = false;
      $(".run-file").hidden = true;
      renderEditorTabs();
      updateGutter();
    }
  });

  function renderTree(items, depth = 0, target = fileList) {
    for (const item of items || []) {
      if (item.kind === "directory") {
        const folder = document.createElement("div");
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "devtools-file devtools-folder";
        toggle.style.paddingLeft = `${7 + depth * 12}px`;
        toggle.textContent = `▾ ${item.name}`;
        toggle.setAttribute("aria-label", `${item.name} folder`);
        const children = document.createElement("div");
        children.className = "devtools-folder-children";
        renderTree(item.children, depth + 1, children);
        toggle.addEventListener("click", () => {
          const collapsed = children.hidden;
          children.hidden = !collapsed;
          toggle.textContent = `${collapsed ? "▾" : "▸"} ${item.name}`;
        });
        folder.append(toggle, children);
        target.append(folder);
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `devtools-file${item.path === pathInput.value ? " active" : ""}`;
        button.style.paddingLeft = `${7 + depth * 12}px`;
        button.textContent = `▤ ${item.name}`;
        button.title = `${item.path} (${item.size} bytes)`;
        button.addEventListener("click", () => openFile(item.path));
        target.append(button);
      }
    }
  }
  async function refreshFiles() {
    try {
      const result = await request("/api/workspace/files");
      workspaceRoot = result.root || "";
      fileList.replaceChildren();
      renderTree(result.items);
      browserStorageMode = false;
      if (activePath && openFiles.has(activePath))
        activateFile(activePath, openFiles.get(activePath));
      $(".devtools-connection").textContent = "● LOCAL WORKSPACE";
      status(
        codeStatus,
        workspaceRoot ? `LOCAL WORKSPACE · ${workspaceRoot}` : "Local workspace connected.",
      );
    } catch (error) {
      if (!error.localApiUnavailable) {
        status(codeStatus, error.message, true);
        return;
      }
      browserStorageMode = true;
      workspaceRoot = "Browser storage · this browser only";
      const files = readBrowserWorkspace();
      fileList.replaceChildren();
      renderTree(browserWorkspaceTree(files));
      $(".devtools-connection").textContent = "● BROWSER STORAGE";
      $(".run-file").hidden = true;
      status(codeStatus, `${workspaceRoot} · Python execution requires weronika-py/start.bat.`);
    }
  }
  async function openFile(path) {
    try {
      const cached = openFiles.get(path);
      if (cached) {
        activateFile(path, cached);
        status(
          codeStatus,
          `Opened ${path}${cached.content !== cached.savedContent ? " · unsaved changes" : ""}`,
        );
        return;
      }
      if (browserStorageMode) {
        const content = readBrowserWorkspace()[path];
        if (typeof content !== "string")
          throw new Error(`Could not find ${path} in browser storage.`);
        setEditorFile(path, content, true);
        status(codeStatus, `Opened ${path} · ${new Blob([content]).size} bytes · browser storage`);
        return;
      }
      const result = await request(`/api/workspace/file?path=${encodeURIComponent(path)}`);
      setEditorFile(result.path, result.content, true);
      status(codeStatus, `Opened ${result.path} · ${result.size} bytes`);
      await refreshFiles();
    } catch (error) {
      status(codeStatus, error.message, true);
    }
  }
  async function saveFile() {
    const path = pathInput.value.trim();
    if (!path) {
      status(codeStatus, "Enter a relative file name first.", true);
      pathInput.focus();
      return;
    }
    const content = editor.value;
    try {
      if (browserStorageMode) {
        if (!supportedFilePath.test(path))
          throw new Error("Use a safe relative path with a supported code or text extension.");
        const files = readBrowserWorkspace();
        if (
          Object.hasOwn(files, path) &&
          !loadedExisting &&
          !window.confirm(`“${path}” already exists in browser storage. Overwrite it?`)
        )
          return;
        files[path] = content;
        localStorage.setItem(browserWorkspaceKey, JSON.stringify(files));
        setEditorFile(path, content, true);
        await refreshFiles();
        status(
          codeStatus,
          `Saved ${path} in this browser only · Python run requires the local worker.`,
        );
        return;
      }
      let result;
      try {
        result = await post("/api/workspace/file", { path, content, overwrite: loadedExisting });
      } catch (error) {
        if (
          !/already exists/i.test(error.message) ||
          !window.confirm(`“${path}” already exists. Overwrite it with the editor contents?`)
        )
          throw error;
        result = await post("/api/workspace/file", { path, content, overwrite: true });
      }
      setEditorFile(result.path, content, true);
      status(codeStatus, `Saved ${result.path} · ${result.size} bytes`);
      await refreshFiles();
    } catch (error) {
      status(codeStatus, error.message, true);
    }
  }
  async function collectWorkspaceFiles() {
    rememberActiveFile();
    let files = [];
    if (browserStorageMode) {
      files = Object.entries(readBrowserWorkspace()).map(([path, content]) => ({ path, content }));
    } else {
      try {
        const result = await request("/api/workspace/files");
        const paths = [];
        const walk = (items) => {
          for (const item of items || []) {
            if (item.kind === "directory") walk(item.children);
            else if (item.kind === "file" && supportedFilePath.test(item.path))
              paths.push(item.path);
          }
        };
        walk(result.items);
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
      status(
        codeStatus,
        error instanceof Error ? error.message : "Could not create the workspace ZIP.",
        true,
      );
    } finally {
      button.disabled = false;
    }
  }

  async function runPython() {
    const path = pathInput.value.trim();
    if (browserStorageMode) {
      status(
        codeStatus,
        "Python execution needs the local worker. Run weronika-py/start.bat on this PC.",
        true,
      );
      return;
    }
    if (!path.toLowerCase().endsWith(".py")) return;
    if (!loadedExisting || editor.value !== savedContent) {
      status(codeStatus, "Save the current Python file before running it.", true);
      return;
    }
    if (
      !window.confirm(
        `Run ${path} with the local Python interpreter? Code can access this device and your files. Continue only if you trust it.`,
      )
    )
      return;
    try {
      const result = await post("/api/workspace/run", { path, confirmed: true });
      const output =
        [result.stdout && `stdout:\n${result.stdout}`, result.stderr && `stderr:\n${result.stderr}`]
          .filter(Boolean)
          .join("\n\n") || "(no output)";
      status(
        codeStatus,
        `Exit ${result.returncode ?? "timeout"}${result.timed_out ? " · stopped after timeout" : ""}\n${output}`,
        result.returncode !== 0 || result.timed_out,
      );
    } catch (error) {
      status(codeStatus, error.message, true);
    }
  }

  function open() {
    panel.hidden = false;
    refreshFiles();
  }
  if (launch) launch.addEventListener("click", open);

  function closeWorkspace() {
    panel.hidden = true;
  }
  $(".devtools-close").addEventListener("click", closeWorkspace);
  $(".devtools-light.close").addEventListener("click", closeWorkspace);

  // macOS-style minimise: collapse to just the title bar.
  let minimised = false;
  $(".devtools-light.min").addEventListener("click", () => {
    minimised = !minimised;
    panel.style.height = minimised ? "36px" : "";
    panel.style.bottom = minimised ? "auto" : "";
  });

  // macOS-style zoom: fill the viewport, or return to the floating window.
  let maximised = false;
  $(".devtools-light.max").addEventListener("click", () => {
    maximised = !maximised;
    panel.style.inset = maximised ? "0" : "";
    panel.style.borderRadius = maximised ? "0" : "";
  });

  // ---- live preview -------------------------------------------------------
  const previewToggle = $(".preview-toggle");
  const previewFrame = $(".workspace-preview-frame");
  const previewRefresh = $(".preview-refresh");

  function previewBlobUrl(files) {
    // Render the project's own HTML in a sandboxed frame, with its CSS and JS
    // inlined, so the preview never needs a server or network access.
    const list = Array.isArray(files) ? files : [];
    const byPath = new Map(
      list.map((file) => [String(file.path || ""), String(file.content || "")]),
    );
    const entry =
      [...byPath.keys()].find((path) => /^index\.html?$/i.test(path)) ||
      [...byPath.keys()].find((path) => /\.html?$/i.test(path));
    if (!entry) return "";
    let html = byPath.get(entry) || "";
    html = html.replace(/<link[^>]+href=["']([^"']+\.css)["'][^>]*>/gi, (match, href) => {
      const css = byPath.get(href.replace(/^\.?\//, "")) || byPath.get(href);
      return css ? `<style>${css}</style>` : match;
    });
    html = html.replace(
      /<script[^>]+src=["']([^"']+\.js)["'][^>]*>\s*<\/script>/gi,
      (match, src) => {
        const js = byPath.get(src.replace(/^\.?\//, "")) || byPath.get(src);
        return js ? `<script>${js}</script>` : match;
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
      status(
        codeStatus,
        error instanceof Error ? error.message : "Could not build the preview.",
        true,
      );
    }
  }

  if (previewToggle) {
    previewToggle.addEventListener("click", () => {
      const isOpen = panel.classList.toggle("preview-open");
      previewToggle.setAttribute("aria-pressed", String(isOpen));
      if (isOpen) void refreshPreview();
    });
  }
  if (previewRefresh) {
    previewRefresh.addEventListener("click", () => void refreshPreview());
  }
  async function submitWorkspacePrompt() {
    const prompt = promptInput.value.trim();
    if (!prompt) {
      status(buildStatus, "Describe the code or project you want Weronika to build.", true);
      promptInput.focus();
      return;
    }
    if (typeof onPrompt !== "function") {
      status(buildStatus, "The cloud brain is not connected to Workspace yet.", true);
      appendWorkspaceMessage("assistant", "The cloud brain is not connected to Workspace yet.");
      return;
    }
    appendWorkspaceMessage("user", prompt);
    buildButton.disabled = true;
    status(buildStatus, "Weronika is working…");
    const pending = appendWorkspaceMessage(
      "system",
      "Planning your request and preparing file changes…",
    );
    promptInput.value = "";
    try {
      const reply = await onPrompt(prompt, getWorkspaceContext());
      pending.remove();
      const message = reply || "Draft ready. Review the editor tabs, then save the files.";
      appendWorkspaceMessage("assistant", message);
      status(buildStatus, "Finished · review the generated files before saving.");
    } catch (error) {
      pending.remove();
      const message =
        error instanceof Error ? error.message : "Weronika could not build that draft.";
      appendWorkspaceMessage("assistant", message);
      status(buildStatus, message, true);
    } finally {
      buildButton.disabled = false;
      promptInput.focus();
    }
  }
  buildButton.addEventListener("click", submitWorkspacePrompt);
  promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      submitWorkspacePrompt();
    }
  });
  $(".new-file").addEventListener("click", () => {
    if (
      editor.value !== savedContent &&
      !window.confirm("Discard the unsaved editor changes and start a new file?")
    )
      return;
    setEditorFile("", "", false);
    status(codeStatus, "Enter a relative path and draft code, then choose SAVE.");
    pathInput.focus();
  });
  $(".save-file").addEventListener("click", saveFile);
  $(".refresh-files").addEventListener("click", refreshFiles);
  $(".download-zip").addEventListener("click", downloadWorkspaceZip);
  $(".run-file").addEventListener("click", runPython);
  pathInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") editor.focus();
  });
  editor.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
      event.preventDefault();
      const start = editor.selectionStart;
      editor.setRangeText("  ", start, editor.selectionEnd, "end");
      updateGutter();
    }
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && !panel.hidden) {
      event.preventDefault();
      saveFile();
    }
  });

  async function openDraftFiles(files) {
    if (!Array.isArray(files) || !files.length || files.length > 10) return false;
    for (const file of files) {
      if (!file || typeof file.path !== "string" || typeof file.content !== "string") return false;
      const current = openFiles.get(file.path);
      if (
        current &&
        current.content !== current.savedContent &&
        !window.confirm(`Replace the unsaved draft in ${file.path}?`)
      ) {
        return false;
      }
    }
    for (const file of files) {
      openFiles.set(file.path, {
        content: file.content,
        savedContent: "",
        existing: false,
      });
    }
    const last = files[files.length - 1];
    activateFile(last.path, openFiles.get(last.path));
    panel.hidden = false;
    await refreshFiles();
    status(
      codeStatus,
      `Weronika drafted ${files.length} file${files.length === 1 ? "" : "s"}. Review each tab, then SAVE to write locally.`,
    );
    return true;
  }

  return {
    open,
    getWorkspaceContext,
    openDraftFiles,
    openDraftFile(path, content) {
      return openDraftFiles([{ path, content }]);
    },
    refreshFiles,
  };
}
