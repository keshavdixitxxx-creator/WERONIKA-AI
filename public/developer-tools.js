const WORKSPACE_STYLE = `
  .devtools-panel { position:fixed; z-index:55; inset:3vh 2vw; display:flex; flex-direction:column; min-width:320px; color:#dce6f2; background:#17191e; border:1px solid #343943; border-radius:8px; box-shadow:0 24px 90px #000d,0 0 35px #008cff24; font:13px/1.45 "Segoe UI",ui-sans-serif,system-ui,sans-serif; overflow:hidden; }
  .devtools-panel[hidden] { display:none; }
  .devtools-top { display:flex; align-items:center; gap:14px; min-height:42px; padding:6px 12px; background:#202329; border-bottom:1px solid #ffffff12; }
  .devtools-brand { color:#e3e8f0; font-size:12px; font-weight:600; letter-spacing:.04em; margin-right:auto; }
  .devtools-subtitle { color:#858d9b; font-size:11px; }
  .devtools-close { border:0; border-radius:4px; color:#ccd3df; background:transparent; padding:5px 10px; cursor:pointer; font-size:18px; }
  .devtools-close:hover { background:#ffffff13; color:#fff; }
  .devtools-body { flex:1; min-height:0; display:flex; padding:0; }
  .workspace-main { flex:1; min-height:0; display:grid; grid-template-columns:220px minmax(0,1fr) 345px; }
  .workspace-explorer { display:flex; flex-direction:column; min-height:0; background:#181a1f; border-right:1px solid #ffffff12; }
  .workspace-pane-heading { display:flex; align-items:center; justify-content:space-between; min-height:35px; padding:0 10px; color:#c5cbd5; font-size:10px; font-weight:700; letter-spacing:.1em; border-bottom:1px solid #ffffff0e; }
  .workspace-project-title { padding:9px 10px 5px; color:#bfc7d4; font-size:11px; font-weight:600; }
  .devtools-files { flex:1; overflow:auto; padding:5px 4px 12px; }
  .devtools-file { display:block; width:100%; text-align:left; border:0; border-radius:3px; padding:5px 7px; color:#aeb8c8; background:transparent; font:12px/1.4 "Segoe UI",ui-sans-serif,system-ui,sans-serif; cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .devtools-file:hover,.devtools-file.active { background:#ffffff0d; color:#fff; }
  .workspace-editor-pane { display:flex; flex-direction:column; min-width:0; min-height:0; background:#1e1f22; }
  .devtools-toolbar { display:flex; gap:6px; align-items:center; min-height:38px; flex-wrap:wrap; padding:5px 8px; background:#25272d; border-bottom:1px solid #ffffff10; }
  .devtools-toolbar input { min-width:70px; flex:1; border:1px solid transparent; background:#1b1d22; color:#e8edf5; border-radius:4px; padding:6px 8px; font:11px ui-monospace,Consolas,monospace; }
  .devtools-toolbar input:focus { outline:1px solid #388bfd; }
  .devtools-btn { border:1px solid #454a55; color:#c9d2df; background:#2b2e35; border-radius:4px; padding:5px 8px; font:11px "Segoe UI",ui-sans-serif,system-ui,sans-serif; cursor:pointer; }
  .devtools-btn:hover { background:#363b45; color:#fff; }
  .devtools-btn.warn { color:#ffb19b; border-color:#ff775570; }
  .devtools-status { min-height:19px; padding:2px 9px; color:#8e98a7; background:#1e1f22; font-size:10px; }
  .devtools-status.error { color:#ff9c88; }
  .devtools-editor-column { display:flex; flex:1; flex-direction:column; min-width:0; min-height:0; }
  .devtools-editor-tabs { display:flex; min-height:35px; overflow-x:auto; background:#25272d; border-bottom:1px solid #ffffff12; }
  .devtools-file-tab { display:flex; align-items:center; gap:11px; flex:0 0 auto; padding:5px 10px; color:#aeb8c8; background:#25272d; border-right:1px solid #ffffff0c; border-top:1px solid transparent; font-size:11px; cursor:pointer; }
  .devtools-file-tab.active { color:#f0f4fa; background:#1e1f22; border-top-color:#388bfd; }
  .devtools-tab-name { color:inherit; border:0; background:transparent; font:inherit; cursor:pointer; }
  .devtools-tab-close { color:#8994a2; border:0; background:transparent; cursor:pointer; font:inherit; }
  .devtools-tab-close:hover { color:#fff; }
  .devtools-editor-wrap { display:flex; flex:1; min-width:0; min-height:0; background:#1e1f22; overflow:hidden; }
  .devtools-gutter { flex:0 0 auto; width:48px; overflow:hidden; padding:12px 8px; color:#737985; text-align:right; white-space:pre; line-height:1.55; user-select:none; font:12px/1.55 ui-monospace,Consolas,monospace; }
  .devtools-editor { flex:1; min-width:0; min-height:0; resize:none; border:0; outline:0; padding:12px; color:#dce3ed; background:transparent; font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace; tab-size:2; white-space:pre; overflow:auto; }
  .workspace-agent-pane { display:flex; flex-direction:column; min-width:0; min-height:0; background:#191b20; border-left:1px solid #ffffff12; }
  .workspace-agent-head { display:flex; align-items:center; gap:8px; min-height:41px; padding:0 12px; border-bottom:1px solid #ffffff12; color:#e5ebf4; font-size:12px; font-weight:600; }
  .workspace-agent-dot { width:7px; height:7px; border-radius:50%; background:#3fb950; box-shadow:0 0 8px #3fb95088; }
  .workspace-chat-messages { flex:1; min-height:0; overflow:auto; padding:13px 11px; display:flex; flex-direction:column; gap:11px; }
  .workspace-chat-message { padding:9px 10px; border-radius:6px; white-space:pre-wrap; overflow-wrap:anywhere; color:#cbd4e0; background:#22252b; font-size:12px; line-height:1.5; }
  .workspace-chat-message.user { color:#e0ebfa; background:#202a39; border-left:2px solid #388bfd; }
  .workspace-chat-message.assistant { border-left:2px solid #6e7681; }
  .workspace-chat-message.system { color:#8792a0; background:transparent; padding:2px 4px; font-size:10px; }
  .workspace-chat-welcome { color:#8893a2; padding:5px 4px; font-size:11px; line-height:1.55; }
  .workspace-chat-composer { padding:10px; border-top:1px solid #ffffff12; background:#1d1f24; }
  .workspace-prompt { width:100%; min-height:86px; max-height:220px; resize:vertical; padding:10px; border:1px solid #454a55; border-radius:6px; color:#e4ebf5; background:#24272e; font:12px/1.45 "Segoe UI",ui-sans-serif,system-ui,sans-serif; outline:none; }
  .workspace-prompt:focus { border-color:#388bfd; box-shadow:0 0 0 1px #388bfd55; }
  .workspace-composer-footer { display:flex; align-items:center; justify-content:space-between; gap:8px; padding-top:8px; }
  .workspace-chat-hint { color:#7e8794; font-size:9px; }
  .workspace-build { color:#f0f6fc; border-color:#388bfd; background:#1765ad; }
  .workspace-build:hover { background:#1f78cc; }
  .workspace-build:disabled { opacity:.55; cursor:wait; }
  .workspace-statusbar { display:flex; gap:14px; align-items:center; min-height:23px; padding:3px 11px; color:#d5e8ff; background:#12689f; font-size:10px; }
  .workspace-statusbar span:last-child { margin-left:auto; }
  @media(max-width:1000px) { .workspace-main { grid-template-columns:185px minmax(0,1fr) 300px; } }
  @media(max-width:780px) { .devtools-panel { inset:1vh 1vw; } .workspace-main { grid-template-columns:160px minmax(0,1fr); grid-template-rows:minmax(0,1fr) 260px; } .workspace-explorer { grid-row:1 / 3; } .workspace-agent-pane { grid-column:2; grid-row:2; border-left:0; border-top:1px solid #ffffff12; } .workspace-editor-pane { grid-column:2; grid-row:1; } .devtools-subtitle { display:none; } }
  @media(max-width:520px) { .workspace-main { grid-template-columns:115px minmax(0,1fr); grid-template-rows:minmax(0,1fr) 240px; } .devtools-toolbar .run-file { display:none; } .devtools-brand { font-size:11px; } }
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
    <header class="devtools-top"><span class="devtools-brand">WERONIKA AI</span><span class="devtools-subtitle">WORKSPACE · CLOUD AGENT · MULTI-LANGUAGE</span><button class="devtools-close" type="button" aria-label="Close Workspace">×</button></header>
    <div class="devtools-body">
      <div class="workspace-main">
        <aside class="workspace-explorer" aria-label="Project Explorer">
          <div class="workspace-pane-heading"><span>EXPLORER</span><button class="devtools-btn download-zip" type="button" title="Download project as ZIP">ZIP ↓</button></div>
          <div class="workspace-project-title">⌄ WERONIKA WORKSPACE</div>
          <div class="devtools-files" aria-label="Workspace files"></div>
        </aside>
        <section class="workspace-editor-pane" aria-label="Code editor">
          <div class="devtools-toolbar"><input class="devtools-path" aria-label="Workspace file path" placeholder="src / main.py" autocomplete="off"><button class="devtools-btn new-file" type="button">＋ FILE</button><button class="devtools-btn save-file" type="button">SAVE</button><button class="devtools-btn run-file" type="button" hidden>RUN PYTHON</button><button class="devtools-btn refresh-files" type="button" title="Refresh workspace files">⟳</button></div>
          <div class="devtools-status workspace-status" role="status">Connecting to local workspace…</div>
          <div class="devtools-editor-column"><div class="devtools-editor-tabs" role="tablist" aria-label="Open files"></div><div class="devtools-editor-wrap"><pre class="devtools-gutter" aria-hidden="true">1</pre><textarea class="devtools-editor" spellcheck="false" aria-label="Code editor" placeholder="Open a file or ask Weronika to create one…"></textarea></div></div>
        </section>
        <aside class="workspace-agent-pane" aria-label="Chat with Weronika">
          <header class="workspace-agent-head"><span class="workspace-agent-dot"></span><span>WERONIKA</span><span style="margin-left:auto;color:#7e8794;font-size:10px;font-weight:400">AGENT</span></header>
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
    return [...byPath].map(([path, content]) => ({ path, content }));
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
  $(".devtools-close").addEventListener("click", () => {
    panel.hidden = true;
  });
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
