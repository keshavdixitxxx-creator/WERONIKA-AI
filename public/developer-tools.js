const WORKSPACE_STYLE = `
  .devtools-launch { position:fixed; top:62px; right:24px; z-index:21; }
  .devtools-panel { position:fixed; z-index:55; inset:2vh 2vw; display:flex; flex-direction:column; min-width:320px; color:#e8edf5; background:#10141b; border:1px solid rgba(255,170,48,.56); border-radius:8px; box-shadow:0 24px 90px #000c,0 0 35px #ff981322; font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace; overflow:hidden; }
  .devtools-panel[hidden] { display:none; }
  .devtools-top { display:flex; align-items:center; gap:12px; padding:10px 16px; background:#171d26; border-bottom:1px solid #ffffff18; }
  .devtools-brand { color:#ffbd59; font-weight:bold; letter-spacing:.12em; margin-right:auto; }
  .devtools-subtitle { color:#96a1b0; font-size:11px; }
  .devtools-close { border:1px solid #ffffff2b; border-radius:4px; color:#f1f3f6; background:#ffffff0a; padding:5px 10px; cursor:pointer; }
  .devtools-tabs { display:flex; gap:4px; padding:0 12px; background:#11161e; border-bottom:1px solid #ffffff18; }
  .devtools-tab { border:0; border-bottom:2px solid transparent; color:#9ba7b8; background:transparent; padding:9px 14px; font:inherit; cursor:pointer; }
  .devtools-tab[aria-selected=true] { color:#ffc66a; border-bottom-color:#ffaa30; }
  .devtools-body { flex:1; min-height:0; display:flex; flex-direction:column; padding:10px 12px 0; }
  .devtools-statusbar { display:flex; gap:18px; align-items:center; min-height:24px; padding:3px 12px; color:#18212b; background:#d99032; font-size:10px; }
  .devtools-statusbar span:last-child { margin-left:auto; }
  .devtools-view { display:none; height:100%; min-height:0; }
  .devtools-view.active { display:flex; flex-direction:column; }
  .devtools-toolbar { display:flex; gap:7px; align-items:center; flex-wrap:wrap; padding-bottom:9px; }
  .devtools-toolbar input,.devtools-toolbar textarea { min-width:150px; flex:1; border:1px solid #ffffff25; background:#090d13; color:#e8edf5; border-radius:5px; padding:8px; font:inherit; }
  .devtools-btn { border:1px solid #ffad4a70; color:#ffc66a; background:#ffad4a13; border-radius:5px; padding:7px 10px; font:inherit; cursor:pointer; }
  .devtools-btn:hover { background:#ffad4a28; }
  .devtools-btn.warn { color:#ffb19b; border-color:#ff775570; }
  .devtools-status { min-height:20px; color:#9faaba; font-size:11px; }
  .devtools-status.error { color:#ff9c88; }
  .devtools-editor-layout { display:grid; grid-template-columns:minmax(190px, 250px) 1fr; gap:10px; min-height:0; flex:1; }
  .devtools-file-pane { display:flex; flex-direction:column; min-height:0; background:#0a0e14; border-right:1px solid #ffffff16; }
  .devtools-file-heading { display:flex; justify-content:space-between; align-items:center; padding:8px 9px; color:#aeb9c7; font-size:10px; letter-spacing:.13em; border-bottom:1px solid #ffffff13; }
  .devtools-files { flex:1; overflow:auto; padding:8px 5px; }
  .devtools-file { display:block; width:100%; text-align:left; border:0; border-radius:3px; padding:5px 7px; color:#bfcbda; background:transparent; font:inherit; cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .devtools-file:hover,.devtools-file.active { background:#ffad4a18; color:#ffd28b; }
  .devtools-editor-column { display:flex; flex-direction:column; min-width:0; min-height:0; }
  .devtools-editor-tabs { display:flex; min-height:34px; overflow-x:auto; background:#0d1118; border-bottom:1px solid #ffffff1a; }
  .devtools-file-tab { display:flex; align-items:center; gap:12px; flex:0 0 auto; padding:6px 10px; color:#aeb9c7; background:#131923; border-right:1px solid #ffffff12; border-top:1px solid transparent; font:inherit; font-size:11px; cursor:pointer; }
  .devtools-file-tab.active { color:#f2d8aa; background:#090d13; border-top-color:#ffaa30; }
  .devtools-tab-name { color:inherit; border:0; background:transparent; font:inherit; cursor:pointer; }
  .devtools-tab-close { color:#8994a2; border:0; background:transparent; cursor:pointer; font:inherit; }
  .devtools-tab-close:hover { color:#fff; }
  .devtools-editor-wrap { display:flex; flex:1; min-width:0; min-height:0; background:#090d13; border:1px solid #ffffff1b; border-top:0; overflow:hidden; }
  .devtools-gutter { flex:0 0 auto; width:46px; overflow:hidden; padding:12px 8px; color:#586575; text-align:right; white-space:pre; line-height:1.5; user-select:none; }
  .devtools-editor { flex:1; min-width:0; min-height:0; resize:none; border:0; outline:0; padding:12px; color:#dbe5f0; background:transparent; font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace; tab-size:2; white-space:pre; overflow:auto; }
  .devtools-browser-list { flex:1; overflow:auto; display:flex; flex-direction:column; gap:7px; padding:4px 0; }
  .devtools-tabrow { display:flex; align-items:center; gap:9px; border:1px solid #ffffff18; background:#0b1017; border-radius:6px; padding:9px; }
  .devtools-tabrow-main { flex:1; min-width:0; overflow:hidden; cursor:pointer; }
  .devtools-tabrow-main strong,.devtools-tabrow-main span { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .devtools-tabrow-main strong { color:#ffc66a; font-weight:normal; }
  .devtools-tabrow-main span { color:#8895a6; font-size:11px; }
  .devtools-help { color:#9ba7b8; font-size:11px; padding:5px 0; }
  @media(max-width:720px) { .devtools-panel { inset:2vh 2vw; } .devtools-editor-layout { grid-template-columns:115px 1fr; } .devtools-subtitle { display:none; } .devtools-toolbar input { min-width:120px; } }
`;

