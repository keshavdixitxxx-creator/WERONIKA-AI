const WORKSPACE_STYLE = `
  .devtools-launch { position:fixed; top:62px; right:24px; z-index:21; }
  .devtools-panel { position:fixed; z-index:55; inset:5vh 5vw; display:flex; flex-direction:column; min-width:320px; color:#e8edf5; background:#10141b; border:1px solid rgba(255,170,48,.56); border-radius:12px; box-shadow:0 24px 90px #000c,0 0 35px #ff981322; font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace; overflow:hidden; }
  .devtools-panel[hidden] { display:none; }
  .devtools-top { display:flex; align-items:center; gap:12px; padding:12px 16px; background:#171d26; border-bottom:1px solid #ffffff18; }
  .devtools-brand { color:#ffbd59; font-weight:bold; letter-spacing:.12em; margin-right:auto; }
  .devtools-subtitle { color:#96a1b0; font-size:11px; }
  .devtools-close { border:1px solid #ffffff2b; border-radius:6px; color:#f1f3f6; background:#ffffff0a; padding:5px 10px; cursor:pointer; }
  .devtools-tabs { display:flex; gap:4px; padding:8px 12px 0; background:#11161e; border-bottom:1px solid #ffffff18; }
  .devtools-tab { border:0; border-bottom:2px solid transparent; color:#9ba7b8; background:transparent; padding:9px 14px; font:inherit; cursor:pointer; }
  .devtools-tab[aria-selected=true] { color:#ffc66a; border-bottom-color:#ffaa30; }
  .devtools-body { flex:1; min-height:0; display:flex; flex-direction:column; padding:12px; }
  .devtools-view { display:none; height:100%; min-height:0; }
  .devtools-view.active { display:flex; flex-direction:column; }
  .devtools-toolbar { display:flex; gap:7px; align-items:center; flex-wrap:wrap; padding-bottom:9px; }
  .devtools-toolbar input,.devtools-toolbar textarea { min-width:150px; flex:1; border:1px solid #ffffff25; background:#090d13; color:#e8edf5; border-radius:5px; padding:8px; font:inherit; }
  .devtools-btn { border:1px solid #ffad4a70; color:#ffc66a; background:#ffad4a13; border-radius:5px; padding:7px 10px; font:inherit; cursor:pointer; }
  .devtools-btn:hover { background:#ffad4a28; }
  .devtools-btn.warn { color:#ffb19b; border-color:#ff775570; }
  .devtools-status { min-height:20px; color:#9faaba; font-size:11px; }
  .devtools-status.error { color:#ff9c88; }
  .devtools-editor-layout { display:grid; grid-template-columns:minmax(150px, 245px) 1fr; gap:10px; min-height:0; flex:1; }
  .devtools-files { overflow:auto; background:#0a0e14; border:1px solid #ffffff16; border-radius:6px; padding:8px; }
  .devtools-file { display:block; width:100%; text-align:left; border:0; border-radius:4px; padding:5px 7px; color:#bfcbda; background:transparent; font:inherit; cursor:pointer; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .devtools-file:hover,.devtools-file.active { background:#ffad4a18; color:#ffd28b; }
  .devtools-editor-wrap { display:flex; min-width:0; min-height:0; background:#090d13; border:1px solid #ffffff1b; border-radius:6px; overflow:hidden; }
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
  launch.textContent = "CODE · BROWSER";
  launch.title = "Open Weronika's coding workspace and managed browser";
  document.body.append(launch);

  const panel = document.createElement("section");
  panel.className = "devtools-panel";
  panel.hidden = true;
  panel.setAttribute("aria-label", "Weronika coding workspace");
  panel.innerHTML = `
    <header class="devtools-top"><span class="devtools-brand">WERONIKA · DEVELOPER WORKSPACE</span><span class="devtools-subtitle">Local files · explicit run confirmation · managed browser</span><button class="devtools-close" type="button" aria-label="Close workspace">×</button></header>
    <nav class="devtools-tabs" aria-label="Workspace tools">
      <button class="devtools-tab" type="button" data-tab="code" aria-selected="true">CODE</button>
      <button class="devtools-tab" type="button" data-tab="browser" aria-selected="false">BROWSER</button>
    </nav>
    <div class="devtools-body">
      <section class="devtools-view active" data-view="code">
        <div class="devtools-toolbar"><input class="devtools-path" aria-label="Workspace file path" placeholder="src/main.py" autocomplete="off"><button class="devtools-btn new-file" type="button">NEW FILE</button><button class="devtools-btn save-file" type="button">SAVE</button><button class="devtools-btn run-file" type="button" hidden>RUN PYTHON</button><button class="devtools-btn refresh-files" type="button">REFRESH</button></div>
        <div class="devtools-status workspace-status" role="status">Connecting to local workspace…</div>
        <div class="devtools-editor-layout"><div class="devtools-files" aria-label="Workspace files"></div><div class="devtools-editor-wrap"><pre class="devtools-gutter" aria-hidden="true">1</pre><textarea class="devtools-editor" spellcheck="false" aria-label="Code editor" placeholder="Choose a file or ask Weronika to draft code here…"></textarea></div></div>
      </section>
      <section class="devtools-view" data-view="browser">
        <div class="devtools-toolbar"><input class="browser-addresses" aria-label="Website addresses" placeholder="localhost:5173 or https://example.com (one per line)"><button class="devtools-btn open-websites" type="button">OPEN TABS</button><button class="devtools-btn refresh-tabs" type="button">REFRESH</button></div>
        <div class="devtools-help">Opens pages in Weronika’s persistent Chromium browser profile. Localhost URLs remain on this computer.</div>
        <div class="devtools-status browser-status" role="status">Browser is ready when the local worker is running.</div>
        <div class="devtools-browser-list" aria-label="Open browser tabs"></div>
      </section>
    </div>`;
  document.body.append(panel);

  const $ = (selector) => panel.querySelector(selector);
  const editor = $(".devtools-editor");
  const pathInput = $(".devtools-path");
  const fileList = $(".devtools-files");
  const codeStatus = $(".workspace-status");
  const browserStatus = $(".browser-status");
  const tabList = $(".devtools-browser-list");
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
  function setEditorFile(path, content, existing) {
    pathInput.value = path;
    editor.value = content;
    savedContent = content;
    loadedExisting = existing;
    $(".run-file").hidden = !path.toLowerCase().endsWith(".py");
    updateGutter();
  }
  function updateGutter() {
    const lines = Math.max(1, editor.value.split("\n").length);
    $(".devtools-gutter").textContent = Array.from({ length: lines }, (_, i) => String(i + 1)).join(
      "\n",
    );
    $(".devtools-gutter").scrollTop = editor.scrollTop;
  }
  editor.addEventListener("input", updateGutter);
  editor.addEventListener("scroll", updateGutter);

  function renderTree(items, depth = 0) {
    for (const item of items || []) {
      if (item.kind === "directory") {
        const folder = document.createElement("div");
        folder.className = "devtools-file";
        folder.style.paddingLeft = `${7 + depth * 12}px`;
        folder.textContent = `▾ ${item.name}`;
        folder.setAttribute("aria-label", `${item.name} folder`);
        fileList.append(folder);
        renderTree(item.children, depth + 1);
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `devtools-file${item.path === pathInput.value ? " active" : ""}`;
        button.style.paddingLeft = `${7 + depth * 12}px`;
        button.textContent = `▤ ${item.name}`;
        button.title = `${item.path} (${item.size} bytes)`;
        button.addEventListener("click", () => openFile(item.path));
        fileList.append(button);
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
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveFile();
    }
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
