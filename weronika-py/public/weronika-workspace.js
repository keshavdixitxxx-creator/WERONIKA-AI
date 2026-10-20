import { detectLocalMediaRequest } from "./weronika-local-prompts.js";

const LEGACY_HTML_KEY = "weronika.codeWorkspace.html";
const FILES_STORAGE_KEY = "weronika.codeWorkspace.files.v1";
const FOLDERS_STORAGE_KEY = "weronika.codeWorkspace.folders.v1";
const DIRTY_FILES_STORAGE_KEY = "weronika.codeWorkspace.dirtyFiles.v1";
const CURRENT_FILE_KEY = "weronika.codeWorkspace.currentFile";
const CURRENT_FOLDER_KEY = "weronika.codeWorkspace.currentFolder";
const MAX_SOURCE_CHARS = 180_000;
const MAX_BRAIN_MESSAGE_CHARS = 7_600;
const MAX_WORKSPACE_PATH_CHARS = 240;
const MAX_WORKSPACE_PATH_DEPTH = 12;
const PREVIEW_POLICY =
  "default-src 'none'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' data:; script-src 'self' 'unsafe-inline' data:; font-src 'self' data:; media-src 'self' data: blob:; connect-src 'none'; form-action 'none'; object-src 'none'; base-uri 'self'";