export function mountDeveloperTools() {
  const style = document.createElement("style");
  style.textContent = WORKSPACE_STYLE;
  document.head.append(style);
  const launch = document.createElement("button");
  launch.type = "button";
  launch.className = "hud-btn devtools-launch";
  launch.textContent = "WORKSPACE";
  launch.title = "Open Weronika's workspace, code editor, and managed browser";
  document.body.append(launch);

  const panel = document.createElement("section");
  panel.className = "devtools-panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", "Weronika Workspace");
  panel.innerHTML = `
    <header class="devtools-top"><span class="devtools-brand">WERONIKA · WORKSPACE</span><span class="devtools-subtitle">LOCAL PROJECT · EDITOR · PYTHON RUN · BROWSER</span><button class="devtools-close" type="button" aria-label="Close Workspace">×</button></header>
    <nav class="devtools-tabs" aria-label="Workspace tools">
      <button class="devtools-tab" type="button" data-tab="code" aria-selected="true">EXPLORER</button>
      <button class="devtools-tab" type="button" data-tab="browser" aria-selected="false">BROWSER</button>
    </nav>
    <div class="devtools-body">
      <section class="devtools-view active" data-view="code">
        <div class="devtools-toolbar"><input class="devtools-path" aria-label="Workspace file path" placeholder="src / main.py" autocomplete="off"><button class="devtools-btn new-file" type="button">NEW FILE</button><button class="devtools-btn save-file" type="button">SAVE</button><button class="devtools-btn run-file" type="button" hidden>RUN PYTHON</button><button class="devtools-btn refresh-files" type="button">REFRESH</button></div>
        <div class="devtools-status workspace-status" role="status">Connecting to local workspace…</div>
        <div class="devtools-editor-layout"><aside class="devtools-file-pane"><div class="devtools-file-heading"><span>EXPLORER</span><span class="devtools-project-name">WERONIKA WORKSPACE</span></div><div class="devtools-files" aria-label="Workspace files"></div></aside><div class="devtools-editor-column"><div class="devtools-editor-tabs" role="tablist" aria-label="Open files"></div><div class="devtools-editor-wrap"><pre class="devtools-gutter" aria-hidden="true">1</pre><textarea class="devtools-editor" spellcheck="false" aria-label="Code editor" placeholder="Choose a file or ask Weronika to draft code here…"></textarea></div></div></div>
      </section>
      <section class="devtools-view" data-view="browser">
        <div class="devtools-toolbar"><input class="browser-addresses" aria-label="Website addresses" placeholder="localhost:5173 or https://example.com (one per line)"><button class="devtools-btn open-websites" type="button">OPEN TABS</button><button class="devtools-btn refresh-tabs" type="button">REFRESH</button></div>
        <div class="devtools-help">Opens pages in Weronika’s persistent Chromium browser profile. Localhost URLs remain on this computer.</div>
        <div class="devtools-status browser-status" role="status">Browser is ready when the local worker is running.</div>
        <div class="devtools-browser-list" aria-label="Open browser tabs"></div>
      </section>
    </div>
    <footer class="devtools-statusbar"><span class="devtools-connection">● LOCAL</span><span class="devtools-line-count">Ln 1, Col 1</span><span class="devtools-language">Plain Text</span><span>UTF-8</span><span>SPACES: 2</span></footer>`;
  document.body.append(panel);

  const $ = (selector) => panel.querySelector(selector);
  const editor = $(".devtools-editor");
  const pathInput = $(".devtools-path");
  const fileList = $(".devtools-files");
  const editorTabs = $(".devtools-editor-tabs");
  const codeStatus = $(".workspace-status");
  const browserStatus = $(".browser-status");
  const tabList = $(".devtools-browser-list");
  const openFiles = new Map();
  let activePath = "";
  let savedContent = "";
  let loadedExisting = false;
  let workspaceRoot = "";

  function status(element, message, error = false) {
    element.textContent = message;
    element.classList.toggle("error", error);
  }
  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(path, { cache: "no-store", ...options });
    } catch {
      throw new Error("Local workspace is offline. Start Weronika with start.bat on this device.");
    }
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || "The local workspace rejected that request.");
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
    $(".run-file").hidden = !path.toLowerCase().endsWith(".py");
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
        ts: "TypeScript",
        html: "HTML",
        css: "CSS",
        json: "JSON",
        md: "Markdown",
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
      status(
        codeStatus,
        workspaceRoot ? `LOCAL WORKSPACE · ${workspaceRoot}` : "Local workspace connected.",
      );
    } catch (error) {
      status(codeStatus, error.message, true);
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
  async function openBrowserTabs(urls) {
    const clean = urls.map((url) => url.trim()).filter(Boolean);
    if (!clean.length) {
      status(browserStatus, "Enter at least one website address.", true);
      return;
    }
    status(browserStatus, `Opening ${clean.length} browser tab${clean.length === 1 ? "" : "s"}…`);
    try {
      const result = await post("/api/workspace/browser/open", { urls: clean });
      const tabs = result.tabs || [];
      status(browserStatus, `Opened ${tabs.length} tab${tabs.length === 1 ? "" : "s"}.`);
      await refreshTabs();
      return result;
    } catch (error) {
      status(browserStatus, error.message, true);
      return null;
    }
  }
  async function refreshTabs() {
    try {
      const result = await request("/api/workspace/browser/tabs");
      tabList.replaceChildren();
      for (const tab of result.tabs || []) {
        const row = document.createElement("div");
        row.className = "devtools-tabrow";
        const main = document.createElement("div");
        main.className = "devtools-tabrow-main";
        const title = document.createElement("strong");
        title.textContent = tab.title || "Untitled page";
        const url = document.createElement("span");
        url.textContent = tab.url || "Page not navigated yet";
        main.append(title, url);
        main.addEventListener("click", async () => {
          try {
            await post("/api/workspace/browser/activate", { tab_id: tab.id });
          } catch (error) {
            status(browserStatus, error.message, true);
          }
        });
        const close = document.createElement("button");
        close.type = "button";
        close.className = "devtools-btn warn";
        close.textContent = "CLOSE";
        close.addEventListener("click", async () => {
          try {
            await post("/api/workspace/browser/close", { tab_id: tab.id });
            await refreshTabs();
          } catch (error) {
            status(browserStatus, error.message, true);
          }
        });
        row.append(main, close);
        tabList.append(row);
      }
      if (!(result.tabs || []).length)
        status(
          browserStatus,
          "No managed browser tabs yet. Open one above or ask Weronika in chat.",
        );
    } catch (error) {
      status(browserStatus, error.message, true);
    }
  }
  async function runPython() {
    const path = pathInput.value.trim();
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

  launch.addEventListener("click", () => {
    panel.hidden = false;
    refreshFiles();
    refreshTabs();
  });
  $(".devtools-close").addEventListener("click", () => {
    panel.hidden = true;
  });
  panel.querySelectorAll(".devtools-tab").forEach((button) =>
    button.addEventListener("click", () => {
      panel
        .querySelectorAll(".devtools-tab")
        .forEach((item) => item.setAttribute("aria-selected", String(item === button)));
      panel
        .querySelectorAll(".devtools-view")
        .forEach((view) =>
          view.classList.toggle("active", view.dataset.view === button.dataset.tab),
        );
      if (button.dataset.tab === "browser") refreshTabs();
    }),
  );
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
  $(".run-file").addEventListener("click", runPython);
  $(".open-websites").addEventListener("click", () =>
    openBrowserTabs($(".browser-addresses").value.split(/\n+/)),
  );
  $(".refresh-tabs").addEventListener("click", refreshTabs);
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

  return {
    open() {
      panel.hidden = false;
      refreshFiles();
      refreshTabs();
    },
    async openDraftFile(path, content) {
      panel.hidden = false;
      panel.querySelector('[data-tab="code"]').click();
      if (
        editor.value !== savedContent &&
        !window.confirm("Discard current unsaved editor changes and load Weronika’s new draft?")
      )
        return false;
      setEditorFile(path, content, false);
      await refreshFiles();
      status(
        codeStatus,
        `Weronika drafted ${path}. Review it, then choose SAVE to write it locally.`,
      );
      return true;
    },
    refreshFiles,
    refreshTabs,
    openBrowserTabs,
  };
}
