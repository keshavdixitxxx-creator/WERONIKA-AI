"""On-device memory file for the orb's conversation with Weronika.

The orb keeps its own memory in browser storage. When it is served by this worker it
also mirrors that memory here, so a cleared browser profile, another browser, or a
different port still finds the same conversation after a shutdown.

The worker stores the document as-is and never reads meaning into it. The orb never
puts message text, contact names, or email content from local messaging, reply watch,
or Gmail into this document; those steps are recorded only as a neutral marker.

Forgetting is done by the orb as well: it writes a document without the forgotten
turns and with the time of the wipe, so that a stale copy in another browser cannot
bring them back. That is why this store has no delete operation.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

MAX_MEMORY_BYTES = 2_000_000
MEMORY_FILE = "weronika-memory.json"
MEMORY_VERSION = 1


class MemoryStoreError(RuntimeError):
    """A safe, user-actionable memory error."""


class MemoryStore:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or (Path.home() / ".weronika" / "memory")).expanduser()
        self.path = self.root / MEMORY_FILE
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any] | None:
        """Return the stored memory, or None when nothing readable is stored."""
        with self._lock:
            try:
                if self.path.is_symlink():
                    return None
                raw = self.path.read_bytes()
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise MemoryStoreError("Weronika could not read her memory file on this device.") from exc
            if len(raw) > MAX_MEMORY_BYTES:
                self._set_aside()
                return None
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = None
            if not isinstance(value, dict) or value.get("v") != MEMORY_VERSION:
                # Keep an unreadable file for manual recovery instead of overwriting it.
                self._set_aside()
                return None
            return value

    def save(self, memory: object) -> dict[str, Any]:
        if not isinstance(memory, dict) or memory.get("v") != MEMORY_VERSION:
            raise MemoryStoreError("Memory must be a version 1 memory document.")
        turns = memory.get("turns")
        if not isinstance(turns, list):
            raise MemoryStoreError("Memory must list its conversation turns.")
        encoded = json.dumps(memory, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_MEMORY_BYTES:
            raise MemoryStoreError("Memory is larger than the 2 MB limit for this device.")
        with self._lock:
            temp_name = ""
            try:
                self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    self.root.chmod(0o700)
                except OSError:
                    pass
                if self.path.is_symlink():
                    raise MemoryStoreError("The memory file location is not a regular file.")
                # Write beside the target and swap, so a crash or power cut during a
                # shutdown never leaves a half-written memory file.
                handle, temp_name = tempfile.mkstemp(prefix=".memory-", suffix=".tmp", dir=self.root)
                with os.fdopen(handle, "wb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.chmod(temp_name, 0o600)
                except OSError:
                    pass
                os.replace(temp_name, self.path)
                temp_name = ""
            except OSError as exc:
                raise MemoryStoreError("Weronika could not write her memory file on this device.") from exc
            finally:
                if temp_name:
                    try:
                        os.unlink(temp_name)
                    except OSError:
                        pass
        return {"saved": True, "bytes": len(encoded), "turns": len(turns)}

    def _set_aside(self) -> None:
        try:
            os.replace(self.path, self.root / "weronika-memory.unreadable.json")
        except OSError:
            pass
