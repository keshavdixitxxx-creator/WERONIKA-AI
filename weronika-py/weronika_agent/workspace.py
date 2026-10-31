"""Safe local workspace files and opt-in Python execution."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILE_BYTES = 1_000_000
MAX_RUN_SECONDS = 20
MAX_OUTPUT_CHARS = 20_000
IGNORED_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".vscode"}
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt", ".toml", ".yaml", ".yml"}


class WorkspaceError(RuntimeError):
    """A safe, user-actionable workspace error."""


class LocalWorkspace:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or (Path.home() / ".weronika" / "workspace")).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def _resolve(self, raw: str) -> Path:
        if not isinstance(raw, str) or not raw.strip():
            raise WorkspaceError("Choose a workspace file first.")
        relative = PurePosixPath(raw.replace("\\", "/"))
        if relative.is_absolute() or any(part in {"..", ""} for part in relative.parts):
            raise WorkspaceError("Workspace paths must stay inside the Weronika workspace.")
        path = (self.root / Path(*relative.parts)).resolve()
        if not path.is_relative_to(self.root):
            raise WorkspaceError("Workspace paths must stay inside the Weronika workspace.")
        if path.name in IGNORED_NAMES:
            raise WorkspaceError("That workspace path is reserved.")
        return path

    @staticmethod
    def _check_extension(path: Path) -> None:
        if path.suffix.casefold() not in ALLOWED_EXTENSIONS:
            raise WorkspaceError("This first workspace version supports code and text files only.")

    def tree(self, max_items: int = 500) -> list[dict[str, Any]]:
        count = 0

        def visit(folder: Path, prefix: str = "") -> list[dict[str, Any]]:
            nonlocal count
            items: list[dict[str, Any]] = []
            try:
                entries = sorted(folder.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
            except OSError:
                return items
            for entry in entries:
                if entry.name.startswith(".") or entry.name in IGNORED_NAMES or entry.is_symlink():
                    continue
                count += 1
                if count > max_items:
                    break
                relative = f"{prefix}/{entry.name}".strip("/")
                if entry.is_dir():
                    items.append({"name": entry.name, "path": relative, "kind": "directory", "children": visit(entry, relative)})
                elif entry.is_file() and entry.suffix.casefold() in ALLOWED_EXTENSIONS:
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        continue
                    items.append({"name": entry.name, "path": relative, "kind": "file", "size": size})
            return items

        return visit(self.root)

    def read(self, raw_path: str) -> dict[str, Any]:
        path = self._resolve(raw_path)
        self._check_extension(path)
        if not path.is_file() or path.is_symlink():
            raise WorkspaceError("That workspace file does not exist.")
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise WorkspaceError("This file is over the 1 MB editor limit.")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceError("This editor opens UTF-8 text files only.") from exc
        return {"path": path.relative_to(self.root).as_posix(), "content": content, "size": size}

    def save(self, raw_path: str, content: str, *, overwrite: bool = True) -> dict[str, Any]:
        path = self._resolve(raw_path)
        self._check_extension(path)
        if not isinstance(content, str):
            raise WorkspaceError("File content must be text.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise WorkspaceError("Files are limited to 1 MB in this workspace.")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or (path.exists() and not overwrite):
            raise WorkspaceError("That file already exists. Confirm overwrite in the editor first.")
        path.write_bytes(encoded)
        return {"path": path.relative_to(self.root).as_posix(), "size": len(encoded), "saved": True}

    def run_python(self, raw_path: str, *, confirmed: bool) -> dict[str, Any]:
        if confirmed is not True:
            raise WorkspaceError("Running code requires explicit confirmation in the workspace.")
        path = self._resolve(raw_path)
        if path.suffix.casefold() != ".py":
            raise WorkspaceError("Run is currently available for Python files only.")
        if not path.is_file() or path.is_symlink():
            raise WorkspaceError("Save the Python file before running it.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError("This file is over the 1 MB run limit.")
        environment = {
            key: os.environ[key]
            for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE")
            if key in os.environ
        }
        try:
            result = subprocess.run(
                [sys.executable, "-I", str(path)],
                cwd=str(self.root),
                env=environment,
                capture_output=True,
                text=True,
                timeout=MAX_RUN_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _output_text(exc.stdout)
            stderr = _output_text(exc.stderr)
            return {
                "returncode": None,
                "stdout": stdout,
                "stderr": (stderr + "\nExecution stopped after 20 seconds.").strip(),
                "timed_out": True,
            }
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-MAX_OUTPUT_CHARS:],
            "stderr": result.stderr[-MAX_OUTPUT_CHARS:],
            "timed_out": False,
        }


def _output_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")[-MAX_OUTPUT_CHARS:]
    return value[-MAX_OUTPUT_CHARS:]
