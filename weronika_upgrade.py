"""Self-upgrade proposals for the local Weronika agent.

A proposal is a unified diff plus an explanation. Nothing in the project is
written or executed until approve() is called with confirm=True for that id.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Callable

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE) if os.path.isdir(os.path.join(HERE, "..", "public")) else HERE

INSPECT_FILES = (
    "weronika_agent.py",
    "weronika_automation.py",
    "weronika_calls.py",
    "weronika_upgrade.py",
    "requirements.txt",
    "README.md",
    "config.json",
)

ALLOWED_SUFFIXES = (".py", ".md", ".txt", ".js", ".ts", ".html")
DENY_NAMES = {
    "config.json",
    ".env",
    ".env.local",
    "credentials.json",
}


def _proposals_dir(root: str | None = None) -> str:
    path = os.path.join(root or HERE, "proposals")
    os.makedirs(path, exist_ok=True)
    return path


def sanitize_address(raw: str | None) -> str:
    text = re.sub(r"[\x00-\x1f<>{}]", "", raw or "")
    text = re.sub(r"\s+", " ", text).strip()[:40]
    return text or "Commander"


def repo_root(root: str | None = None) -> str:
    if root:
        return os.path.abspath(root)
    return os.path.abspath(REPO_ROOT)


def inspect_project(root: str | None = None) -> dict:
    base = repo_root(root)
    local = base if os.path.basename(base) == "weronika-local" else os.path.join(base, "weronika-local")
    if not os.path.isdir(local):
        local = base
    files = []
    for name in INSPECT_FILES:
        path = os.path.join(local, name)
        if not os.path.isfile(path):
            files.append({"name": name, "exists": False})
            continue
        size = os.path.getsize(path)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(80_000)
        files.append({
            "name": name,
            "exists": True,
            "bytes": size,
            "lines": text.count("\n") + 1,
        })
    features = []
    agent = os.path.join(local, "weronika_agent.py")
    if os.path.isfile(agent):
        features.append("local agent present")
    if os.path.isfile(os.path.join(local, "weronika_calls.py")):
        features.append("call assistant module present")
    try:
        import pywinauto  # noqa: F401
        features.append("pywinauto installed")
    except Exception:
        features.append("pywinauto not installed")
    return {
        "root": base,
        "local": local,
        "files": files,
        "features": features,
        "platform": os.name,
    }


def _rel_path(path: str, root: str) -> str:
    rel = path.replace("\\", "/").lstrip("/")
    if rel.startswith("a/") or rel.startswith("b/"):
        rel = rel[2:]
    rel = os.path.normpath(rel).replace("\\", "/")
    if rel.startswith("../") or rel == ".." or os.path.isabs(path):
        raise ValueError(f"path escapes the project: {path}")
    full = os.path.normpath(os.path.join(root, rel))
    if os.path.commonpath([root, full]) != os.path.normpath(root):
        raise ValueError(f"path escapes the project: {path}")
    return rel


def path_allowed(rel: str) -> bool:
    name = os.path.basename(rel)
    if name in DENY_NAMES or name.startswith(".env"):
        return False
    if rel.startswith(".git/") or "/.git/" in f"/{rel}/" or "node_modules" in rel.split("/"):
        return False
    if not rel.endswith(ALLOWED_SUFFIXES):
        return False
    allowed_prefixes = (
        "weronika-local/",
        "public/",
        "src/routes/api/public/",
        "src/lib/",
    )
    if rel in {"README.md", "weronika-local/README.md"}:
        return True
    return any(rel.startswith(prefix) or rel == prefix.rstrip("/") for prefix in allowed_prefixes) or (
        "/" not in rel and rel.endswith((".py", ".md", ".txt"))
    )


def parse_unified_diff(patch: str, root: str) -> list[dict]:
    if "--- " not in patch or "+++ " not in patch:
        raise ValueError("proposal patch is not a unified diff")
    lines = patch.splitlines()
    files: list[dict] = []
    current: dict | None = None
    hunk: dict | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- "):
            old = line[4:].split("\t", 1)[0].strip()
            if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
                raise ValueError("malformed diff header")
            new = lines[i + 1][4:].split("\t", 1)[0].strip()
            target = new if new != "/dev/null" else old
            if target == "/dev/null":
                raise ValueError("file deletions are not applied by upgrade approval")
            rel = _rel_path(target, root)
            if not path_allowed(rel):
                raise ValueError(f"patch path is not allowed: {rel}")
            current = {"path": rel, "hunks": [], "new_file": old == "/dev/null"}
            files.append(current)
            hunk = None
            i += 2
            continue
        if line.startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not match or current is None:
                raise ValueError("malformed hunk header")
            hunk = {
                "old_start": int(match.group(1)),
                "old_len": int(match.group(2) or "1"),
                "lines": [],
            }
            current["hunks"].append(hunk)
            i += 1
            continue
        if hunk is not None and (line.startswith("+") or line.startswith("-") or line.startswith(" ") or line == ""):
            # A completely empty line in a diff is a context line of "".
            if line == "":
                hunk["lines"].append((" ", ""))
            else:
                hunk["lines"].append((line[0], line[1:]))
            i += 1
            continue
        i += 1
    if not files:
        raise ValueError("diff did not name any files")
    return files


def _apply_hunks(original: str, hunks: list[dict]) -> str:
    src = original.splitlines()
    out: list[str] = []
    cursor = 0
    for hunk in hunks:
        start = max(hunk["old_start"] - 1, 0)
        if start < cursor:
            raise ValueError("overlapping hunks")
        out.extend(src[cursor:start])
        cursor = start
        for kind, text in hunk["lines"]:
            if kind == " ":
                if cursor >= len(src) or src[cursor] != text:
                    raise ValueError("hunk context did not match the file")
                out.append(src[cursor])
                cursor += 1
            elif kind == "-":
                if cursor >= len(src) or src[cursor] != text:
                    raise ValueError("hunk deletion did not match the file")
                cursor += 1
            elif kind == "+":
                out.append(text)
    out.extend(src[cursor:])
    trailing = original.endswith("\n") or original == ""
    text = "\n".join(out)
    if trailing or text:
        text += "\n"
    return text


def apply_patch(patch: str, root: str | None = None, write: bool = False) -> dict:
    base = repo_root(root)
    files = parse_unified_diff(patch, base)
    planned = []
    for item in files:
        full = os.path.join(base, item["path"])
        if item["new_file"]:
            original = ""
            if os.path.exists(full):
                raise ValueError(f"{item['path']} already exists")
        else:
            if not os.path.isfile(full):
                raise ValueError(f"missing file for patch: {item['path']}")
            with open(full, "r", encoding="utf-8") as fh:
                original = fh.read()
        updated = _apply_hunks(original, item["hunks"])
        planned.append({"path": item["path"], "full": full, "content": updated, "new_file": item["new_file"]})
    if write:
        for item in planned:
            os.makedirs(os.path.dirname(item["full"]), exist_ok=True)
            with open(item["full"], "w", encoding="utf-8") as fh:
                fh.write(item["content"])
    return {"files": [item["path"] for item in planned], "written": write}


def _offline_patch(inspection: dict, goal: str) -> tuple[str, str]:
    local_rel = "weronika-local/assistant_diagnostics.md"
    root = inspection["root"]
    # When tests point root at a temp weronika-local folder, keep the file inside it.
    if os.path.basename(root) == "weronika-local" or not os.path.isdir(os.path.join(root, "weronika-local")):
        rel = "assistant_diagnostics.md"
        full = os.path.join(root, rel)
    else:
        rel = local_rel
        full = os.path.join(root, rel)
    lines = [
        "# Weronika local diagnostics",
        "",
        "Prepared by inspection. This note does not change runtime behavior.",
        "",
        f"Goal: {goal or 'general inspection'}",
        f"Platform: {inspection['platform']}",
        "",
        "Files:",
    ]
    for item in inspection["files"]:
        if item.get("exists"):
            lines.append(f"- {item['name']}: {item['lines']} lines")
        else:
            lines.append(f"- {item['name']}: missing")
    lines.append("")
    lines.append("Features: " + ", ".join(inspection["features"]))
    lines.append("")
    new_text = "\n".join(lines) + "\n"
    if os.path.isfile(full):
        with open(full, "r", encoding="utf-8") as fh:
            old = fh.read().splitlines()
        diff = [f"--- a/{rel}", f"+++ b/{rel}", f"@@ -1,{len(old)} +1,{len(new_text.splitlines())} @@"]
        for line in old:
            diff.append(f"-{line}")
        for line in new_text.splitlines():
            diff.append(f"+{line}")
        patch = "\n".join(diff) + "\n"
    else:
        body = new_text.splitlines()
        diff = [f"--- /dev/null", f"+++ b/{rel}", f"@@ -0,0 +1,{len(body)} @@"]
        diff.extend(f"+{line}" for line in body)
        patch = "\n".join(diff) + "\n"
    explanation = (
        "I inspected the local project and prepared a diagnostics note. "
        "It lists which agent files are present and which optional pieces are missing. "
        "Nothing has been written yet."
    )
    return explanation, patch


def _extract_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model did not return JSON")
    return json.loads(raw[start : end + 1])


def create_proposal(
    goal: str = "",
    address_name: str = "Commander",
    lang: str = "en",
    complete_fn: Callable[[list[dict]], str] | None = None,
    root: str | None = None,
) -> dict:
    inspection = inspect_project(root)
    title = sanitize_address(address_name)
    explanation = ""
    patch = ""
    source = "inspection"
    if complete_fn and goal.strip():
        try:
            raw = complete_fn([
                {
                    "role": "system",
                    "content": (
                        "You propose a minimal unified diff for the local Weronika project. "
                        "Reply with one JSON object and nothing else: "
                        '{"explanation":"...","patch":"unified diff"}. '
                        "Only touch weronika-local markdown or python files other than config.json. "
                        "Do not delete files. Do not include shell commands. "
                        "The patch must be a valid unified diff."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"goal": goal, "inspection": inspection}, ensure_ascii=False)[:8000],
                },
            ])
            data = _extract_json(raw)
            explanation = str(data.get("explanation") or "").strip()
            patch = str(data.get("patch") or "")
            apply_patch(patch, inspection["root"], write=False)
            source = "model"
        except Exception as exc:
            explanation = (
                f"I could not turn that goal into a safe patch ({exc}). "
                "I prepared an inspection note instead."
            )
            patch = ""
    if not patch:
        offline_explanation, patch = _offline_patch(inspection, goal)
        explanation = f"{explanation} {offline_explanation}".strip() if explanation else offline_explanation
        source = "inspection"
    try:
        checked = apply_patch(patch, inspection["root"], write=False)
        applicable = True
        files = checked["files"]
        reason = ""
    except Exception as exc:
        applicable = False
        files = []
        reason = str(exc)
    proposal = {
        "id": uuid.uuid4().hex[:12],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "goal": goal.strip(),
        "explanation": explanation,
        "patch": patch,
        "files": files,
        "source": source,
        "status": "pending" if applicable else "invalid",
        "applicable": applicable,
        "reason": reason,
        "address_name": title,
        "lang": lang or "en",
        "root": inspection["root"],
        "written": False,
        "executed": False,
    }
    store_root = HERE if root is None else inspection["local"]
    store_dir = _proposals_dir(store_root)
    path = os.path.join(store_dir, f"{proposal['id']}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(proposal, fh, ensure_ascii=False, indent=2)
    say = (
        f"{title}, I prepared a proposal. Nothing is written until you approve it."
        if not (lang or "").startswith("hi")
        else f"{title}, मैंने एक प्रस्ताव तैयार किया है। जब तक आप मंज़ूरी नहीं देते, कुछ लिखा नहीं जाएगा।"
    )
    return {**proposal, "say": say, "path": path}


def _load(proposal_id: str, root: str | None = None) -> tuple[str, dict]:
    store = _proposals_dir(HERE if root is None else root)
    path = os.path.join(store, f"{os.path.basename(proposal_id)}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError("proposal not found")
    with open(path, "r", encoding="utf-8") as fh:
        return path, json.load(fh)


def approve_proposal(proposal_id: str, confirm: bool = False, root: str | None = None) -> dict:
    if confirm is not True:
        return {
            "ok": False,
            "status": "needs_confirmation",
            "written": False,
            "executed": False,
            "reason": "Set confirm to true to write this proposal. Nothing was written or executed.",
        }
    try:
        path, proposal = _load(proposal_id, root)
    except FileNotFoundError:
        return {"ok": False, "status": "error", "written": False, "executed": False, "reason": "proposal not found"}
    if proposal.get("status") == "applied":
        return {
            "ok": False,
            "status": "error",
            "written": False,
            "executed": False,
            "reason": "That proposal was already applied. It was not executed again.",
        }
    if not proposal.get("applicable"):
        return {
            "ok": False,
            "status": "error",
            "written": False,
            "executed": False,
            "reason": proposal.get("reason") or "This proposal cannot be applied.",
        }
    try:
        result = apply_patch(proposal.get("patch") or "", proposal.get("root"), write=True)
    except Exception as exc:
        return {"ok": False, "status": "error", "written": False, "executed": False, "reason": str(exc)}
    proposal["status"] = "applied"
    proposal["written"] = True
    proposal["executed"] = False
    proposal["applied_files"] = result["files"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(proposal, fh, ensure_ascii=False, indent=2)
    title = proposal.get("address_name") or "Commander"
    return {
        "ok": True,
        "status": "applied",
        "id": proposal["id"],
        "written": True,
        "executed": False,
        "files": result["files"],
        "reason": "The patch was written. It was not executed. Restart the local agent to load Python changes.",
        "say": f"{title}, the proposal is written. I did not run it.",
    }


def reject_proposal(proposal_id: str, root: str | None = None) -> dict:
    try:
        path, proposal = _load(proposal_id, root)
    except FileNotFoundError:
        return {"ok": False, "status": "error", "written": False, "reason": "proposal not found"}
    proposal["status"] = "rejected"
    proposal["written"] = False
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(proposal, fh, ensure_ascii=False, indent=2)
    return {"ok": True, "status": "rejected", "written": False, "executed": False, "reason": "Rejected. Nothing was written."}


def list_proposals(root: str | None = None) -> list[dict]:
    store = _proposals_dir(HERE if root is None else root)
    items = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(store, name), "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        items.append({
            "id": data.get("id"),
            "status": data.get("status"),
            "applicable": data.get("applicable"),
            "files": data.get("files"),
            "written": data.get("written", False),
        })
    return items