const STARTER_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weronika · Live Preview</title>
  <style>
    * { box-sizing: border-box; }
    body { min-height: 100vh; margin: 0; display: grid; place-items: center; padding: 28px; background: radial-gradient(circle at 80% 15%, #dceaff, transparent 34%), linear-gradient(135deg, #f6f8ff, #e8efff); color: #18233c; font: 16px/1.5 system-ui, sans-serif; }
    main { width: min(680px, 100%); padding: clamp(28px, 7vw, 64px); border: 1px solid #dbe4f3; border-radius: 24px; background: rgba(255,255,255,.88); box-shadow: 0 28px 80px rgba(42,68,122,.15); }
    .eyebrow { color: #4169c4; font-size: 12px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
    h1 { margin: 16px 0 10px; font-size: clamp(36px, 8vw, 64px); line-height: 1.02; letter-spacing: -.05em; }
    p { max-width: 46ch; color: #586780; }
    .tip { display: inline-flex; gap: 8px; align-items: center; margin-top: 22px; padding: 10px 14px; border-radius: 999px; background: #edf3ff; color: #3155a5; font-size: 13px; font-weight: 700; }
  </style>
</head>
<body><main><div class="eyebrow">WERONIKA · LIVE PREVIEW</div><h1>Your preview is ready.</h1><p>Describe a website, app, or page above, then choose <strong>BUILD WITH WERONIKA AI</strong>. Your HTML will appear here while you edit the code.</p><div class="tip">✦ Live sandbox · changes update automatically</div></main></body>
</html>`;

const LANGUAGES = {
  html: { label: "HTML", extension: ".html", filename: "index.html" },
  css: { label: "CSS", extension: ".css", filename: "styles.css" },
  javascript: { label: "JavaScript", extension: ".js", filename: "script.js" },
  typescript: { label: "TypeScript", extension: ".ts", filename: "main.ts" },
  python: { label: "Python", extension: ".py", filename: "main.py" },
  java: { label: "Java", extension: ".java", filename: "Main.java" },
  c: { label: "C", extension: ".c", filename: "main.c" },
  cpp: { label: "C++", extension: ".cpp", filename: "main.cpp" },
  csharp: { label: "C#", extension: ".cs", filename: "main.cs" },
  go: { label: "Go", extension: ".go", filename: "main.go" },
  rust: { label: "Rust", extension: ".rs", filename: "main.rs" },
  php: { label: "PHP", extension: ".php", filename: "index.php" },
  ruby: { label: "Ruby", extension: ".rb", filename: "main.rb" },
  swift: { label: "Swift", extension: ".swift", filename: "main.swift" },
  kotlin: { label: "Kotlin", extension: ".kt", filename: "Main.kt" },
  dart: { label: "Dart", extension: ".dart", filename: "main.dart" },
  sql: { label: "SQL", extension: ".sql", filename: "query.sql" },
  bash: { label: "Bash", extension: ".sh", filename: "script.sh" },
  json: { label: "JSON", extension: ".json", filename: "data.json" },
  markdown: { label: "Markdown", extension: ".md", filename: "README.md" },
};

const ALLOWED_EXTENSIONS = new Set(
  Object.values(LANGUAGES)
    .map(({ extension }) => extension)
    .concat([
      ".htm",
      ".mjs",
      ".cjs",
      ".tsx",
      ".jsx",
      ".h",
      ".hpp",
      ".kts",
      ".txt",
      ".bat",
      ".yml",
      ".yaml",
      ".vue",
      ".svelte",
      ".r",
      ".lua",
      ".pl",
    ]),
);

const EXTENSION_LANGUAGE = {
  ".htm": "html",
  ".mjs": "javascript",
  ".cjs": "javascript",
  ".jsx": "javascript",
  ".tsx": "typescript",
  ".h": "c",
  ".hpp": "cpp",
  ".kts": "kotlin",
  ".txt": "markdown",
  ".bat": "bash",
  ".yml": "json",
  ".yaml": "json",
  ".vue": "html",
  ".svelte": "html",
  ".r": "python",
  ".lua": "python",
  ".pl": "python",
};

const LANGUAGE_HINTS = [
  ["cpp", /(?:^|[^a-z0-9])(?:c\+\+|cpp)(?:$|[^a-z0-9])/i],
  ["csharp", /(?:^|[^a-z0-9])(?:c#|c-sharp|csharp)(?:$|[^a-z0-9])/i],
  ["typescript", /\btypescript\b|\bts\b/i],
  ["javascript", /\bjavascript\b|\bjs\b|\bnode(?:\.js)?\b/i],
  ["python", /\bpython\b|\bpy\b|पाइथन|पायथन/i],
  ["java", /\bjava\b/i],
  ["go", /\bgolang\b|\b(?:in|using|language)\s+go\b|\bgo\s+(?:program|code|app|script)\b/i],
  ["rust", /\brust\b/i],
  ["php", /\bphp\b/i],
  ["ruby", /\bruby\b/i],
  ["swift", /\bswift\b/i],
  ["kotlin", /\bkotlin\b/i],
  ["dart", /\bdart\b/i],
  ["sql", /\bsql\b/i],
  ["bash", /\bbash\b|\bshell script\b/i],
  ["json", /\bjson\b/i],
  ["markdown", /\bmarkdown\b|\breadme\b/i],
  ["css", /\bcss\b/i],
  ["html", /\bhtml\b/i],
  ["c", /\b(?:language|in|using) c\b|\bc program\b|\bc code\b/i],
];

export function createCodeWorkspace({ askBrain, getDisplayName, getLanguage }) {
  const root = document.getElementById("codeWorkspace");
  const openButton = document.getElementById("codeWorkspaceBtn");
  const closeButton = document.getElementById("workspaceCloseBtn");
  const requestInput = document.getElementById("workspaceRequest");
  const buildButton = document.getElementById("workspaceBuildBtn");
  const editor = document.getElementById("workspaceEditor");
  const lineNumbers = document.getElementById("workspaceLineNumbers");
  const preview = document.getElementById("workspacePreview");
  const previewMode = document.getElementById("workspacePreviewMode");
  const status = document.getElementById("workspaceStatus");
  const mainPane = document.getElementById("workspaceMain");
  const rightPaneButton = document.getElementById("workspaceRightPaneBtn");
  const aiTabButton = document.getElementById("workspaceAITab");
  const previewTabButton = document.getElementById("workspacePreviewTab");
  const aiPanel = document.getElementById("workspaceAIPanel");
  const previewPanel = document.getElementById("workspacePreviewPanel");
  const aiChat = document.getElementById("workspaceAIChat");
  const aiForm = document.getElementById("workspaceAIForm");
  const aiInput = document.getElementById("workspaceAIInput");
  const aiAskButton = document.getElementById("workspaceAIAskBtn");
  const aiContext = document.getElementById("workspaceAIContext");
  const terminalOutput = document.getElementById("workspaceTerminalOutput");
  const terminalForm = document.getElementById("workspaceTerminalForm");
  const terminalInput = document.getElementById("workspaceTerminalInput");
  const terminalClearButton = document.getElementById("workspaceTerminalClearBtn");
  const confirmDialog = document.getElementById("workspaceConfirmDialog");
  const confirmMessage = document.getElementById("workspaceConfirmMessage");
  const confirmTitle = document.getElementById("workspaceConfirmTitle");
  const confirmAcceptButton = document.getElementById("workspaceConfirmAccept");
  const confirmCancelButton = document.getElementById("workspaceConfirmCancel");
  const runButton = document.getElementById("workspaceRunBtn");
  const saveButton = document.getElementById("workspaceSaveBtn");
  const loadButton = document.getElementById("workspaceLoadBtn");
  const testButton = document.getElementById("workspaceTestBtn");
  const vscodeButton = document.getElementById("workspaceVscodeBtn");
  const languageSelect = document.getElementById("workspaceLanguage");
  const fileSelect = document.getElementById("workspaceFileSelect");
  const explorerList = document.getElementById("workspaceExplorerList");
  const fileNameInput = document.getElementById("workspaceFileName");
  const fileLabel = document.getElementById("workspaceFileLabel");
  const languageLabel = document.getElementById("workspaceLanguageLabel");
  const activeFolderLabel = document.getElementById("workspaceActiveFolder");
  const folderNameInput = document.getElementById("workspaceFolderName");
  const newFileButton = document.getElementById("workspaceNewFileBtn");
  const newFolderButton = document.getElementById("workspaceNewFolderBtn");
  const cancelFolderRenameButton = document.getElementById("workspaceCancelFolderRenameBtn");
  const deleteButton = document.getElementById("workspaceDeleteBtn");
  const renameButton = document.getElementById("workspaceRenameBtn");
  let open = false;
  let refreshTimer = 0;
  let lastVscodeOpen = false;
  let lastLocalTest = false;
  let lastBuildWasHtml = false;
  let renameFolderSource = "";
  let confirmationResolver = null;
  let browserFiles = readBrowserFiles();
  let needsRemoteHydration = Object.keys(browserFiles).length === 0;
  let browserFolders = readBrowserFolders();
  let dirtyFiles = readDirtyFiles();
  let currentFileName = readCurrentFileName();
  let currentFolder = readCurrentFolder();
  if (currentFolder === null) currentFolder = parentDirectory(currentFileName);
  let remoteFiles = [];
  let remoteDirectories = [];
  const collapsedFolders = new Set();
  const previewLoads = new Set();

  function localAgentPath(path) {
    const route = path.startsWith("/") ? path : `/${path}`;
    return location.port === "8765" ? route : `/api/weronika-agent${route}`;
  }

  function isHindi() {
    const language = typeof getLanguage === "function" ? String(getLanguage() || "") : "";
    return /^hi(?:-|$)/i.test(language);
  }

  function isFollowupRequest(text) {
    return /^(?:please\s+)?(?:change|update|make|edit|modify|fix|add|remove|replace|style|center|colour|color|resize|move|rename)\b|^(?:कृपया\s*)?(?:इसे|इसमें|रंग|टाइटल|शीर्षक|बड़ा|छोटा|बदल|बदलो|बदलें|केंद्र|सेंटर)/i.test(
      String(text || "").trim(),
    );
  }

  function setStatus(message, isError = false) {
    if (!status) return;
    status.textContent = message;
    status.style.color = isError ? "#ff9b87" : "#9bcbe7";
  }

  function setWorkspacePanel(tab) {
    const showPreview = tab === "preview";
    if (aiPanel) aiPanel.hidden = showPreview;
    if (previewPanel) previewPanel.hidden = !showPreview;
    if (aiTabButton) aiTabButton.setAttribute("aria-selected", String(!showPreview));
    if (previewTabButton) previewTabButton.setAttribute("aria-selected", String(showPreview));
  }

  function toggleWorkspaceRightPane() {
    if (!mainPane) return;
    const hidden = mainPane.classList.toggle("workspace-ai-hidden");
    if (rightPaneButton) rightPaneButton.setAttribute("aria-pressed", String(!hidden));
    if (!hidden && aiInput) aiInput.focus();
  }

  function revealWorkspaceRightPane() {
    if (mainPane?.classList.contains("workspace-ai-hidden")) {
      mainPane.classList.remove("workspace-ai-hidden");
      if (rightPaneButton) rightPaneButton.setAttribute("aria-pressed", "true");
    }
  }

  function appendWorkspaceAIMessage(role, text) {
    if (!aiChat) return;
    const message = document.createElement("div");
    message.className = `workspace-ai-message ${role === "user" ? "user" : "assistant"}`;
    const label = document.createElement("span");
    label.className = "workspace-ai-message-label";
    label.textContent = role === "user" ? "YOU" : "WERONIKA · PROJECT ASSISTANT";
    const body = document.createElement("div");
    body.textContent = String(text || "");
    message.appendChild(label);
    message.appendChild(body);
    aiChat.appendChild(message);
    aiChat.scrollTop = aiChat.scrollHeight;
  }

  async function askWorkspaceAI() {
    const question = String(aiInput?.value || "").trim();
    if (!question || !aiInput || !aiAskButton) return;
    appendWorkspaceAIMessage("user", question);
    aiInput.value = "";
    aiInput.disabled = true;
    aiAskButton.disabled = true;
    if (aiContext)
      aiContext.textContent = `PROJECT CONTEXT · ${currentFilename() || currentFileName} · Browser workspace and connected project files`;
    const filename = currentFilename() || currentFileName;
    const fileContent =
      filename === currentFilename()
        ? String(editor?.value || "")
        : String(browserFiles[filename] || "");
    const files = [
      ...new Set([...Object.keys(browserFiles), ...remoteFiles.map((item) => item.filename)]),
    ]
      .filter((name) => safeFilename(name))
      .slice(0, 60);
    const fileSummary = files.join(", ").slice(0, 1200);
    const promptPrefix = [
      "WERONIKA PROJECT ASSISTANT. Answer the user's question; do not claim to edit or save files. For requested changes, explain a concise suggestion and direct the user to BUILD WITH WERONIKA AI to apply a code change.",
      `Answer in the user's language and preserve its script. Current file: ${filename}. Project files: ${fileSummary || "none"}.`,
      `User question: ${question}`,
      "Current file source excerpt (may be truncated):\n",
    ].join("\n\n");
    const sourceBudget = Math.max(
      0,
      Math.min(4500, MAX_BRAIN_MESSAGE_CHARS - promptPrefix.length - 100),
    );
    let sourceExcerpt = fileContent;
    if (fileContent.length > sourceBudget) {
      const marker = "\n[Middle omitted]\n";
      const excerptBudget = Math.max(0, sourceBudget - marker.length);
      const headLength = Math.ceil(excerptBudget / 2);
      const tailLength = Math.floor(excerptBudget / 2);
      sourceExcerpt = `${fileContent.slice(0, headLength)}${sourceBudget >= marker.length ? marker : ""}${tailLength > 0 ? fileContent.slice(-tailLength) : ""}`;
    }
    const prompt = `${promptPrefix}${sourceExcerpt}`;
    try {
      const reply = await askBrain(
        prompt,
        typeof getLanguage === "function" ? getLanguage() : "en-US",
      );
      if (reply && typeof reply === "object" && reply.error) {
        appendWorkspaceAIMessage(
          "assistant",
          `I couldn't reach the project brain: ${String(reply.error)}`,
        );
      } else {
        const answer =
          typeof reply === "string"
            ? reply
            : String(
                reply?.answer ||
                  reply?.text ||
                  reply?.response ||
                  "I didn't receive a readable answer. Please try again.",
              );
        appendWorkspaceAIMessage("assistant", answer);
      }
    } catch (error) {
      appendWorkspaceAIMessage(
        "assistant",
        `Project assistant request failed: ${error?.message || "brain unavailable"}`,
      );
    } finally {
      aiInput.disabled = false;
      aiAskButton.disabled = false;
      aiInput.focus();
    }
  }

  function appendTerminalLine(text, kind = "output") {
    if (!terminalOutput) return;
    const line = document.createElement("div");
    line.className = `workspace-terminal-line${kind === "command" ? " command" : kind === "error" ? " error" : ""}`;
    line.textContent = String(text || "");
    terminalOutput.appendChild(line);
    while (terminalOutput.children?.length > 120)
      terminalOutput.removeChild(terminalOutput.firstChild);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
  }

  function terminalHelp() {
    appendTerminalLine(
      "Safe commands: help, pwd, ls, cat <file>, open <file>, save, savepc, preview, test, vscode, refresh, status, clear",
    );
    appendTerminalLine(
      "This is a project console, not a shell. It cannot run arbitrary commands or control other desktop apps.",
    );
  }

  async function runProjectTerminalCommand(rawCommand) {
    const raw = String(rawCommand || "").trim();
    if (!raw) return;
    const separator = raw.search(/\s/);
    const command = (separator < 0 ? raw : raw.slice(0, separator)).toLowerCase();
    const argument =
      separator < 0
        ? ""
        : raw
            .slice(separator)
            .trim()
            .replace(
              /^(?:\"([\s\S]*)\"|'([\s\S]*)')$/,
              (_match, doubleQuoted, singleQuoted) => doubleQuoted ?? singleQuoted,
            );
    appendTerminalLine(`weronika-site > ${raw}`, "command");
    const projectNames = [
      ...new Set([...Object.keys(browserFiles), ...remoteFiles.map((item) => item.filename)]),
    ]
      .filter((name) => safeFilename(name))
      .sort((a, b) => a.localeCompare(b));
    switch (command) {
      case "help":
        terminalHelp();
        break;
      case "pwd":
        appendTerminalLine(
          `Browser project workspace · active file ${currentFilename() || currentFileName}. A local PC project is available only while the Weronika agent is connected.`,
        );
        break;
      case "ls":
        appendTerminalLine(
          projectNames.length
            ? projectNames.join("  ")
            : "No project files listed yet. Try refresh.",
        );
        if (browserFolders.size || remoteDirectories.length) {
          const folders = [...new Set([...browserFolders, ...remoteDirectories])].sort();
          if (folders.length) appendTerminalLine(`Folders: ${folders.join("  ")}`);
        }
        break;
      case "cat": {
        const filename = safeFilename(argument);
        if (!filename) {
          appendTerminalLine("Usage: cat <project-file>", "error");
          break;
        }
        let content = Object.hasOwn(browserFiles, filename) ? browserFiles[filename] : null;
        if (content === null) {
          try {
            const response = await fetch(
              `${localAgentPath("/api/workspace/source")}?name=${encodeURIComponent(filename)}`,
              { cache: "no-store" },
            );
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.ok || !data.exists || typeof data.content !== "string") {
              appendTerminalLine(
                data.error || `${filename} is not available in the project workspace.`,
                "error",
              );
              break;
            }
            content = data.content;
          } catch {
            appendTerminalLine(
              `${filename} is not in this browser workspace, and the local project agent is offline.`,
              "error",
            );
            break;
          }
        }
        const source = String(content || "");
        appendTerminalLine(
          source.length > 3200
            ? `${source.slice(0, 3200)}\n[Output truncated; open the file in the editor to view it all.]`
            : source || "(empty file)",
        );
        break;
      }
      case "open": {
        const filename = safeFilename(argument);
        if (!filename) appendTerminalLine("Usage: open <project-file>", "error");
        else if (!projectNames.includes(filename))
          appendTerminalLine(
            `${filename} is not in the listed project files. Use ls or refresh first.`,
            "error",
          );
        else await loadFile(filename);
        break;
      }
      case "save":
        if (!currentFilename())
          appendTerminalLine("Choose a supported file name before saving.", "error");
        else {
          persistCurrentFile();
          appendTerminalLine(`Saved ${currentFilename()} to this browser's project workspace.`);
        }
        break;
      case "savepc":
        await saveToPc();
        break;
      case "preview":
        renderPreview();
        setWorkspacePanel("preview");
        appendTerminalLine(
          "Refreshed the sandboxed project preview. Select the Preview tab in the right panel.",
        );
        break;
      case "test":
        await testOnLocalhost();
        break;
      case "vscode":
        await openInVSCode();
        break;
      case "refresh":
        await refreshFileList();
        appendTerminalLine(
          `Refreshed project file list (${projectNames.length} browser/agent file(s) before refresh).`,
        );
        break;
      case "status":
        appendTerminalLine(
          `Active: ${currentFilename() || currentFileName} · unsaved browser edits: ${dirtyFiles.size} · project files: ${projectNames.length} · preview: sandboxed`,
        );
        break;
      case "clear":
        terminalOutput?.replaceChildren();
        break;
      default:
        appendTerminalLine(
          `Command not available: ${command}. Type help. Arbitrary shell execution is intentionally disabled.`,
          "error",
        );
    }
  }

  function resolveConfirmation(accepted) {
    if (confirmDialog) confirmDialog.hidden = true;
    const resolve = confirmationResolver;
    confirmationResolver = null;
    if (resolve) resolve(Boolean(accepted));
  }

  function requestConfirmation(
    message,
    title = "Confirm workspace change",
    acceptLabel = "DELETE",
  ) {
    if (!confirmDialog || !confirmMessage || !confirmAcceptButton || !confirmCancelButton) {
      if (typeof window.confirm === "function") return Promise.resolve(window.confirm(message));
      return Promise.resolve(false);
    }
    if (confirmationResolver) resolveConfirmation(false);
    if (confirmTitle) confirmTitle.textContent = title;
    confirmMessage.textContent = message;
    confirmAcceptButton.textContent = acceptLabel;
    confirmDialog.hidden = false;
    return new Promise((resolve) => {
      confirmationResolver = resolve;
      confirmCancelButton.focus();
    });
  }

  function safeWorkspacePath(value, directory = false) {
    const path = String(value || "").trim();
    const parts = path.split("/");
    if (
      !path ||
      path.length > MAX_WORKSPACE_PATH_CHARS ||
      path.includes("\\") ||
      path.startsWith("/") ||
      parts.length > MAX_WORKSPACE_PATH_DEPTH ||
      parts.some((part) => !/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(part))
    )
      return "";
    if (!directory) {
      const basename = parts.at(-1);
      const extension = basename.slice(basename.lastIndexOf(".")).toLowerCase();
      if (!ALLOWED_EXTENSIONS.has(extension)) return "";
    }
    return parts.join("/");
  }

  function safeFilename(value) {
    return safeWorkspacePath(value);
  }

  function safeFolderPath(value) {
    return safeWorkspacePath(value, true);
  }

  function parentDirectory(path) {
    const safePath = safeFilename(path);
    if (!safePath || !safePath.includes("/")) return "";
    return safePath.slice(0, safePath.lastIndexOf("/"));
  }

  function joinWorkspacePath(folder, name) {
    const safeName = String(name || "").trim();
    if (!safeName) return "";
    if (safeName.includes("/")) return safeName;
    return folder ? `${folder}/${safeName}` : safeName;
  }

  function revealFolder(path) {
    let current = "";
    for (const part of String(path || "")
      .split("/")
      .filter(Boolean)) {
      current = current ? `${current}/${part}` : part;
      collapsedFolders.delete(current);
    }
  }

  function languageForFilename(filename) {
    const extension = String(filename || "")
      .slice(String(filename || "").lastIndexOf("."))
      .toLowerCase();
    if (EXTENSION_LANGUAGE[extension]) return EXTENSION_LANGUAGE[extension];
    return (
      Object.entries(LANGUAGES).find(([, item]) => item.extension === extension)?.[0] || "html"
    );
  }

  function filenameForLanguage(language) {
    return LANGUAGES[language]?.filename || LANGUAGES.html.filename;
  }

  function readBrowserFiles() {
    const files = {};
    try {
      const parsed = JSON.parse(localStorage.getItem(FILES_STORAGE_KEY) || "{}");
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        for (const [name, content] of Object.entries(parsed)) {
          const safeName = safeFilename(name);
          if (safeName && typeof content === "string")
            files[safeName] = content.slice(0, MAX_SOURCE_CHARS);
        }
      }
      const legacyHtml = localStorage.getItem(LEGACY_HTML_KEY);
      if (legacyHtml && !files["index.html"])
        files["index.html"] = legacyHtml.slice(0, MAX_SOURCE_CHARS);
    } catch {
      // Browser storage can be disabled; an in-memory editor still works.
    }
    return files;
  }

  function readBrowserFolders() {
    const folders = new Set();
    try {
      const saved = JSON.parse(localStorage.getItem(FOLDERS_STORAGE_KEY) || "[]");
      if (Array.isArray(saved)) {
        for (const value of saved) {
          const path = safeFolderPath(value);
          if (path) folders.add(path);
        }
      }
    } catch {
      // Browser storage can be disabled; folders from the PC project still appear.
    }
    return folders;
  }

  function readCurrentFileName() {
    try {
      const saved = safeFilename(localStorage.getItem(CURRENT_FILE_KEY));
      if (saved) return saved;
    } catch {
      // Ignore disabled browser storage.
    }
    return Object.keys(browserFiles)[0] || "index.html";
  }

  function readCurrentFolder() {
    try {
      const saved = localStorage.getItem(CURRENT_FOLDER_KEY);
      if (saved === null) return null;
      if (saved === "") return "";
      return safeFolderPath(saved) || null;
    } catch {
      return null;
    }
  }

  function readDirtyFiles() {
    const files = new Set();
    try {
      const saved = JSON.parse(localStorage.getItem(DIRTY_FILES_STORAGE_KEY) || "[]");
      if (Array.isArray(saved)) {
        for (const value of saved) {
          const path = safeFilename(value);
          if (path && Object.hasOwn(browserFiles, path)) files.add(path);
        }
      }
    } catch {
      // Unsaved indicators can be reconstructed after the next edit.
    }
    return files;
  }

  function persistBrowserFolders() {
    try {
      localStorage.setItem(FOLDERS_STORAGE_KEY, JSON.stringify([...browserFolders]));
    } catch {
      // Keep the active folder in memory when localStorage is unavailable.
    }
  }

  function persistDirtyFiles() {
    try {
      localStorage.setItem(DIRTY_FILES_STORAGE_KEY, JSON.stringify([...dirtyFiles]));
    } catch {
      // Keep the unsaved state in memory when localStorage is unavailable.
    }
  }

  function updateDirtyFileLabel(filename) {
    if (currentFileName === filename && fileLabel)
      fileLabel.textContent = `${filename}${dirtyFiles.has(filename) ? " •" : ""}`;
  }

  function markDirty(filename) {
    const safeName = safeFilename(filename);
    if (!safeName) return;
    dirtyFiles.add(safeName);
    persistDirtyFiles();
    updateDirtyFileLabel(safeName);
  }

  function markClean(filename) {
    dirtyFiles.delete(filename);
    persistDirtyFiles();
    updateDirtyFileLabel(filename);
  }

  function setCurrentFolder(path, persist = true) {
    currentFolder = path ? safeFolderPath(path) : "";
    if (path && !currentFolder) return false;
    if (activeFolderLabel)
      activeFolderLabel.textContent = `ACTIVE FOLDER · ${currentFolder || "/"}`;
    if (persist) {
      try {
        localStorage.setItem(CURRENT_FOLDER_KEY, currentFolder);
      } catch {
        // The active folder remains in memory when localStorage is unavailable.
      }
    }
    return true;
  }

  function persistBrowserFiles() {
    try {
      localStorage.setItem(FILES_STORAGE_KEY, JSON.stringify(browserFiles));
      localStorage.setItem(CURRENT_FILE_KEY, currentFileName);
      if (currentFileName === "index.html" && languageForFilename(currentFileName) === "html") {
        localStorage.setItem(LEGACY_HTML_KEY, browserFiles[currentFileName] || "");
      }
    } catch {
      // The active tab remains editable even if localStorage is unavailable.
    }
  }

  function currentFilename() {
    return safeFilename(fileNameInput?.value || currentFileName) || "";
  }

  function updateFileIdentity(filename) {
    const safeName = safeFilename(filename);
    if (!safeName) return false;
    currentFileName = safeName;
    if (fileNameInput) fileNameInput.value = safeName;
    if (fileLabel) fileLabel.textContent = `${safeName}${dirtyFiles.has(safeName) ? " •" : ""}`;
    setCurrentFolder(parentDirectory(safeName));
    revealFolder(parentDirectory(safeName));
    const language = languageForFilename(safeName);
    if (languageLabel)
      languageLabel.textContent = `${LANGUAGES[language]?.label || "Source"} · LOCAL FILE`;
    if (aiContext)
      aiContext.textContent = `ACTIVE FILE · ${safeName} · Weronika can inspect this browser copy and the listed project files.`;
    return true;
  }

  function populateFileSelect(files, directories) {
    if (Array.isArray(files))
      remoteFiles = files.filter((item) => item && safeFilename(item.filename));
    if (Array.isArray(directories))
      remoteDirectories = directories.map(safeFolderPath).filter(Boolean);

    const selected = currentFileName;
    const names = new Set([
      ...Object.keys(browserFiles),
      ...remoteFiles.map((item) => item.filename),
    ]);
    const sorted = [...names]
      .filter((name) => safeFilename(name))
      .sort((a, b) => a.localeCompare(b));

    if (fileSelect) {
      fileSelect.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "PROJECT FILES";
      fileSelect.appendChild(placeholder);
      for (const name of sorted) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = `${name}${dirtyFiles.has(name) ? " •" : ""}`;
        fileSelect.appendChild(option);
      }
      fileSelect.value = sorted.includes(selected) ? selected : "";
    }

    const folderPaths = new Set([...browserFolders, ...remoteDirectories]);
    const addAncestors = (path) => {
      const parts = path.split("/").filter(Boolean);
      let relative = "";
      for (const part of parts) {
        relative = relative ? `${relative}/${part}` : part;
        folderPaths.add(relative);
      }
    };
    for (const name of sorted) addAncestors(parentDirectory(name));
    for (const folder of [...folderPaths]) addAncestors(folder);
    if (currentFolder) addAncestors(currentFolder);
    if (!explorerList) return;
    explorerList.replaceChildren();
    if (!sorted.length && !folderPaths.size) {
      const empty = document.createElement("div");
      empty.className = "workspace-explorer-empty";
      empty.textContent = "No files or folders yet. Choose NEW FILE or create a folder.";
      explorerList.appendChild(empty);
      return;
    }

    const makeNode = () => ({ folders: new Map(), files: [] });
    const rootNode = makeNode();
    const ensureFolder = (path) => {
      let node = rootNode;
      let relative = "";
      for (const part of path.split("/").filter(Boolean)) {
        relative = relative ? `${relative}/${part}` : part;
        if (!node.folders.has(part)) node.folders.set(part, { ...makeNode(), path: relative });
        node = node.folders.get(part);
      }
      return node;
    };
    for (const folder of [...folderPaths].sort((a, b) => a.localeCompare(b))) ensureFolder(folder);
    for (const name of sorted) ensureFolder(parentDirectory(name)).files.push(name);

    const rootButton = document.createElement("button");
    rootButton.type = "button";
    rootButton.className = `workspace-explorer-folder workspace-explorer-root${currentFolder === "" ? " active" : ""}`;
    rootButton.setAttribute("role", "treeitem");
    rootButton.setAttribute("aria-expanded", "true");
    const rootIcon = document.createElement("span");
    rootIcon.className = "workspace-explorer-icon workspace-folder-icon";
    rootIcon.setAttribute("aria-hidden", "true");
    rootIcon.textContent = "▾";
    const rootLabel = document.createElement("span");
    rootLabel.textContent = "WERONIKA-SITE";
    rootButton.append(rootIcon, rootLabel);
    rootButton.addEventListener("click", () => {
      setCurrentFolder("");
      populateFileSelect();
    });
    explorerList.appendChild(rootButton);

    function renderChildren(node, depth = 0) {
      const folders = [...node.folders.values()].sort((a, b) => a.path.localeCompare(b.path));
      for (const folder of folders) {
        const isExpanded = !collapsedFolders.has(folder.path);
        const row = document.createElement("div");
        row.className = "workspace-explorer-folder-row";
        row.style.paddingLeft = `${10 + depth * 13}px`;
        const button = document.createElement("button");
        button.type = "button";
        button.className = `workspace-explorer-folder${currentFolder === folder.path ? " active" : ""}`;
        button.setAttribute("role", "treeitem");
        button.setAttribute("aria-expanded", isExpanded ? "true" : "false");
        button.title = folder.path;
        const arrow = document.createElement("span");
        arrow.className = "workspace-explorer-icon workspace-folder-icon";
        arrow.setAttribute("aria-hidden", "true");
        arrow.textContent = isExpanded ? "▾" : "▸";
        const label = document.createElement("span");
        label.textContent = folder.path.split("/").at(-1);
        button.append(arrow, label);
        button.addEventListener("click", () => {
          setCurrentFolder(folder.path);
          if (collapsedFolders.has(folder.path)) collapsedFolders.delete(folder.path);
          else collapsedFolders.add(folder.path);
          populateFileSelect();
        });
        row.appendChild(button);
        const rename = document.createElement("button");
        rename.type = "button";
        rename.className = "workspace-explorer-action";
        rename.title = `Rename folder ${folder.path}`;
        rename.setAttribute("aria-label", `Rename folder ${folder.path}`);
        rename.textContent = "✎";
        rename.addEventListener("click", (event) => {
          event.stopPropagation();
          beginFolderRename(folder.path);
        });
        row.appendChild(rename);

        const hasChildren =
          folder.files.length > 0 ||
          folder.folders.size > 0 ||
          sorted.some((name) => name.startsWith(`${folder.path}/`));
        if (!hasChildren) {
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "workspace-explorer-remove";
          remove.title = `Delete empty folder ${folder.path}`;
          remove.setAttribute("aria-label", `Delete empty folder ${folder.path}`);
          remove.textContent = "×";
          remove.addEventListener("click", (event) => {
            event.stopPropagation();
            deleteFolder(folder.path);
          });
          row.appendChild(remove);
        }
        explorerList.appendChild(row);
        if (isExpanded) renderChildren(folder, depth + 1);
      }
      for (const name of node.files.sort((a, b) => a.localeCompare(b))) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `workspace-explorer-file${name === selected ? " active" : ""}`;
        button.style.paddingLeft = `${23 + depth * 13}px`;
        button.setAttribute("role", "treeitem");
        button.setAttribute("aria-selected", name === selected ? "true" : "false");
        button.title = name;
        const icon = document.createElement("span");
        icon.className = "workspace-explorer-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = explorerGlyph(name);
        const label = document.createElement("span");
        label.className = "workspace-explorer-name";
        label.textContent = name.split("/").at(-1);
        button.append(icon, label);
        if (dirtyFiles.has(name)) {
          const marker = document.createElement("span");
          marker.className = "workspace-explorer-dirty";
          marker.textContent = "●";
          marker.setAttribute("aria-label", "Unsaved changes");
          button.appendChild(marker);
        }
        button.addEventListener("click", () => loadFile(name));
        explorerList.appendChild(button);
      }
    }
    renderChildren(rootNode);
  }

  function explorerGlyph(filename) {
    const extension = filename.slice(filename.lastIndexOf(".")).toLowerCase();
    return (
      {
        ".html": "◇",
        ".htm": "◇",
        ".css": "#",
        ".js": "JS",
        ".mjs": "JS",
        ".ts": "TS",
        ".tsx": "TS",
        ".py": "Py",
        ".json": "{}",
        ".md": "M",
      }[extension] || "·"
    );
  }

  function projectHasFile(filename) {
    const target = filename.toLocaleLowerCase();
    return [...Object.keys(browserFiles), ...remoteFiles.map((item) => item.filename)].some(
      (name) => name.toLocaleLowerCase() === target,
    );
  }

  function projectHasFolder(path) {
    const target = path.toLocaleLowerCase();
    const folderNames = [...browserFolders, ...remoteDirectories].map((folder) =>
      folder.toLocaleLowerCase(),
    );
    const filenames = [...Object.keys(browserFiles), ...remoteFiles.map((item) => item.filename)];
    return (
      folderNames.includes(target) ||
      folderNames.some((folder) => folder.startsWith(`${target}/`)) ||
      filenames.some((name) => {
        const parent = parentDirectory(name).toLocaleLowerCase();
        return parent === target || parent.startsWith(`${target}/`);
      })
    );
  }

  function htmlEscape(value) {
    return String(value).replace(
      /[&<>"']/g,
      (char) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char],
    );
  }

  function resolveProjectAsset(filename, reference) {
    let target = String(reference || "").trim();
    if (!target || /^(?:[a-z][a-z0-9+.-]*:|\/\/|\/|#)/i.test(target)) return "";
    target = target.split(/[?#]/, 1)[0];
    try {
      target = decodeURIComponent(target);
    } catch {
      return "";
    }
    const parts = parentDirectory(filename).split("/").filter(Boolean);
    for (const part of target.split("/")) {
      if (!part || part === ".") continue;
      if (part === "..") {
        if (!parts.length) return "";
        parts.pop();
      } else if (/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(part)) {
        parts.push(part);
      } else {
        return "";
      }
    }
    return safeFilename(parts.join("/"));
  }

  function browserAssetDataUrl(filename, reference, type) {
    const path = resolveProjectAsset(filename, reference);
    const source = path ? browserFiles[path] : "";
    if (typeof source !== "string") return "";
    const mime = type === "style" ? "text/css" : "text/javascript";
    return `data:${mime};charset=utf-8,${encodeURIComponent(source)}`;
  }

  function inlineBrowserAssets(html, filename) {
    let content = String(html || "");
    content = content.replace(/<link\b[^>]*>/gi, (tag) => {
      const rel = tag.match(/\brel\s*=\s*(["'])(.*?)\1/i)?.[2] || "";
      const hrefMatch = tag.match(/\bhref\s*=\s*(["'])(.*?)\1/i);
      if (!/stylesheet/i.test(rel) || !hrefMatch) return tag;
      const dataUrl = browserAssetDataUrl(filename, hrefMatch[2], "style");
      if (!dataUrl) return tag;
      return tag
        .replace(hrefMatch[0], `href="${dataUrl}"`)
        .replace(/\s(?:integrity|crossorigin)\s*=\s*(["']).*?\1/gi, "");
    });
    content = content.replace(
      /<script\b[^>]*\bsrc\s*=\s*(["'])(.*?)\1[^>]*>\s*<\/script\s*>/gi,
      (tag, _quote, reference) => {
        const dataUrl = browserAssetDataUrl(filename, reference, "script");
        if (!dataUrl) return tag;
        return tag
          .replace(reference, dataUrl)
          .replace(/\s(?:integrity|crossorigin)\s*=\s*(["']).*?\1/gi, "");
      },
    );
    return content;
  }

  function previewPolicyForDocument() {
    try {
      const origin = new URL(location.origin).origin;
      return PREVIEW_POLICY.replaceAll("'self'", `'self' ${origin}`);
    } catch {
      return PREVIEW_POLICY;
    }
  }

  function withPreviewPolicy(html, filename = currentFilename() || currentFileName) {
    let content = inlineBrowserAssets(html, filename).replace(/<base\b[^>]*>/gi, "");
    const csp = `<meta http-equiv="Content-Security-Policy" content="${previewPolicyForDocument()}">`;
    const directory = parentDirectory(filename);
    const encodedDirectory = directory
      .split("/")
      .filter(Boolean)
      .map((part) => encodeURIComponent(part))
      .join("/");
    const baseUrl = `${localAgentPath("/api/workspace/preview-files/")}${encodedDirectory ? `${encodedDirectory}/` : ""}`;
    const base = `<base href="${htmlEscape(baseUrl)}">`;
    if (/<head\b[^>]*>/i.test(content)) {
      content = content.replace(/<head\b[^>]*>/i, (tag) => `${tag}${csp}${base}`);
    } else if (/<html\b[^>]*>/i.test(content)) {
      content = content.replace(/<html\b[^>]*>/i, (tag) => `${tag}<head>${csp}${base}</head>`);
    } else {
      content = `<!doctype html><html><head>${csp}${base}</head><body>${content}</body></html>`;
    }
    const diagnostics = `<script>
      window.addEventListener("error", event => parent.postMessage({ source: "weronika-code-preview", type: "error", message: event.message || "Script error" }, "*"));
      window.addEventListener("unhandledrejection", event => parent.postMessage({ source: "weronika-code-preview", type: "error", message: String(event.reason || "Unhandled promise rejection") }, "*"));
    </script>`;
    if (/<\/body\s*>/i.test(content))
      return content.replace(/<\/body\s*>/i, `${diagnostics}</body>`);
    return `${content}${diagnostics}`;
  }

  function sourceViewerDocument(source, filename) {
    const language = languageForFilename(filename);
    const label = LANGUAGES[language]?.label || language.toUpperCase();
    const sourceHtml = htmlEscape(source || "");
    const safeFilename = htmlEscape(filename);
    const csp = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_POLICY}">`;
    return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">${csp}<style>
      *{box-sizing:border-box}body{margin:0;min-height:100vh;background:#f3f6fb;color:#172237;font:14px/1.5 system-ui,sans-serif}
      header{padding:14px 18px;background:#e6edf7;border-bottom:1px solid #ccd7e6;color:#263e5c;font-weight:700}
      header small{display:block;margin-top:4px;color:#64748b;font-weight:400}
      pre{margin:18px;padding:18px;overflow:auto;border:1px solid #d6dfeb;border-radius:9px;background:#fff;color:#172237;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,Consolas,monospace}
    </style></head><body><header>${safeFilename} · ${label}<small>This language is shown as source here. Use TEST ON LOCALHOST or VS Code to run it on your PC.</small></header><pre><code>${sourceHtml || "&nbsp;"}</code></pre></body></html>`;
  }

  function findProjectHtmlEntry(filename) {
    const candidates = [
      ...new Set([...Object.keys(browserFiles), ...remoteFiles.map((item) => item.filename)]),
    ].filter((name) => safeFilename(name) && languageForFilename(name) === "html");
    if (!candidates.length) return "";
    const folder = parentDirectory(filename);
    const rank = (name) => {
      if (name === filename) return 0;
      if (folder && name === `${folder}/index.html`) return 1;
      if (folder && name === `${folder}/index.htm`) return 2;
      if (folder && parentDirectory(name) === folder) return 3;
      if (name === "index.html") return 4;
      if (name === "index.htm") return 5;
      return 6;
    };
    return candidates.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))[0];
  }

  function previewMessageDocument(title, message) {
    return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:#f2f6fb;color:#31435d;font:14px/1.5 system-ui,sans-serif}main{max-width:520px;padding:24px;border:1px solid #d9e2ee;border-radius:12px;background:#fff}h1{font-size:18px}p{color:#64748b}</style></head><body><main><h1>${htmlEscape(title)}</h1><p>${htmlEscape(message)}</p></main></body></html>`;
  }

  async function loadProjectPreviewSource(filename) {
    if (previewLoads.has(filename)) return;
    previewLoads.add(filename);
    try {
      const response = await fetch(
        `${localAgentPath("/api/workspace/source")}?name=${encodeURIComponent(filename)}`,
        { cache: "no-store" },
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok || !data.exists || typeof data.content !== "string")
        throw new Error(data.error || `Local workspace returned HTTP ${response.status}.`);
      browserFiles[filename] = data.content;
      markClean(filename);
      persistBrowserFiles();
      populateFileSelect();
      renderPreview();
    } catch (error) {
      if (findProjectHtmlEntry(currentFilename() || currentFileName) === filename) {
        if (previewMode) previewMode.textContent = "PREVIEW OFFLINE";
        if (preview)
          preview.srcdoc = withPreviewPolicy(
            previewMessageDocument(
              "Project preview unavailable",
              `Could not load ${filename}: ${error?.message || "local agent unavailable"}`,
            ),
            filename,
          );
      }
    } finally {
      previewLoads.delete(filename);
    }
  }

  function syncLineNumbers() {
    if (!editor || !lineNumbers) return;
    const lineCount = Math.max(1, editor.value.split("\n").length);
    lineNumbers.textContent = Array.from({ length: lineCount }, (_, index) => index + 1).join("\n");
    lineNumbers.scrollTop = editor.scrollTop;
  }

  function renderPreview() {
    if (!editor || !preview) return;
    syncLineNumbers();
    const filename = currentFilename() || currentFileName || "index.html";
    const language = languageForFilename(filename);
    const htmlFilename = findProjectHtmlEntry(filename);
    preview.removeAttribute("src");
    if (htmlFilename) {
      const isCurrentHtml = language === "html" && filename === htmlFilename;
      if (previewMode)
        previewMode.textContent = isCurrentHtml ? "HTML SANDBOX" : `LIVE · ${htmlFilename}`;
      if (htmlFilename === filename) {
        preview.srcdoc = withPreviewPolicy(
          editor.value || "<!doctype html><html><body></body></html>",
          htmlFilename,
        );
      } else if (typeof browserFiles[htmlFilename] === "string") {
        preview.srcdoc = withPreviewPolicy(browserFiles[htmlFilename], htmlFilename);
      } else {
        if (previewMode) previewMode.textContent = "LIVE · LOADING";
        preview.srcdoc = withPreviewPolicy(
          previewMessageDocument(
            "Loading project preview",
            `Loading ${htmlFilename} from the local project…`,
          ),
          htmlFilename,
        );
        loadProjectPreviewSource(htmlFilename);
      }
      return;
    }
    if (previewMode) previewMode.textContent = `${LANGUAGES[language]?.label || "CODE"} SOURCE`;
    preview.srcdoc = sourceViewerDocument(editor.value, filename);
  }

  function persistCurrentFile(markAsDirty = true) {
    const filename = currentFilename();
    if (!filename || !editor) return false;
    updateFileIdentity(filename);
    const source = editor.value.slice(0, MAX_SOURCE_CHARS);
    const changed = browserFiles[filename] !== source;
    browserFiles[filename] = source;
    if (markAsDirty || changed) markDirty(filename);
    persistBrowserFiles();
    populateFileSelect();
    if (fileSelect) fileSelect.value = filename;
    return true;
  }

  function createStarterSource(language) {
    if (language === "html") return STARTER_HTML;
    if (language === "python")
      return 'def main():\n    print("Hello, world!")\n\nif __name__ == "__main__":\n    main()\n';
    if (language === "javascript")
      return 'function main() {\n  console.log("Hello, world!");\n}\n\nmain();\n';
    if (language === "typescript")
      return 'function main(): void {\n  console.log("Hello, world!");\n}\n\nmain();\n';
    if (language === "css") return "/* Add styles for your page here. */\n";
    if (language === "json") return '{\n  "name": "my-project"\n}\n';
    if (language === "markdown") return "# My project\n\nDescribe your project here.\n";
    return `// ${LANGUAGES[language]?.label || "Source"} file\n`;
  }

  function initialize() {
    if (!editor) return;
    if (!Object.keys(browserFiles).length) browserFiles["index.html"] = STARTER_HTML;
    if (!browserFiles[currentFileName])
      currentFileName = Object.keys(browserFiles)[0] || "index.html";
    editor.value = browserFiles[currentFileName] || STARTER_HTML;
    const startupFolder = currentFolder;
    updateFileIdentity(currentFileName);
    setCurrentFolder(startupFolder);
    persistBrowserFiles();
    populateFileSelect();
    if (fileSelect) fileSelect.value = currentFileName;
    renderPreview();
    refreshFileList();
  }

  function show() {
    if (!root) return;
    open = true;
    root.classList.add("visible");
    root.setAttribute("aria-hidden", "false");
    renderPreview();
    setTimeout(() => requestInput?.focus(), 60);
  }

  function hide() {
    if (!root) return;
    if (confirmationResolver) resolveConfirmation(false);
    open = false;
    root.classList.remove("visible");
    root.setAttribute("aria-hidden", "true");
  }

  function extractSource(answer, language) {
    let source = String(answer || "").trim();
    const fenced = source.match(/```[^\r\n]*\r?\n([\s\S]*?)```/);
    if (fenced) source = fenced[1].trim();
    if (language === "html") {
      const doctypeAt = source.toLowerCase().indexOf("<!doctype html");
      if (doctypeAt >= 0) source = source.slice(doctypeAt);
      else {
        const htmlAt = source.toLowerCase().indexOf("<html");
        if (htmlAt >= 0) source = `<!doctype html>\n${source.slice(htmlAt)}`;
        else if (!/<[a-z!/][^>]*>/i.test(source)) return "";
      }
    }
    return source.length > 0 && source.length <= MAX_SOURCE_CHARS ? source : "";
  }

  function detectLanguage(prompt, isRevision) {
    const chosen = languageSelect?.value || "auto";
    if (chosen !== "auto" && LANGUAGES[chosen]) return chosen;
    const explicitLanguageSwitch =
      /\b(?:in|using|into|as|to)\s+(?:html|css|javascript|js|typescript|ts|python|py|java|c\+\+|cpp|c#|c-sharp|csharp|go|golang|rust|php|ruby|swift|kotlin|dart|sql|bash|shell|json|markdown|c)(?=$|[^a-z0-9])/i.test(
        prompt,
      );
    if (isRevision && !explicitLanguageSwitch)
      return languageForFilename(currentFilename() || currentFileName);
    const browserArtifactRequest =
      /\b(?:website|web\s?page|webpage|site|landing page|frontend|front-end|web app|app(?:lication)?|browser game|browser-based|dashboard|portfolio|calculator|to-?do|game|quiz|timer|clock|converter|weather app|login page|signup page|form)\b|वेबसाइट|वेब\s?पेज/i.test(
        prompt,
      );
    if (browserArtifactRequest) {
      for (const [language, pattern] of LANGUAGE_HINTS) {
        if (["html", "css", "javascript", "typescript"].includes(language)) continue;
        if (pattern.test(prompt)) return language;
      }
      return "html";
    }
    for (const [language, pattern] of LANGUAGE_HINTS) {
      if (pattern.test(prompt)) return language;
    }
    if (isRevision) return languageForFilename(currentFilename() || currentFileName);
    return "python";
  }

  function requestedFilename(prompt) {
    const names =
      prompt.match(
        /(?<![A-Za-z0-9_.-])[A-Za-z0-9][A-Za-z0-9._-]*(?:\/[A-Za-z0-9][A-Za-z0-9._-]*)*\.(?:html?|css|js|mjs|cjs|ts|tsx|jsx|py|java|c|h|cpp|hpp|cs|go|rs|php|rb|swift|kt|kts|dart|r|lua|pl|sql|sh|bat|json|md|txt|ya?ml|vue|svelte)\b/gi,
      ) || [];
    return names.map(safeFilename).find(Boolean) || "";
  }

  function updateSourcePreviewStatus() {
    const filename = currentFilename() || currentFileName;
    const language = languageForFilename(filename);
    renderPreview();
    if (language === "html") {
      setStatus("HTML preview refreshed in the isolated sandbox.");
    } else {
      const htmlFilename = findProjectHtmlEntry(filename);
      setStatus(
        htmlFilename
          ? `Live project preview refreshed from ${htmlFilename}; ${LANGUAGES[language]?.label || "Source"} stays open in the editor.`
          : `${LANGUAGES[language]?.label || "Source"} selected. Add an HTML file to enable a live webpage preview.`,
      );
    }
  }

  async function saveToPc(filename = currentFilename(), content) {
    const safeName = safeFilename(filename);
    if (!safeName)
      return { ok: false, error: "Use a relative project path with a supported code extension." };
    if (!editor) return { ok: false, error: "The source editor is unavailable." };
    const source =
      typeof content === "string"
        ? content
        : safeName === currentFilename()
          ? editor.value
          : browserFiles[safeName];
    if (typeof source !== "string")
      return { ok: false, error: `No browser copy of ${safeName} is available to save.` };
    if (safeName === currentFilename()) updateFileIdentity(safeName);
    browserFiles[safeName] = source.slice(0, MAX_SOURCE_CHARS);
    markDirty(safeName);
    persistBrowserFiles();
    try {
      const response = await fetch(localAgentPath("/api/workspace/save"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: safeName, content: source }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        return {
          ok: false,
          error: data.error || `Local workspace returned HTTP ${response.status}.`,
        };
      }
      if (!remoteFiles.some((item) => item.filename === safeName))
        remoteFiles.push({ filename: safeName });
      markClean(safeName);
      populateFileSelect();
      if (fileSelect && safeName === currentFilename()) fileSelect.value = safeName;
      return { ok: true, data };
    } catch (error) {
      return { ok: false, error: error?.message || "The local agent is not reachable." };
    }
  }

  async function saveProjectToPc() {
    if (editor) persistCurrentFile(false);
    await refreshFileList();
    const folders = [...browserFolders].sort(
      (a, b) => a.split("/").length - b.split("/").length || a.localeCompare(b),
    );
    for (const folder of folders) {
      try {
        const response = await fetch(localAgentPath("/api/workspace/mkdir"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: folder }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok && !(response.status === 409 && remoteDirectories.includes(folder)))
          return {
            ok: false,
            error: data.error || `Could not create ${folder} (HTTP ${response.status}).`,
          };
      } catch (error) {
        return { ok: false, error: error?.message || "The local agent is not reachable." };
      }
    }

    let lastSaved = null;
    let currentSaved = null;
    const filenames = [...dirtyFiles]
      .filter((name) => safeFilename(name) && Object.hasOwn(browserFiles, name))
      .sort((a, b) => a.localeCompare(b));
    const selectedFilename = currentFilename();
    if (
      !filenames.length &&
      remoteFiles.length === 0 &&
      selectedFilename &&
      !remoteFiles.some((item) => item.filename === selectedFilename) &&
      typeof browserFiles[selectedFilename] === "string"
    )
      filenames.push(selectedFilename);
    for (const filename of filenames) {
      const saved = await saveToPc(filename, browserFiles[filename]);
      if (!saved.ok) return saved;
      lastSaved = saved.data;
      if (filename === currentFilename()) currentSaved = saved.data;
    }
    await refreshFileList();
    return { ok: true, data: currentSaved || lastSaved || { path: "" } };
  }

  async function refreshFileList() {
    let files = null;
    let directories = null;
    try {
      const response = await fetch(localAgentPath("/api/workspace/files"), { cache: "no-store" });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.ok && Array.isArray(data.files)) {
        files = data.files;
        directories = Array.isArray(data.directories) ? data.directories : [];
      }
    } catch {
      // Keep browser-only project files available when the local agent is offline.
    }
    populateFileSelect(files, directories);
    if (files && needsRemoteHydration) {
      needsRemoteHydration = false;
      if (
        remoteFiles.some((item) => item.filename === currentFileName) &&
        browserFiles[currentFileName] === STARTER_HTML &&
        !dirtyFiles.has(currentFileName)
      )
        await loadFile(currentFileName);
    }
    return files || remoteFiles;
  }

  async function loadFile(filename = currentFilename()) {
    const safeName = safeFilename(filename);
    if (!safeName) {
      setStatus("Choose or type a supported filename before loading.", true);
      return false;
    }
    let pcLoadNote = "The local PC agent could not be reached.";
    try {
      const response = await fetch(
        `${localAgentPath("/api/workspace/source")}?name=${encodeURIComponent(safeName)}`,
        { cache: "no-store" },
      );
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.ok && data.exists && typeof data.content === "string") {
        if (
          dirtyFiles.has(safeName) &&
          !(await requestConfirmation(
            `Discard unsaved browser changes to ${safeName} and reload from the PC?`,
            "Unsaved browser changes",
            "DISCARD CHANGES",
          ))
        )
          return false;
        updateFileIdentity(safeName);
        editor.value = data.content;
        browserFiles[safeName] = data.content;
        markClean(safeName);
        persistBrowserFiles();
        populateFileSelect();
        if (fileSelect) fileSelect.value = safeName;
        renderPreview();
        setStatus(`Loaded ${safeName} from the local project.`);
        return true;
      }
      pcLoadNote =
        data.error ||
        (data.exists === false
          ? "This file hasn't been saved to the PC yet."
          : `Local agent returned HTTP ${response.status}.`);
    } catch {
      // Fall through to the browser copy below.
    }
    if (Object.hasOwn(browserFiles, safeName)) {
      updateFileIdentity(safeName);
      editor.value = browserFiles[safeName];
      populateFileSelect();
      if (fileSelect) fileSelect.value = safeName;
      renderPreview();
      setStatus(`Loaded the browser-saved copy of ${safeName}. ${pcLoadNote}`);
      return true;
    }
    setStatus(
      `Couldn't load ${safeName}. It isn't saved in this browser, and the local agent may be offline.`,
      true,
    );
    return false;
  }

  async function createNewFile() {
    const entered = String(fileNameInput?.value || "").trim();
    const chosenLanguage = languageSelect?.value || "auto";
    const fallbackLanguage =
      chosenLanguage !== "auto" && LANGUAGES[chosenLanguage]
        ? chosenLanguage
        : languageForFilename(currentFileName);
    let filename = safeFilename(entered);
    let useDefaultName = false;

    if (
      chosenLanguage !== "auto" &&
      LANGUAGES[chosenLanguage] &&
      (!filename || languageForFilename(filename) !== chosenLanguage)
    ) {
      filename = filenameForLanguage(chosenLanguage);
      useDefaultName = true;
    } else if (!filename && !entered) {
      filename = filenameForLanguage(fallbackLanguage);
      useDefaultName = true;
    } else if (filename === currentFileName) {
      filename = filenameForLanguage(fallbackLanguage);
      useDefaultName = true;
    } else if (!filename) {
      setStatus("Use a valid relative project path, such as src/main.py or index.html.", true);
      return false;
    }

    if (!filename.includes("/")) filename = joinWorkspacePath(currentFolder, filename);
    if (!safeFilename(filename)) {
      setStatus("Use a supported code extension and a simple relative project path.", true);
      return false;
    }
    if (useDefaultName && projectHasFile(filename)) {
      const folder = parentDirectory(filename);
      const basename = filename.split("/").at(-1);
      const extension = basename.slice(basename.lastIndexOf("."));
      const stem = basename.slice(0, basename.lastIndexOf("."));
      let suffix = 2;
      let candidate = filename;
      while (projectHasFile(candidate)) {
        const name = `${stem}-${suffix++}${extension}`;
        candidate = folder ? `${folder}/${name}` : name;
      }
      filename = candidate;
    } else if (projectHasFile(filename)) {
      setStatus(
        `${filename} already exists. Select it from the explorer or choose another name.`,
        true,
      );
      return false;
    }

    const language = languageForFilename(filename);
    updateFileIdentity(filename);
    editor.value = createStarterSource(language);
    browserFiles[filename] = editor.value;
    markDirty(filename);
    persistBrowserFiles();
    populateFileSelect();
    if (fileSelect) fileSelect.value = filename;
    renderPreview();
    setStatus(
      `Created ${filename} in the browser workspace. Choose SAVE FILE to write it to the PC project.`,
    );
    return true;
  }

  async function createNewFolder() {
    const entered = String(folderNameInput?.value || "").trim();
    if (!entered) {
      setStatus("Enter a folder name or relative path first.", true);
      folderNameInput?.focus();
      return false;
    }
    if (renameFolderSource) return renameFolder(renameFolderSource, entered);
    const folder = entered;
    const candidate = currentFolder ? `${currentFolder}/${folder}` : folder;
    const safeFolder = safeFolderPath(candidate);
    if (!safeFolder) {
      setStatus("Use a simple relative folder path with no special characters.", true);
      return false;
    }
    if (projectHasFolder(safeFolder) || projectHasFile(safeFolder)) {
      setStatus(`${safeFolder} already exists in this project.`, true);
      return false;
    }

    let createdOnPc = false;
    let pcError = "";
    try {
      const response = await fetch(localAgentPath("/api/workspace/mkdir"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: safeFolder }),
      });
      const data = await response.json().catch(() => ({}));
      createdOnPc = response.ok && !!data.ok;
      if (!createdOnPc) {
        pcError = data.error || `Local workspace returned HTTP ${response.status}.`;
        setStatus(`Could not create ${safeFolder}: ${pcError}`, true);
        return false;
      }
    } catch (error) {
      pcError = error?.message || "The local agent is not reachable.";
    }
    browserFolders.add(safeFolder);
    persistBrowserFolders();
    if (folderNameInput) folderNameInput.value = "";
    revealFolder(safeFolder);
    setCurrentFolder(safeFolder);
    populateFileSelect();
    setStatus(
      createdOnPc
        ? `Created folder ${safeFolder} in the local project.`
        : `Created ${safeFolder} in this browser workspace. It will be written to the PC project when saved. (${pcError})`,
      !createdOnPc,
    );
    return true;
  }

  function beginFolderRename(path) {
    const safeFolder = safeFolderPath(path);
    if (!safeFolder || !folderNameInput) return false;
    renameFolderSource = safeFolder;
    folderNameInput.value = safeFolder.split("/").at(-1);
    folderNameInput.placeholder = `Rename ${safeFolder}`;
    if (newFolderButton) newFolderButton.textContent = "RENAME";
    if (cancelFolderRenameButton) cancelFolderRenameButton.hidden = false;
    folderNameInput.focus();
    setStatus(`Enter a new name for ${safeFolder}, then choose RENAME.`);
    return true;
  }

  function cancelFolderRename() {
    renameFolderSource = "";
    if (folderNameInput) {
      folderNameInput.value = "";
      folderNameInput.placeholder = "New folder name";
    }
    if (newFolderButton) newFolderButton.textContent = "+ FOLDER";
    if (cancelFolderRenameButton) cancelFolderRenameButton.hidden = true;
    setStatus("Folder rename cancelled.");
  }

  async function renameFolder(path, entered) {
    const oldFolder = safeFolderPath(path);
    const value = String(entered || "").trim();
    if (!oldFolder || !value) {
      setStatus("Enter the folder's new name or project-relative path.", true);
      return false;
    }
    const parent = oldFolder.includes("/") ? oldFolder.slice(0, oldFolder.lastIndexOf("/")) : "";
    const candidate = value.includes("/") ? value : joinWorkspacePath(parent, value);
    const newFolder = safeFolderPath(candidate);
    if (!newFolder) {
      setStatus("Use a simple relative path for the renamed folder.", true);
      return false;
    }
    if (newFolder === oldFolder) {
      setStatus("The folder name has not changed.", true);
      return false;
    }
    if (newFolder.startsWith(`${oldFolder}/`)) {
      setStatus("A folder cannot be moved into itself or one of its subfolders.", true);
      return false;
    }
    if (projectHasFolder(newFolder) || projectHasFile(newFolder)) {
      setStatus(`${newFolder} already exists in this project.`, true);
      return false;
    }

    let renamedOnPc = false;
    let pcError = "The local agent is not reachable.";
    try {
      const response = await fetch(localAgentPath("/api/workspace/rename"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_name: oldFolder, new_name: newFolder, directory: true }),
      });
      const data = await response.json().catch(() => ({}));
      renamedOnPc = response.ok && !!data.ok;
      if (!renamedOnPc) pcError = data.error || `Local workspace returned HTTP ${response.status}.`;
    } catch (error) {
      pcError = error?.message || pcError;
    }

    const hasBrowserCopy =
      browserFolders.has(oldFolder) ||
      Object.keys(browserFiles).some((name) => name.startsWith(`${oldFolder}/`));
    if (!renamedOnPc && !hasBrowserCopy) {
      setStatus(`Could not rename ${oldFolder}: ${pcError}`, true);
      return false;
    }
    const renamedFiles = {};
    for (const [name, content] of Object.entries(browserFiles)) {
      const nextName = name.startsWith(`${oldFolder}/`)
        ? `${newFolder}/${name.slice(oldFolder.length + 1)}`
        : name;
      renamedFiles[nextName] = content;
    }
    browserFiles = renamedFiles;
    dirtyFiles = new Set(
      [...dirtyFiles].map((name) =>
        name.startsWith(`${oldFolder}/`)
          ? `${newFolder}/${name.slice(oldFolder.length + 1)}`
          : name,
      ),
    );
    if (!renamedOnPc)
      for (const name of Object.keys(browserFiles))
        if (name.startsWith(`${newFolder}/`)) dirtyFiles.add(name);
    persistDirtyFiles();
    browserFolders = new Set(
      [...browserFolders].map((folder) =>
        folder === oldFolder || folder.startsWith(`${oldFolder}/`)
          ? `${newFolder}${folder.slice(oldFolder.length)}`
          : folder,
      ),
    );
    remoteDirectories = remoteDirectories.map((folder) =>
      folder === oldFolder || folder.startsWith(`${oldFolder}/`)
        ? `${newFolder}${folder.slice(oldFolder.length)}`
        : folder,
    );
    remoteFiles = remoteFiles.map((item) => ({
      ...item,
      filename: item.filename.startsWith(`${oldFolder}/`)
        ? `${newFolder}/${item.filename.slice(oldFolder.length + 1)}`
        : item.filename,
    }));
    if (currentFileName.startsWith(`${oldFolder}/`)) {
      currentFileName = `${newFolder}/${currentFileName.slice(oldFolder.length + 1)}`;
      updateFileIdentity(currentFileName);
    }
    if (currentFolder === oldFolder || currentFolder.startsWith(`${oldFolder}/`))
      setCurrentFolder(`${newFolder}${currentFolder.slice(oldFolder.length)}`);
    revealFolder(newFolder);
    renameFolderSource = "";
    if (folderNameInput) {
      folderNameInput.value = "";
      folderNameInput.placeholder = "New folder name";
    }
    if (newFolderButton) newFolderButton.textContent = "+ FOLDER";
    if (cancelFolderRenameButton) cancelFolderRenameButton.hidden = true;
    persistBrowserFiles();
    persistBrowserFolders();
    populateFileSelect();
    renderPreview();
    setStatus(
      renamedOnPc
        ? `Renamed folder ${oldFolder} to ${newFolder} in the local project.`
        : `Renamed the browser copy to ${newFolder}; PC rename failed: ${pcError}`,
      !renamedOnPc,
    );
    return true;
  }

  async function deleteFolder(path) {
    const safeFolder = safeFolderPath(path);
    if (!safeFolder) {
      setStatus("Select a valid project folder first.", true);
      return false;
    }
    if (
      !(await requestConfirmation(
        `Delete the empty folder ${safeFolder}? Files and non-empty folders are never removed this way.`,
        "Delete empty folder",
      ))
    )
      return false;

    const wasBrowserFolder = browserFolders.has(safeFolder);
    let deletedOnPc = false;
    let serverResponded = false;
    let responseStatus = 0;
    let pcError = "The local agent is not reachable.";
    try {
      const response = await fetch(localAgentPath("/api/workspace/delete"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: safeFolder, directory: true, confirm: true }),
      });
      serverResponded = true;
      responseStatus = response.status;
      const data = await response.json().catch(() => ({}));
      deletedOnPc = response.ok && !!data.ok;
      if (!deletedOnPc) pcError = data.error || `Local workspace returned HTTP ${response.status}.`;
    } catch (error) {
      pcError = error?.message || pcError;
    }
    if (!deletedOnPc && serverResponded && responseStatus !== 404) {
      setStatus(`Could not delete ${safeFolder}: ${pcError}`, true);
      return false;
    }
    if (!deletedOnPc && !wasBrowserFolder) {
      setStatus(`Could not delete ${safeFolder}: ${pcError}`, true);
      return false;
    }
    browserFolders.delete(safeFolder);
    remoteDirectories = remoteDirectories.filter((folder) => folder !== safeFolder);
    persistBrowserFolders();
    if (currentFolder === safeFolder || currentFolder.startsWith(`${safeFolder}/`))
      setCurrentFolder(
        safeFolder.includes("/") ? safeFolder.slice(0, safeFolder.lastIndexOf("/")) : "",
      );
    populateFileSelect();
    setStatus(
      deletedOnPc
        ? `Deleted the empty folder ${safeFolder}.`
        : `Removed ${safeFolder} from the browser folder list; PC deletion failed: ${pcError}`,
      !deletedOnPc,
    );
    return true;
  }

  async function renameCurrentFile() {
    const oldName = currentFileName;
    const entered = String(fileNameInput?.value || "").trim();
    let newName = safeFilename(entered);
    if (newName && !entered.includes("/"))
      newName = joinWorkspacePath(parentDirectory(oldName), newName);
    if (!newName) {
      setStatus("Enter a valid new filename with a supported extension.", true);
      return false;
    }
    if (oldName === newName) {
      setStatus("Change the filename first, then choose RENAME.", true);
      return false;
    }
    if (projectHasFile(newName)) {
      setStatus(`${newName} already exists in this project.`, true);
      return false;
    }
    let renamedOnPc = false;
    let renameError = "The local agent is not reachable.";
    try {
      const response = await fetch(localAgentPath("/api/workspace/rename"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_name: oldName, new_name: newName }),
      });
      const data = await response.json().catch(() => ({}));
      renamedOnPc = response.ok && !!data.ok;
      if (!renamedOnPc)
        renameError = data.error || `Local workspace returned HTTP ${response.status}.`;
    } catch (error) {
      renameError = error?.message || renameError;
    }
    if (Object.hasOwn(browserFiles, oldName)) {
      browserFiles[newName] = browserFiles[oldName];
      delete browserFiles[oldName];
      const wasDirty = dirtyFiles.has(oldName);
      dirtyFiles.delete(oldName);
      if (wasDirty || !renamedOnPc) dirtyFiles.add(newName);
      persistDirtyFiles();
    } else if (!renamedOnPc) {
      setStatus(`Couldn't rename ${oldName}: ${renameError}`, true);
      return false;
    }
    if (renamedOnPc) {
      remoteFiles = remoteFiles.filter((item) => item.filename !== oldName);
      if (!remoteFiles.some((item) => item.filename === newName))
        remoteFiles.push({ filename: newName });
    }
    updateFileIdentity(newName);
    persistBrowserFiles();
    populateFileSelect();
    if (fileSelect) fileSelect.value = newName;
    renderPreview();
    setStatus(
      renamedOnPc
        ? `Renamed ${oldName} to ${newName} on the PC.`
        : `Renamed the browser copy to ${newName}; PC rename failed: ${renameError}`,
      !renamedOnPc,
    );
    return true;
  }

  async function deleteCurrentFile() {
    const filename = currentFileName;
    if (!safeFilename(filename)) {
      setStatus("Select a valid project file before deleting.", true);
      return false;
    }
    if (
      !(await requestConfirmation(
        `Delete ${filename} from the browser copy and local project?`,
        "Delete project file",
      ))
    )
      return false;
    const hadBrowserCopy = Object.hasOwn(browserFiles, filename);
    delete browserFiles[filename];
    dirtyFiles.delete(filename);
    persistDirtyFiles();
    let deletedOnPc = false;
    let deleteError = "The local agent is not reachable.";
    try {
      const response = await fetch(localAgentPath("/api/workspace/delete"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, confirm: true }),
      });
      const data = await response.json().catch(() => ({}));
      deletedOnPc = response.ok && !!data.ok;
      if (!deletedOnPc)
        deleteError = data.error || `Local workspace returned HTTP ${response.status}.`;
    } catch (error) {
      deleteError = error?.message || deleteError;
    }
    const nextFile = Object.keys(browserFiles)[0] || "index.html";
    if (!Object.keys(browserFiles).length) browserFiles[nextFile] = STARTER_HTML;
    currentFileName = nextFile;
    editor.value = browserFiles[nextFile] || STARTER_HTML;
    updateFileIdentity(nextFile);
    persistBrowserFiles();
    renderPreview();
    await refreshFileList();
    if (deletedOnPc) setStatus(`Deleted ${filename} from the local project and browser copy.`);
    else if (hadBrowserCopy)
      setStatus(
        `Deleted the browser copy of ${filename}; local PC deletion failed: ${deleteError}`,
        true,
      );
    else setStatus(`Couldn't delete ${filename} from the PC: ${deleteError}`, true);
    return deletedOnPc || hadBrowserCopy;
  }

  async function testOnLocalhost(targetFilename = currentFilename()) {
    lastLocalTest = false;
    const filename = safeFilename(targetFilename);
    if (!filename || languageForFilename(filename) !== "html") {
      renderPreview();
      const htmlFilename = filename ? findProjectHtmlEntry(filename) : "";
      setStatus(
        htmlFilename
          ? `Select ${htmlFilename} to run its localhost preview. The live project page remains visible beside this source.`
          : "Select an HTML file to run a webpage on localhost. This language remains editable and can be opened in VS Code.",
        true,
      );
      return false;
    }
    const saved = await saveProjectToPc();
    if (!saved.ok) {
      renderPreview();
      setStatus(
        `Localhost agent unavailable (${saved.error}). The isolated browser preview remains active.`,
        true,
      );
      return false;
    }
    const previewUrl = `${localAgentPath("/api/workspace/preview")}?name=${encodeURIComponent(filename)}&asset_prefix=${encodeURIComponent(localAgentPath("/api/workspace/preview-files/"))}&t=${Date.now()}`;
    try {
      const response = await fetch(previewUrl, { cache: "no-store" });
      if (!response.ok) throw new Error(`preview returned HTTP ${response.status}`);
      preview.removeAttribute("srcdoc");
      preview.src = previewUrl;
      if (previewMode) previewMode.textContent = "LOCALHOST";
      lastLocalTest = true;
      setStatus(
        `Testing ${filename} from your local project${saved.data.path ? `: ${saved.data.path}` : ""}.`,
      );
      return true;
    } catch (error) {
      renderPreview();
      setStatus(
        `Could not start the localhost preview (${error?.message || "agent unavailable"}). The sandbox preview is still active.`,
        true,
      );
      return false;
    }
  }

  async function openInVSCode() {
    const saved = await saveProjectToPc();
    if (!saved.ok) {
      lastVscodeOpen = false;
      setStatus(
        `VS Code needs Weronika's local PC agent. This browser copy remains available: ${saved.error}`,
        true,
      );
      return false;
    }
    try {
      const response = await fetch(localAgentPath("/api/workspace/open-vscode"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) {
        lastVscodeOpen = false;
        setStatus(data.error || `VS Code launch failed (HTTP ${response.status}).`, true);
        return false;
      }
      lastVscodeOpen = true;
      setStatus(`Saved and opened the local project in VS Code: ${data.directory || data.path}.`);
      return true;
    } catch (error) {
      lastVscodeOpen = false;
      setStatus(
        `VS Code automation needs Weronika running locally: ${error?.message || "agent offline"}`,
        true,
      );
      return false;
    }
  }

  async function buildFromPrompt(rawPrompt, isRevision = false) {
    const prompt = String(rawPrompt || "").trim();
    if (!prompt) {
      setStatus("Describe the code or page you want me to build first.", true);
      return false;
    }
    lastVscodeOpen = false;
    lastLocalTest = false;
    lastBuildWasHtml = false;
    show();
    requestInput.value = prompt;
    setStatus("Asking Weronika's existing brain to write the source…");
    if (buildButton) buildButton.disabled = true;
    const detectedLanguage = detectLanguage(prompt, isRevision);
    const revisionFilename = currentFilename();
    const reuseCurrentFile =
      isRevision && languageForFilename(revisionFilename) === detectedLanguage;
    const requestedName = requestedFilename(prompt);
    const preferredName =
      requestedName ||
      (reuseCurrentFile ? revisionFilename : filenameForLanguage(detectedLanguage));
    const candidateName = preferredName.includes("/")
      ? preferredName
      : joinWorkspacePath(currentFolder, preferredName);
    const safeName = safeFilename(candidateName) || filenameForLanguage(detectedLanguage);
    updateFileIdentity(safeName);
    const language = languageForFilename(safeName);
    const currentSource =
      safeName === revisionFilename ? editor?.value || "" : browserFiles[safeName] || "";
    const displayName = typeof getDisplayName === "function" ? getDisplayName() : "Commander";
    const htmlTask = language === "html";
    lastBuildWasHtml = htmlTask;
    const sourceInstructions = htmlTask
      ? "Return a complete, responsive HTML5 document starting with <!doctype html>. Put CSS and JavaScript inline. Do not use Markdown fences, external libraries, fonts, images, or network resources; the preview sandbox has no network access. Make the page polished, accessible, and easy to test."
      : `Return only valid source code for ${LANGUAGES[language]?.label || language} in the file ${safeName}. Do not return HTML, explanations, or Markdown fences. Make it complete and runnable where practical, use standard libraries unless the request says otherwise, and include brief comments or a usage example in the source when useful.`;
    const brainPromptPrefix = [
      `CODING WORKSPACE TASK. Write or revise one source file in ${LANGUAGES[language]?.label || language}.`,
      sourceInstructions,
      `User request (keep its original wording and script): ${prompt}`,
      `If the user says “my name” without giving a name, use this saved display name: ${displayName}.`,
    ].join("\n\n");
    const sourceHeader = `Current file: ${safeName}. When revising, preserve useful source and apply the requested changes. Current source:\n`;
    const promptBase = `${brainPromptPrefix}\n\n${sourceHeader}`;
    if (promptBase.length > MAX_BRAIN_MESSAGE_CHARS - 100) {
      setStatus(
        "This build request is too long for one AI turn. Please split the instructions into smaller steps and try again.",
        true,
      );
      if (buildButton) buildButton.disabled = false;
      return false;
    }
    const sourceBudget = Math.max(0, MAX_BRAIN_MESSAGE_CHARS - promptBase.length - 100);
    let sourceExcerpt = currentSource;
    let truncationMarker = "";
    if (sourceExcerpt.length > sourceBudget) {
      truncationMarker =
        "\n[Middle of the existing source omitted to fit the brain message limit.]\n";
      const excerptBudget = Math.max(0, sourceBudget - truncationMarker.length);
      const headLength = Math.ceil(excerptBudget / 2);
      const tailLength = Math.floor(excerptBudget / 2);
      sourceExcerpt = `${currentSource.slice(0, headLength)}${truncationMarker}${tailLength ? currentSource.slice(-tailLength) : ""}`;
    }
    const brainPrompt = `${promptBase}${sourceExcerpt}`;
    try {
      const reply = await askBrain(
        brainPrompt,
        typeof getLanguage === "function" ? getLanguage() : "en-US",
      );
      if (reply && typeof reply === "object" && reply.error) {
        const detail = /message is too long/i.test(String(reply.error))
          ? "The build request exceeded the AI message limit. I already shorten large source context; try splitting unusually long instructions into smaller build steps."
          : String(reply.error);
        setStatus(`The brain could not write the source: ${detail}`, true);
        return false;
      }
      const source = extractSource(reply, language);
      if (!source) {
        setStatus(
          `The brain didn't return usable ${LANGUAGES[language]?.label || language} source. Ask it to return code only and try again.`,
          true,
        );
        return false;
      }
      editor.value = source;
      browserFiles[safeName] = source;
      currentFileName = safeName;
      markDirty(safeName);
      persistBrowserFiles();
      populateFileSelect();
      if (fileSelect) fileSelect.value = safeName;
      renderPreview();
      setStatus(
        htmlTask
          ? "Page generated by Weronika's brain. The isolated HTML preview is shown beside the source."
          : `${LANGUAGES[language]?.label || language} source generated. The project webpage preview stays beside the editor when an HTML entry is available.`,
      );
      if (/\b(?:vs\s*code|visual studio code)\b/i.test(prompt)) {
        const opened = await openInVSCode();
        if (opened && htmlTask) await testOnLocalhost(safeName);
      }
      return true;
    } catch (error) {
      setStatus(`Code generation failed: ${error?.message || "brain unavailable"}`, true);
      return false;
    } finally {
      if (buildButton) buildButton.disabled = false;
    }
  }

  async function handleRequest(text) {
    const raw = String(text || "").trim();
    if (detectLocalMediaRequest(raw)) return null;
    const directMediaRequest =
      /^\s*(?:please\s+)?(?:make|create|generate|draw|paint|design|render|show\s+me|write|sing|compose|shoot|film)\s+(?:me\s+)?(?:(?:a|an|the)\s+)?(?:image|picture|photo|pic|art|artwork|drawing|wallpaper|illustration|song|music|track|melody|tune|video(?!\s+game)|clip|reel|animation|movie)\b/i.test(
        raw,
      );
    if (directMediaRequest) return null;
    if (/^(?:open|show)\s+(?:the\s+)?(?:code|coding)\s+(?:workspace|editor)$/i.test(raw)) {
      show();
      return isHindi()
        ? "कोड वर्कस्पेस खुल गया है। वेबपेज बनाने के लिए कहें या ऊपर से कोई प्रोग्रामिंग भाषा चुनें।"
        : "The code workspace is open. Ask for a webpage or another programming language, or choose a language above.";
    }
    const mentionsCode =
      /\b(?:website|web\s?page|webpage|site|landing page|web app|html|css|javascript|typescript|python|java|cpp|csharp|golang|rust|php|ruby|swift|kotlin|dart|sql|bash|json|markdown|code|script|program|function|class|calculator|api|algorithm|game|tool|app|frontend|front-end)\b|(?:^|[^a-z0-9])(?:c\+\+|c#)(?:$|[^a-z0-9])|वेबसाइट|वेब\s?पेज|प्रोग्राम|कोड/i.test(
        raw,
      );
    const buildVerb =
      /\b(?:build|create|make|write|design|develop|generate|code|program|update|edit|modify|fix|change|add|banao|bana|banana|banaye|likho)\b|बना(?:ओ|एँ?|कर|ना|दो|दें)|लिख(?:ो|ें|ना)|डिज़ाइन|डिजाइन|तैयार/i.test(
        raw,
      );
    const followup = open && isFollowupRequest(raw);
    if (!((mentionsCode && buildVerb) || followup)) return null;
    const explicitlyRequestsVSCode = /\b(?:vs\s*code|visual studio code)\b/i.test(raw);
    const isRevision =
      followup || (open && /\b(?:change|update|edit|modify|fix|add|remove|replace)\b/i.test(raw));
    const built = await buildFromPrompt(raw, isRevision);
    if (!built) {
      return isHindi()
        ? "वर्कस्पेस खुला है, लेकिन कोड नहीं बन पाया। कनेक्शन की जानकारी के लिए ऊपर स्टेटस देखें।"
        : "The workspace is open, but the code wasn't generated. Check its status for the connection error.";
    }
    if (explicitlyRequestsVSCode) {
      if (isHindi()) {
        if (!lastVscodeOpen)
          return "कोड तैयार है; VS Code कनेक्शन नहीं हुआ। ऊपर स्टेटस में वजह देखें।";
        if (lastBuildWasHtml && lastLocalTest)
          return "कोड स्थानीय प्रोजेक्ट में सेव किया, VS Code खोला और HTML पेज localhost पर टेस्ट किया।";
        if (lastBuildWasHtml)
          return "कोड सेव करके VS Code खोला, लेकिन localhost टेस्ट पूरा नहीं हुआ; वर्कस्पेस स्टेटस देखें।";
        return "कोड स्थानीय प्रोजेक्ट में सेव करके VS Code खोल दिया है।";
      }
      if (!lastVscodeOpen)
        return "I wrote the code. The VS Code handoff didn't complete; check the workspace status for the reason.";
      if (lastBuildWasHtml && lastLocalTest)
        return "I wrote the code, saved the project, opened VS Code, and tested the HTML page on localhost.";
      if (lastBuildWasHtml)
        return "I saved the code and opened VS Code, but the localhost test didn't complete; check the workspace status.";
      return "I wrote the code, saved it in the local project, and opened VS Code.";
    }
    if (isHindi())
      return "कोड वर्कस्पेस में तैयार है। अलग-अलग फाइलें और भाषाएँ Explorer से चुनें; उपलब्ध HTML प्रोजेक्ट का लाइव प्रीव्यू साथ में दिखेगा।";
    return "The code is ready in the workspace. Choose files and folders in the Explorer; the live webpage preview stays beside the editor whenever the project has an HTML entry.";
  }

  if (openButton) openButton.addEventListener("click", show);
  if (closeButton) closeButton.addEventListener("click", hide);
  if (rightPaneButton) rightPaneButton.addEventListener("click", toggleWorkspaceRightPane);
  if (aiTabButton)
    aiTabButton.addEventListener("click", () => {
      revealWorkspaceRightPane();
      setWorkspacePanel("ai");
    });
  if (previewTabButton)
    previewTabButton.addEventListener("click", () => {
      revealWorkspaceRightPane();
      setWorkspacePanel("preview");
    });
  if (aiForm)
    aiForm.addEventListener("submit", (event) => {
      event.preventDefault();
      askWorkspaceAI();
    });
  if (aiInput)
    aiInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        aiForm?.requestSubmit?.();
        if (!aiForm?.requestSubmit) askWorkspaceAI();
      }
    });
  if (terminalForm)
    terminalForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const command = terminalInput?.value || "";
      if (terminalInput) terminalInput.value = "";
      runProjectTerminalCommand(command);
    });
  if (terminalClearButton)
    terminalClearButton.addEventListener("click", () => terminalOutput?.replaceChildren());
  if (runButton) runButton.addEventListener("click", updateSourcePreviewStatus);
  if (saveButton)
    saveButton.addEventListener("click", async () => {
      const filename = currentFilename();
      if (!filename) {
        setStatus("Enter a valid filename with a supported code extension.", true);
        return;
      }
      const result = await saveToPc(filename);
      setStatus(
        result.ok
          ? `Saved ${filename} on your PC: ${result.data.path}`
          : `Saved ${filename} in this browser only. PC save unavailable: ${result.error}`,
        !result.ok,
      );
      await refreshFileList();
    });
  if (loadButton) loadButton.addEventListener("click", () => loadFile(currentFilename()));
  if (testButton) testButton.addEventListener("click", testOnLocalhost);
  if (vscodeButton) vscodeButton.addEventListener("click", openInVSCode);
  if (newFileButton) newFileButton.addEventListener("click", createNewFile);
  if (newFolderButton) newFolderButton.addEventListener("click", createNewFolder);
  if (cancelFolderRenameButton)
    cancelFolderRenameButton.addEventListener("click", cancelFolderRename);
  if (folderNameInput)
    folderNameInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        createNewFolder();
      }
    });
  if (deleteButton) deleteButton.addEventListener("click", deleteCurrentFile);
  if (renameButton) renameButton.addEventListener("click", renameCurrentFile);
  if (buildButton)
    buildButton.addEventListener("click", () => {
      const prompt = requestInput?.value || "";
      buildFromPrompt(prompt, open && isFollowupRequest(prompt));
    });
  if (requestInput)
    requestInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter")
        buildFromPrompt(requestInput.value, open && isFollowupRequest(requestInput.value));
    });
  if (fileSelect)
    fileSelect.addEventListener("change", () => {
      const filename = safeFilename(fileSelect.value);
      if (filename) loadFile(filename);
    });
  if (fileNameInput)
    fileNameInput.addEventListener("input", () => {
      const filename = safeFilename(fileNameInput.value);
      if (filename) {
        if (fileLabel) fileLabel.textContent = filename;
        renderPreview();
      }
    });
  if (editor)
    editor.addEventListener("input", () => {
      persistCurrentFile();
      syncLineNumbers();
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(renderPreview, 250);
    });
  if (editor)
    editor.addEventListener("scroll", () => {
      if (lineNumbers) lineNumbers.scrollTop = editor.scrollTop;
    });
  if (editor)
    editor.addEventListener("keydown", (event) => {
      if (event.key !== "Tab") return;
      event.preventDefault();
      editor.setRangeText("  ", editor.selectionStart, editor.selectionEnd, "end");
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    });
  window.addEventListener("message", (event) => {
    if (event.source !== preview?.contentWindow || event.data?.source !== "weronika-code-preview")
      return;
    if (event.data.type === "error")
      setStatus(
        `Preview JavaScript error: ${String(event.data.message || "unknown error").slice(0, 180)}`,
        true,
      );
  });
  if (confirmAcceptButton)
    confirmAcceptButton.addEventListener("click", () => resolveConfirmation(true));
  if (confirmCancelButton)
    confirmCancelButton.addEventListener("click", () => resolveConfirmation(false));
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && confirmationResolver) {
      event.preventDefault();
      resolveConfirmation(false);
      return;
    }
    if (event.key === "Escape" && open) hide();
  });

  initialize();

  return {
    handleRequest,
    open: show,
    close: hide,
    isOpen: () => open,
  };
}
