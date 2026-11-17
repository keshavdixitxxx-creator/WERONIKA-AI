"""Loopback-only static UI and JSON API for local messaging automation."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .apps import AppLauncher, OpenService
from .blueprint import (
    MAX_IMAGE_BYTES,
    MAX_MODEL_BYTES,
    BlueprintError,
    describe_vrm_limits,
    glb_to_vrm,
    reconstruct_photo,
)
from .call_intents import has_call_intent, parse_call_request, telegram_note
from .calls import CallWatchError
from .hardware import detect_hardware
from .intents import parse_message_request
from .memory_store import MAX_MEMORY_BYTES, MemoryStore, MemoryStoreError
from .models import Platform
from .news import NewsError, fetch_news
from .phone_link import scan_links
from .reply_watch import ReplyWatchError
from .service import create_call_service, create_messaging_service
from .site_service import SiteError, SiteService
from .tasks import ACTIONS, TaskError
from .web_intents import plan_local, url_for_system_open, wants_system_browser
from .watch_intents import has_watch_intent, parse_watch_request
from .workflow import MessagingError
from .workspace import LocalWorkspace, WorkspaceError

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "public"
MAX_REQUEST_BYTES = 16_384
MAX_WORKSPACE_REQUEST_BYTES = 1_100_000
MAX_MEMORY_REQUEST_BYTES = MAX_MEMORY_BYTES + 200_000


class LocalServer(HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(
    service,
    adapters,
    workspace: LocalWorkspace | None = None,
    watch=None,
    skills=None,
    tasks=None,
    memory: MemoryStore | None = None,
    apps: AppLauncher | None = None,
    news=None,
    calls=None,
):
    local_workspace = workspace or LocalWorkspace()
    memory_store = memory or MemoryStore()
    app_launcher = apps or AppLauncher()
    read_news = news or fetch_news

    class Handler(BaseHTTPRequestHandler):
        server_version = "WeronikaLocal/0.1"

        def log_message(self, format: str, *args) -> None:
            # Never log request bodies (which can contain private message text).
            super().log_message(format, *args)

        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def _blueprint_vrm(self) -> None:
            """Wrap a generated GLB into a VRM container for download."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Invalid model content length."})
                return
            if length <= 0 or length > MAX_MODEL_BYTES:
                self._send_json(413, {"error": "Models must be 80 MB or smaller."})
                return
            payload = self.rfile.read(length)
            if len(payload) != length:
                self._send_json(400, {"error": "The model upload was incomplete. Please try again."})
                return
            title = (self.headers.get("X-Weronika-Title", "") or "Weronika avatar").strip()[:64]
            try:
                vrm = glb_to_vrm(payload, title)
            except BlueprintError as exc:
                self._send_json(exc.status_code, {"error": str(exc)})
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(vrm)))
            self.send_header("Content-Disposition", 'attachment; filename="weronika-avatar.vrm"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Weronika-VRM-Static", "1")
            self.end_headers()
            self.wfile.write(vrm)

        def _blueprint_reconstruct(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Invalid photo content length."})
                return
            if length <= 0 or length > MAX_IMAGE_BYTES:
                self._send_json(413, {"error": "Photos must be 20 MB or smaller for local 3D generation."})
                return
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/") and content_type != "application/octet-stream":
                self._send_json(415, {"error": "Upload a supported image file for local 3D generation."})
                return
            image_bytes = self.rfile.read(length)
            if len(image_bytes) != length:
                self._send_json(400, {"error": "The photo upload was incomplete. Please try again."})
                return
            try:
                glb, message = reconstruct_photo(image_bytes)
            except BlueprintError as exc:
                self._send_json(exc.status_code, {"error": str(exc)})
                return
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(glb)))
            self.send_header("Content-Disposition", 'attachment; filename="weronika-generated-model.glb"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Weronika-Blueprint-Status", message)
            self.end_headers()
            self.wfile.write(glb)

        def _authorized_local_request(self) -> bool:
            try:
                if not self.client_address[0].startswith("127.") and self.client_address[0] != "::1":
                    return False
            except (IndexError, AttributeError):
                return False
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urlparse(origin)
            try:
                origin_port = parsed.port
            except ValueError:
                return False
            return (
                parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                and origin_port == self.server.server_port
            )

        def _read_json(self, max_bytes: int = MAX_REQUEST_BYTES) -> dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid content length.") from exc
            if length < 0 or length > max_bytes:
                raise ValueError("Request is too large.")
            try:
                value = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Expected a UTF-8 JSON request.") from exc
            if not isinstance(value, dict):
                raise ValueError("Expected a JSON object.")
            return value

        def _require_local(self) -> bool:
            if self._authorized_local_request():
                return True
            self._send_json(403, {"error": "This local automation endpoint only accepts same-device requests."})
            return False

        def _require_loopback_host(self) -> bool:
            """Refuse requests that were not addressed to this server by a loopback name.

            A page on another site can point its own hostname at 127.0.0.1 (DNS rebinding).
            Its requests then reach this server looking same-origin, but they still carry
            the foreign hostname in the Host header.
            """
            try:
                parsed = urlparse(f"//{self.headers.get('Host', '')}")
                name, port = parsed.hostname, parsed.port
            except ValueError:
                name, port = None, None
            if name in {"localhost", "127.0.0.1", "::1"} and (port or 80) == self.server.server_port:
                return True
            self._send_json(403, {"error": "Weronika's memory is only available at this device's local address."})
            return False

        def do_GET(self) -> None:
            if not self._require_local():
                return
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"ok": True, "mode": "local-only"})
                return
            if parsed.path == "/api/automation/status":
                self._send_json(200, self._status_payload())
                return
            if parsed.path == "/api/watch/status":
                if watch is None:
                    self._send_json(200, {"watched": 0, "items": [], "watches": [], "busy": False})
                    return
                self._send_json(200, self._watch_status())
                return
            if parsed.path == "/api/watch/item":
                self._watch_item(parse_qs(parsed.query).get("draft_id", [""])[0])
                return
            if parsed.path == "/api/call/status":
                self._send_json(200, self._call_status())
                return
            if parsed.path == "/api/call/capabilities":
                self._send_json(200, self._call_capabilities())
                return
            if parsed.path == "/api/call/links":
                # Which phone is on the cable, and what it can be asked to do.
                try:
                    self._send_json(200, scan_links())
                except Exception as exc:
                    self._send_json(200, {"links": [], "summary": f"Phones could not be scanned: {exc}"})
                return
            if parsed.path == "/api/task/status":
                self._task_status(parse_qs(parsed.query).get("task_id", [""])[0])
                return
            if parsed.path == "/api/browse/capabilities":
                self._send_json(200, self._browse_capabilities())
                return
            if parsed.path == "/api/sites/catalog":
                self._send_json(200, self._sites().catalog())
                return
            if parsed.path == "/api/sites/search":
                query = parse_qs(parsed.query).get("q", [""])[0]
                self._send_json(200, {"sites": self._sites().search(query)})
                return
            if parsed.path == "/api/sites/tabs":
                self._send_json(200, {"tabs": self._sites().tabs()})
                return
            if parsed.path == "/api/news":
                query = parse_qs(parsed.query)
                try:
                    self._send_json(
                        200,
                        read_news(
                            query.get("topic", [""])[0],
                            query.get("lang", ["en"])[0],
                            query.get("country", ["IN"])[0],
                        ),
                    )
                except NewsError as exc:
                    self._send_json(502, {"error": str(exc)})
                return
            if parsed.path == "/api/skills":
                self._send_json(200, skills.catalog() if skills is not None else {"skills": [], "unavailable": []})
                return
            if parsed.path == "/api/blueprint/capabilities":
                payload = detect_hardware()
                payload["vrm_export"] = describe_vrm_limits()
                self._send_json(200, payload)
                return
            if parsed.path == "/api/memory":
                # The orb's conversation memory, mirrored to a file on this device.
                if not self._require_loopback_host():
                    return
                try:
                    self._send_json(200, {"memory": memory_store.load(), "path": str(memory_store.path)})
                except MemoryStoreError as exc:
                    self._send_json(400, {"error": str(exc)})
                return
            if parsed.path == "/api/workspace/status":
                self._send_json(200, {"connected": True, "workspace": "local", "browser": "Playwright Chromium"})
                return
            if parsed.path == "/api/workspace/files":
                self._send_json(200, {"root": str(local_workspace.root), "items": local_workspace.tree()})
                return
            if parsed.path == "/api/workspace/file":
                raw_path = parse_qs(parsed.query).get("path", [""])[0]
                try:
                    self._send_json(200, local_workspace.read(raw_path))
                except WorkspaceError as exc:
                    self._send_json(400, {"error": str(exc)})
                return
            if parsed.path == "/api/workspace/browser/tabs":
                self._send_json(200, {"tabs": adapters.browser.workspace_tabs()})
                return
            if parsed.path.startswith("/api/"):
                self._send_json(404, {"error": "Unknown local API route."})
                return
            relative = unquote(parsed.path).lstrip("/") or "weronika.html"
            requested = (WEB_ROOT / relative).resolve()
            if not requested.is_relative_to(WEB_ROOT.resolve()) or not requested.is_file():
                self.send_error(404)
                return
            data = requested.read_bytes()
            content_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            if not self._require_local():
                return
            try:
                path = urlparse(self.path).path
                if path == "/api/blueprint/reconstruct":
                    self._blueprint_reconstruct()
                    return
                if path == "/api/blueprint/vrm":
                    self._blueprint_vrm()
                    return
                workspace_routes = {
                    "/api/workspace/file",
                    "/api/workspace/run",
                    "/api/workspace/browser/open",
                    "/api/workspace/browser/activate",
                    "/api/workspace/browser/close",
                }
                if path == "/api/memory":
                    if not self._require_loopback_host():
                        return
                    max_bytes = MAX_MEMORY_REQUEST_BYTES
                elif path == "/api/open" or path.startswith("/api/apps/"):
                    # Starting programs is only for the page this worker serves itself.
                    if not self._require_loopback_host():
                        return
                    max_bytes = MAX_REQUEST_BYTES
                elif path in workspace_routes:
                    max_bytes = MAX_WORKSPACE_REQUEST_BYTES
                else:
                    max_bytes = MAX_REQUEST_BYTES
                data = self._read_json(max_bytes)
                if path in {
                    "/api/automation/prepare",
                    "/api/automation/recipient",
                    "/api/automation/confirm",
                    "/api/automation/cancel",
                    "/api/watch/add",
                    "/api/watch/scan",
                    "/api/watch/reply",
                    "/api/watch/choose",
                    "/api/watch/delegate",
                    "/api/watch/confirm",
                    "/api/watch/leave",
                    "/api/watch/hold",
                    "/api/watch/stop",
                    "/api/open",
                    "/api/apps/music",
                    "/api/task/start",
                    "/api/task/approve",
                    "/api/task/cancel",
                    "/api/task/retry",
                    "/api/browse/open",
                    "/api/sites/open",
                    "/api/sites/close",
                    "/api/sites/focus",
                    "/api/call/scan",
                    "/api/call/decide",
                    "/api/call/hear",
                    "/api/call/say",
                    "/api/call/handover",
                    "/api/call/end",
                    "/api/call/summary",
                    "/api/call/configure",
                    "/api/call/simulate",
                }:
                    self._automation_stream(path, data)
                    return
                if path == "/api/message":
                    result = self._prepare(data)
                elif path == "/api/recipient":
                    result = service.select_recipient(self._text(data, "draft_id"), self._text(data, "candidate_id"))
                    result = result.to_dict()
                elif path == "/api/confirm":
                    result = service.confirm_send(
                        self._text(data, "draft_id"), self._text(data, "confirmation")
                    ).to_dict()
                elif path == "/api/cancel":
                    result = service.cancel(self._text(data, "draft_id")).to_dict()
                elif path == "/api/memory":
                    result = memory_store.save(data.get("memory"))
                elif path == "/api/workspace/file":
                    relative_path = self._text(data, "path")
                    content = data.get("content")
                    if not isinstance(content, str):
                        raise WorkspaceError("File content must be text.")
                    result = local_workspace.save(
                        relative_path,
                        content,
                        overwrite=data.get("overwrite") is True,
                    )
                elif path == "/api/workspace/run":
                    result = local_workspace.run_python(
                        self._text(data, "path"), confirmed=data.get("confirmed") is True
                    )
                elif path == "/api/workspace/browser/open":
                    urls = data.get("urls")
                    result = {"tabs": adapters.browser.open_workspace_urls(urls)}
                elif path == "/api/workspace/browser/activate":
                    activated = adapters.browser.activate_workspace_tab(self._text(data, "tab_id"))
                    if not activated:
                        raise WorkspaceError("That browser tab is no longer open.")
                    result = {"activated": True}
                elif path == "/api/workspace/browser/close":
                    closed = adapters.browser.close_workspace_tab(self._text(data, "tab_id"))
                    if not closed:
                        raise WorkspaceError("That browser tab is no longer open.")
                    result = {"closed": True}
                else:
                    self._send_json(404, {"error": "Unknown local API route."})
                    return
                self._send_json(200, result)
            except (
                ValueError,
                MessagingError,
                ReplyWatchError,
                WorkspaceError,
                SiteError,
                MemoryStoreError,
                CallWatchError,
            ) as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception:
                self._send_json(500, {"error": "Weronika encountered an unexpected local error. Check the terminal output."})

        def _automation_stream(self, path: str, data: dict[str, object]) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache")
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.close_connection = True

            def emit(event: dict[str, object]) -> None:
                try:
                    payload = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def progress(message: str) -> None:
                emit({"type": "progress", "message": message})

            try:
                if path == "/api/automation/prepare":
                    plan = data.get("plan")
                    if not isinstance(plan, dict) or plan.get("intent") != "message":
                        raise ValueError("The cloud brain did not return an executable messaging plan.")
                    platform_raw = plan.get("platform")
                    if not isinstance(platform_raw, str):
                        raise ValueError("The plan must name a supported messaging platform.")
                    platform = Platform.parse(platform_raw)
                    recipient = plan.get("recipient")
                    message = plan.get("message")
                    if not isinstance(recipient, str) or not isinstance(message, str):
                        raise ValueError("The plan must include a recipient and exact message text.")
                    progress("The local worker accepted the validated messaging plan.")
                    result = service.prepare(platform, recipient, message, progress=progress)
                elif path == "/api/automation/recipient":
                    result = service.select_recipient(
                        self._text(data, "draft_id"),
                        self._text(data, "candidate_id"),
                        progress=progress,
                    )
                elif path == "/api/automation/confirm":
                    result = service.confirm_send(
                        self._text(data, "draft_id"),
                        self._text(data, "confirmation"),
                        progress=progress,
                    )
                elif path.startswith("/api/watch/"):
                    result = self._watch_stream(path, data, progress)
                elif path.startswith("/api/call/"):
                    result = self._call_stream(path, data, progress)
                elif path.startswith("/api/task/") or path == "/api/browse/open":
                    result = self._task_stream(path, data, progress)
                elif path.startswith("/api/sites/"):
                    result = self._sites_stream(path, data, progress)
                elif path == "/api/open" or path == "/api/apps/music":
                    result = self._open_stream(path, data, progress)
                else:
                    result = service.cancel(self._text(data, "draft_id"), progress=progress)
                payload = result.to_dict() if hasattr(result, "to_dict") else result
                emit({"type": "result", "workflow": payload})
            except (ValueError, MessagingError, ReplyWatchError, TaskError, SiteError, CallWatchError) as exc:
                emit({"type": "error", "message": str(exc)})
            except Exception:
                emit({"type": "error", "message": "The local automation worker encountered an unexpected error."})

        def _status_payload(self) -> dict[str, object]:
            payload: dict[str, object] = {
                "connected": True,
                "worker": "weronika-py",
                "mode": "loopback-only",
                "reply_watch": watch is not None,
                "call_watch": calls is not None,
                "skills": skills is not None,
                "browser_tasks": tasks is not None,
                "sites": True,
                "memory": True,
                "apps": True,
                "news": True,
            }
            if skills is not None:
                payload["skill_count"] = len(skills.catalog()["skills"])
            return payload

        def _call_status(self) -> dict[str, object]:
            if calls is None:
                return {
                    "available": False,
                    "items": [],
                    "active": [],
                    "awaiting": [],
                    "live": [],
                    "reminders": [],
                    "busy": False,
                    "settings": {},
                    "reason": "Call handling is not running in this worker.",
                }
            state = calls.list_state()
            state["available"] = True
            return state

        def _call_capabilities(self) -> dict[str, object]:
            if calls is None:
                return {
                    "available": False,
                    "channels": [],
                    "audio": {"available": False, "reason": "Call handling is not running in this worker."},
                    "telegram": telegram_note(),
                }
            report = calls.capabilities()
            report["available"] = True
            try:
                report["links"] = scan_links()
            except Exception as exc:
                report["links"] = {"links": [], "summary": f"Phones could not be scanned: {exc}"}
            return report

        def _watch_status(self) -> dict[str, object]:
            state = watch.list_state()
            return {
                "watched": len(state["watches"]),
                "watches": state["watches"],
                "items": state["items"],
                "busy": state["busy"],
            }

        def _watch_item(self, item_id: str) -> None:
            if watch is None or not item_id:
                self._send_json(400, {"error": "Choose a reply-watch item first."})
                return
            try:
                self._send_json(
                    200,
                    {
                        "item_id": item_id,
                        "prompt": watch.review_hint(item_id),
                    },
                )
            except ReplyWatchError as exc:
                self._send_json(400, {"error": str(exc)})

        def _browse_capabilities(self) -> dict[str, object]:
            payload: dict[str, object] = {
                "worker": "weronika-py",
                "engine": "visible browser automation",
                "actions": [spec.__dict__ for spec in ACTIONS.values()],
                "system_browsers": adapters.system_browsers() if hasattr(adapters, "system_browsers") else [],
                "local_planning": True,
            }
            return payload

        def _sites(self) -> SiteService:
            return SiteService(adapters.browser)

        def _open_stream(self, path: str, data: dict[str, object], progress) -> object:
            """“Open notepad and YouTube”, “play X on Spotify”: no cloud brain involved."""
            if path == "/api/apps/music":
                own_browser = None
                if tasks is not None:
                    own_browser = lambda url: tasks.open_in_own_browser(url, "")  # noqa: E731
                progress("Handing the song to Spotify…")
                return app_launcher.music(self._text(data, "service"), self._text(data, "query"), own_browser)
            raw = data.get("targets")
            if not isinstance(raw, list):
                raw = data.get("names")
            if isinstance(raw, str):
                raw = [raw]
            if not isinstance(raw, list):
                raw = [self._text(data, "name")]
            targets = [value for value in raw if isinstance(value, (str, dict))]
            progress("Opening it on this computer…")
            # "Open WhatsApp" shows Weronika's own signed-in window for that app.
            chat_window = None
            if callable(adapters):
                chat_window = lambda name: adapters(Platform.parse(name)).open_window()  # noqa: E731
            return OpenService(self._sites(), app_launcher, chat_window).open(targets)

        def _sites_stream(self, path: str, data: dict[str, object], progress) -> object:
            service_sites = self._sites()
            if path == "/api/sites/open":
                raw = data.get("names")
                if isinstance(raw, str):
                    names = [raw]
                elif isinstance(raw, list):
                    names = [str(value) for value in raw]
                else:
                    names = [self._text(data, "site")]
                progress("Opening the site in the Weronika browser window…")
                return service_sites.open(names)
            if path == "/api/sites/close":
                tab_id = self._text(data, "tab_id")
                name = self._text(data, "name") or self._text(data, "site")
                if not tab_id and not name:
                    raise SiteError("Which tab should Weronika close?")
                progress("Closing the tab…")
                return service_sites.close(tab_id, name)
            if path == "/api/sites/focus":
                tab_id = self._text(data, "tab_id")
                name = self._text(data, "name") or self._text(data, "site")
                progress("Switching tabs…")
                return service_sites.focus(tab_id, name)
            raise SiteError("Unknown site action.")

        def _task_status(self, task_id: str) -> None:
            if tasks is None:
                self._send_json(400, {"error": "Browser automation is not available in this worker."})
                return
            try:
                if task_id:
                    task = tasks.get(task_id)
                else:
                    task = tasks.live()
                self._send_json(200, {"task": task.to_dict() if task else None})
            except TaskError as exc:
                self._send_json(400, {"error": str(exc)})

        def _task_stream(self, path: str, data: dict[str, object], progress) -> object:
            if tasks is None:
                raise TaskError("Browser automation is not available in this worker.")
            if path == "/api/browse/open":
                url = str(data.get("url") or "").strip()
                preferred = str(data.get("browser") or "").strip()
                if not url:
                    raise TaskError("Which address should Weronika open?")
                detail = tasks.open_in_own_browser(url, preferred)
                if skills is not None:
                    skills.mark_used("browse")
                return {"stage": "done", "result": detail, "steps": [], "outcomes": [], "pending": None}
            if path == "/api/task/start":
                if skills is not None:
                    skills.mark_used("browse")
                task = tasks.start(data, progress=progress)
                return task.to_dict()
            if path == "/api/task/approve":
                phrase = self._text(data, "confirmation") or "confirm"
                task = tasks.approve(self._text(data, "task_id"), phrase, progress=progress)
                return task.to_dict()
            if path == "/api/task/retry":
                return self._retry_task(data, progress)
            return tasks.cancel(self._text(data, "task_id")).to_dict()

        def _retry_task(self, data: dict[str, object], progress) -> dict[str, object]:
            task = tasks.cancel(self._text(data, "task_id"))
            original = task.message
            plan = plan_local(original)
            if plan is None or not plan.steps:
                raise TaskError(
                    "That request needs the cloud brain to re-plan. Say it again and Weronika will ask the brain."
                )
            rebuilt = tasks.start(
                {
                    "message": original,
                    "steps": [step.to_dict() for step in plan.steps],
                    "context": plan.context,
                },
                progress=progress,
            )
            return rebuilt.to_dict()

        def _watch_stream(self, path: str, data: dict[str, object], progress) -> object:
            if watch is None:
                raise ReplyWatchError("Reply watch is not available in this worker.")
            if path == "/api/watch/add":
                result = watch.add_watch(data, progress=progress)
            elif path == "/api/watch/scan":
                scan = watch.scan(progress=progress)
                for note in scan.get("notes", []):
                    progress(f"Watch note · {note}")
                if skills is not None:
                    skills.mark_used("reply-watch-ask")
                return {
                    "stage": "scan",
                    **scan,
                    "prompt": _scan_prompt(scan),
                }
            elif path == "/api/watch/reply":
                reply = data.get("reply")
                if not isinstance(reply, str):
                    raise ReplyWatchError("Give Weronika the exact reply text first.")
                result = watch.propose(self._text(data, "draft_id"), reply, progress=progress)
                if skills is not None:
                    skills.mark_used("reply-watch-propose")
            elif path == "/api/watch/choose":
                result = watch.choose(
                    self._text(data, "draft_id"),
                    self._text(data, "candidate_id"),
                    progress=progress,
                )
            elif path == "/api/watch/delegate":
                # "Weronika replies": the user's answer for this one message is the approval.
                result = watch.delegate(self._text(data, "draft_id"), progress=progress)
                if skills is not None:
                    skills.mark_used("reply-watch-propose")
            elif path == "/api/watch/confirm":
                result = watch.confirm(
                    self._text(data, "draft_id"),
                    self._text(data, "confirmation"),
                    progress=progress,
                )
            elif path == "/api/watch/leave":
                result = watch.decline(self._text(data, "draft_id"), self._text(data, "reason"))
            elif path == "/api/watch/hold":
                result = watch.hold(self._text(data, "draft_id"))
            else:
                result = watch.remove_watch(self._text(data, "draft_id"))
            return result

        def _watch_route(self, data: dict[str, object]) -> dict[str, object]:
            intent = parse_watch_request(self._text(data, "text"))
            if watch is None or intent.action == "unhandled":
                return {"handled": False}
            if intent.prompt:
                return {"handled": True, "prompt": intent.prompt}
            if intent.action == "add_watch":
                result = watch.add_watch(
                    {
                        "platform": intent.platform.value if intent.platform else "",
                        "chat": intent.chat,
                        "all_chats": intent.all_chats,
                        "mode": intent.mode,
                        "rule": intent.rule,
                        "delay_seconds": intent.delay_seconds,
                        "reminder_seconds": intent.reminder_seconds,
                        "unanswered_after_seconds": intent.unanswered_after_seconds,
                    }
                )
                return {"handled": True, "kind": "watch", **result.to_dict()}
            if intent.action == "status":
                state = watch.list_state()
                return {
                    "handled": True,
                    "kind": "status",
                    "prompt": _status_prompt(state),
                    "items": state["items"],
                }
            if intent.action == "scan":
                scan = watch.scan()
                if skills is not None:
                    skills.mark_used("reply-watch-ask")
                return {"handled": True, "kind": "scan", **scan, "prompt": _scan_prompt(scan)}
            if intent.action == "stop_watch":
                return {"handled": True, "kind": "watch", **watch.remove_watch().to_dict()}
            # reply / leave_it / hold refer to the item Weronika last showed.
            item_id = self._text(data, "draft_id")
            if not item_id:
                return {
                    "handled": True,
                    "prompt": "I need the chat I flagged first. Say ‘who is waiting’ and choose one.",
                }
            if intent.action == "leave_it":
                return {"handled": True, "kind": "watch", **watch.decline(item_id, intent.reply).to_dict()}
            if intent.action == "hold":
                return {"handled": True, "kind": "watch", **watch.hold(item_id).to_dict()}
            return {
                "handled": True,
                "kind": "watch",
                **watch.propose(item_id, intent.reply).to_dict(),
            }

        def _call_stream(self, path: str, data: dict[str, object], progress) -> object:
            if calls is None:
                raise CallWatchError(
                    "Call handling is not running in this worker. Start it with start.bat, "
                    "or with `python start.py` on a machine that has the call support installed."
                )
            if path == "/api/call/configure":
                settings = calls.configure(data)
                return {"stage": "configure", "settings": settings, "prompt": _configure_prompt(settings)}
            if path == "/api/call/scan":
                scan = calls.scan(progress=progress)
                for note in scan.get("notes", []):
                    progress(f"Call note · {note}")
                if skills is not None:
                    skills.mark_used("call-watch-ask")
                return {"stage": "scan", **scan}
            if path == "/api/call/simulate":
                report = self._run_call_example(data, progress)
                if skills is not None:
                    skills.mark_used("call-example")
                return {"stage": "simulate", **report, "prompt": _example_prompt(report)}
            item_id = self._text(data, "item_id") or self._text(data, "draft_id")
            if path == "/api/call/decide":
                result = calls.decide(item_id, self._text(data, "decision"), progress=progress)
                if skills is not None:
                    skills.mark_used("call-handle")
                return result
            if path == "/api/call/hear":
                return calls.hear(item_id, self._text(data, "text"), progress=progress)
            if path == "/api/call/say":
                if data.get("read_secret") is True:
                    # The second step of reading a code aloud, after she refused the first.
                    return calls.retry_secret(progress=progress)
                return calls.dictate(item_id, self._text(data, "text"), progress=progress)
            if path == "/api/call/handover":
                return calls.handover(item_id, progress=progress)
            if path == "/api/call/end":
                return calls.end(
                    item_id,
                    self._text(data, "reason"),
                    goodbye=data.get("goodbye") is not False,
                    progress=progress,
                )
            if path == "/api/call/summary":
                return calls.prepare_summary_message(
                    item_id,
                    self._text(data, "platform") or "whatsapp",
                    self._text(data, "recipient"),
                    progress=progress,
                )
            raise CallWatchError("Unknown call route.")

        def _run_call_example(self, data: dict[str, object], progress):
            from .call_demo import list_examples, run_example

            if data.get("list") is True:
                return {
                    "simulated": True,
                    "examples": list_examples(),
                    "prompt": "These example calls can be run without a phone: "
                    + ", ".join(item["id"] for item in list_examples())
                    + ".",
                }
            speaker = None
            if data.get("speak") is True:
                from .call_audio import build_speaker

                candidate = build_speaker()
                speaker = candidate if candidate.describe().get("available") else None
                if speaker is None:
                    progress("No voice engine is installed, so the example is shown instead of spoken.")
            return run_example(
                self._text(data, "scenario"),
                decision=self._text(data, "decision"),
                owner=self._text(data, "owner") or calls.settings().get("owner", "Commander"),
                responder=calls.responder,
                speak=speaker is not None,
                speaker=speaker,
                progress=progress,
            )

        def _call_route(self, data: dict[str, object]) -> dict[str, object]:
            """Understand a call request typed or spoken in the orb, without the cloud brain."""
            text = self._text(data, "text")
            intent = parse_call_request(text)
            if calls is None or intent.action == "unhandled":
                return {"handled": False}
            action = intent.action
            if action == "enable":
                settings: dict[str, object] = {"enabled": True}
                if intent.channel is not None:
                    settings["channels"] = [intent.channel.value]
                if intent.route is not None:
                    settings["route"] = intent.route.value
                configured = calls.configure(settings)
                return {
                    "handled": True,
                    "kind": "call-setup",
                    "settings": configured,
                    "capabilities": calls.capabilities(),
                    "prompt": _enable_prompt(calls, configured),
                }
            if action == "disable":
                configured = calls.configure({"enabled": False})
                return {
                    "handled": True,
                    "kind": "call-setup",
                    "settings": configured,
                    "prompt": (
                        "Call handling is off. Weronika will not watch for calls, answer one, or ask "
                        "you about one until you say “handle my calls” again."
                    ),
                }
            if action == "scan":
                scan = calls.scan()
                if skills is not None:
                    skills.mark_used("call-watch-ask")
                return {"handled": True, "kind": "call-scan", **scan}
            if action == "status":
                state = calls.list_state()
                return {"handled": True, "kind": "call-status", **state, "prompt": _call_status_prompt(calls, state)}
            if action == "links":
                if skills is not None:
                    skills.mark_used("call-setup")
                report = scan_links()
                report["capabilities"] = calls.capabilities()
                return {"handled": True, "kind": "call-links", **report, "prompt": _links_prompt(report)}
            if action == "simulate":
                report = self._run_call_example(
                    {"scenario": _scenario_for(text, intent.channel)}, None
                )
                if skills is not None:
                    skills.mark_used("call-example")
                return {"handled": True, "kind": "call-example", **report, "prompt": _example_prompt(report)}
            if action == "summary_send":
                current = calls.current()
                if current is None:
                    return {
                        "handled": True,
                        "prompt": "There is no call summary to send yet. Weronika writes one when she has handled a call.",
                    }
                if not intent.recipient:
                    return {
                        "handled": True,
                        "prompt": "Who should get the call summary? For example: “send the summary on WhatsApp to Boss”.",
                    }
                draft = calls.prepare_summary_message(
                    current.id, intent.platform or "whatsapp", intent.recipient
                )
                return {
                    "handled": True,
                    "kind": "call-summary",
                    **draft,
                    "prompt": (
                        f"The call summary is prepared for {intent.recipient}. "
                        "Nothing is sent until you say “confirm send”."
                    ),
                }

            # Everything below is about the call that is ringing or live right now.
            current = calls.current()
            if current is None:
                return {
                    "handled": True,
                    "prompt": (
                        "No call is ringing or live right now, so there is nothing to decide. "
                        "Say “scan calls” and Weronika will look again."
                    ),
                }
            if action == "decide":
                result = calls.decide(current.id, intent.decision)
                if skills is not None and intent.decision == "weronika":
                    skills.mark_used("call-handle")
                return {"handled": True, "kind": "call", **result.to_dict()}
            if action == "read_secret":
                result = calls.retry_secret()
                return {"handled": True, "kind": "call", **result.to_dict()}
            if action == "handover":
                result = calls.handover(current.id)
                return {"handled": True, "kind": "call", **result.to_dict()}
            if action == "end":
                result = calls.end(current.id, "You asked Weronika to end the call.")
                return {"handled": True, "kind": "call", **result.to_dict()}
            if action == "hear":
                result = calls.hear(current.id, intent.text)
                return {"handled": True, "kind": "call", **result.to_dict()}
            if action == "dictate":
                result = calls.dictate(current.id, intent.text)
                return {"handled": True, "kind": "call", **result.to_dict()}
            return {"handled": False}

        @staticmethod
        def _text(data: dict[str, object], key: str) -> str:
            value = data.get(key, "")
            return value.strip() if isinstance(value, str) else ""

        def _prepare(self, data: dict[str, object]) -> dict[str, object]:
            text = self._text(data, "text")
            if not text:
                raise ValueError("Enter a message request first.")
            # A short answer like "you handle it" or "kaat do" only means something while
            # a call is ringing or live, so it is routed locally then and left to the cloud
            # brain at every other moment.
            if has_call_intent(text) or (calls is not None and calls.current() is not None):
                handled_call = self._call_route(data)
                if handled_call.get("handled"):
                    return handled_call
            if has_watch_intent(text):
                watched = self._watch_route(data)
                if watched.get("handled"):
                    return watched
            parsed = parse_message_request(text)
            if not parsed.handled:
                return {
                    "handled": False,
                    "prompt": "Try a clear command such as: Send a WhatsApp message to Boss saying I will be on leave tomorrow.",
                }
            if parsed.prompt:
                return {"handled": True, "prompt": parsed.prompt, "platform": parsed.platform.value if parsed.platform else None}
            assert parsed.platform is not None
            return service.prepare(parsed.platform, parsed.recipient, parsed.message).to_dict()

    return Handler


def _configure_prompt(settings: dict[str, object]) -> str:
    channels = ", ".join(str(item) for item in settings.get("channels") or []) or "phone (SIM), WhatsApp"
    state = "on" if settings.get("enabled") else "off"
    return (
        f"Call handling is {state} for: {channels}. "
        "Weronika asks you about each call before she answers, and she tells the caller she is an AI."
    )


def _enable_prompt(service, settings: dict[str, object]) -> str:
    """What the orb says when you ask her to handle your calls."""
    report = service.capabilities()
    ready = [
        entry
        for entry in report.get("channels") or []
        if isinstance(entry, dict) and entry.get("available")
    ]
    audio = report.get("audio") or {}
    lines = [
        "Weronika will watch for incoming calls and ask you about each one: "
        "“Are you able to handle the call, or should I take it?” "
        "She never answers without asking, and she always tells the caller she is an AI."
    ]
    if ready:
        lines.append(
            "Ready now: "
            + ", ".join(str(entry.get("channel_display") or entry.get("channel")) for entry in ready)
            + "."
        )
    else:
        reasons = [
            str(entry.get("reason"))
            for entry in report.get("channels") or []
            if isinstance(entry, dict) and entry.get("reason")
        ]
        lines.append(
            "No channel is ready yet" + (f": {reasons[0]}" if reasons else "") + "."
        )
    if not audio.get("available"):
        lines.append(f"Call audio: {audio.get('reason') or 'no route available'}.")
    elif not audio.get("automatic"):
        speech = (audio.get("speech") or {}).get("reason", "")
        lines.append(
            f"Audio route: {audio.get('route')}. {speech or 'Typed mode: you tell her what the caller said.'}"
        )
    else:
        lines.append(f"Audio route: {audio.get('route')} — she can listen and speak by herself.")
    lines.append(telegram_note())
    lines.append('Say “show me an example call” to watch the whole flow without a phone ringing.')
    return "\n".join(lines)


def _call_status_prompt(service, state: dict[str, object]) -> str:
    settings = state.get("settings") or {}
    if not settings.get("enabled", True):
        return "Call handling is off. Say “handle my calls” to switch it on."
    awaiting = state.get("awaiting") or []
    live = state.get("live") or []
    if awaiting:
        first = awaiting[0]
        return service.review_hint(str(first["item_id"]))
    if live:
        first = live[0]
        turns = first.get("transcript") or []
        tail = " / ".join(
            f"{'Caller' if turn['speaker'] == 'caller' else 'Weronika'}: {turn['text']}"
            for turn in list(turns)[-2:]
            if isinstance(turn, dict)
        )
        return f"A call with {first.get('caller')} is live. {tail}"
    items = state.get("items") or []
    handled = [item for item in items if item.get("decision") == "weronika"]
    if not items:
        return (
            "No calls have come in since Weronika started watching. "
            "She asks about each one; she never answers on her own."
        )
    return (
        f"{len(items)} call(s) recorded, {len(handled)} handled by Weronika. "
        "Nothing is ringing right now."
    )


def _links_prompt(report: dict[str, object]) -> str:
    lines = [str(report.get("summary") or "")]
    for link in report.get("links") or []:
        if not isinstance(link, dict):
            continue
        name = link.get("name") or link.get("kind")
        state = "linked" if link.get("connected") else "not linked"
        lines.append(f"— {name} ({state}): {link.get('reason') or 'ready'}")
    audio = (report.get("capabilities") or {}).get("audio") or {}
    if audio:
        lines.append(
            f"Audio route: {audio.get('route', 'none')} — "
            f"{audio.get('reason') or ('she can listen and speak by herself' if audio.get('automatic') else 'typed mode')}"
        )
    lines.append(telegram_note())
    return "\n".join(line for line in lines if line)


def _scenario_for(text: str, channel) -> str:
    """Which example a chat request should run.

    A named example wins ("show me an example call, the otp-scam one"); otherwise the
    channel decides, and a request with neither gets the default example.
    """
    from .call_demo import EXAMPLES, example_for_channel

    lowered = " ".join(str(text or "").split()).casefold()
    for scenario_id in EXAMPLES:
        if scenario_id in lowered or scenario_id.replace("-", " ") in lowered:
            return scenario_id
    return example_for_channel(channel)


def _example_prompt(report: dict[str, object]) -> str:
    if report.get("error"):
        return str(report["error"])
    examples = report.get("examples")
    if examples:
        # A listing, not a run: name each example and what it demonstrates.
        lines = ["These example calls run without a phone, a browser session, or a microphone:"]
        for entry in list(examples)[:8]:
            if not isinstance(entry, dict):
                continue
            lines.append(f"· {entry.get('id')} — {entry.get('title')} ({entry.get('channel')})")
            if entry.get("shows"):
                lines.append(f"    shows {entry['shows']}")
        lines.append(
            "Say “show me an example call”, or name the channel: “show me an example of a WhatsApp call”."
        )
        return "\n".join(lines)
    scenario = report.get("scenario") or {}
    lines = [
        f"Example call · {scenario.get('title', '')}. {report.get('note', '')}",
        f"She asked you: “{report.get('question', '')}”",
    ]
    transcript = report.get("transcript") or []
    for turn in list(transcript)[:8]:
        if not isinstance(turn, dict):
            continue
        who = "Caller" if turn.get("speaker") == "caller" else ("You" if turn.get("speaker") == "you" else "Weronika")
        lines.append(f"{who}: {turn.get('text')}")
    if len(transcript) > 8:
        lines.append(f"…and {len(transcript) - 8} more line(s).")
    for flag in list(report.get("flags") or [])[:4]:
        lines.append(f"Flagged: {flag}")
    if report.get("summary"):
        lines.append("")
        lines.append(str(report["summary"]))
    return "\n".join(lines)


def _scan_prompt(scan: dict[str, object]) -> str:
    detected = scan.get("detected") or []
    if isinstance(detected, list) and detected:
        return f"{len(detected)} chat(s) are waiting for your reply. Here is the first one."
    notes = scan.get("notes") or []
    if notes:
        return "Weronika could not read every watched chat. " + str(notes[0])
    return "Nobody is waiting on the chats you asked me to watch."


def _status_prompt(state: dict[str, object]) -> str:
    watches = state.get("watches") or []
    items = state.get("items") or []
    if not watches:
        return (
            "No chats are being watched yet. Say, for example, "
            "“Watch my WhatsApp chat with Boss.”"
        )
    lines = [
        f"Watching {len(watches)} chat(s): "
        + ", ".join(f"{entry['platform'].title()} · {entry['chat_name']}" for entry in watches)
    ]
    waiting = [
        entry
        for entry in items
        if isinstance(entry, dict) and entry.get("state") == "awaiting_user"
    ]
    if not waiting:
        lines.append("Nobody is waiting for a reply right now.")
        return "\n".join(lines)
    for entry in waiting:
        message = entry.get("message") or {}
        text = message.get("text") if isinstance(message, dict) else ""
        lines.append(f"— {entry.get('platform', '').title()} · {entry.get('chat_name')}: “{text}”")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Weronika's local, confirmation-first messaging UI.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile-dir", type=Path, default=None, help="Override the local persistent browser-profile directory.")
    parser.add_argument("--open-browser", action="store_true", help="Open the local messaging page in the default browser.")
    parser.add_argument(
        "--brain-endpoint",
        default=None,
        help=(
            "Cloud-brain URL used only to suggest reply-watch wording. "
            "Use 'off' to keep every suggestion on this device."
        ),
    )
    parser.add_argument(
        "--no-calls",
        dest="calls",
        action="store_false",
        help="Do not watch for incoming calls at all.",
    )
    parser.add_argument(
        "--call-audio-route",
        default="",
        help="Audio route for calls: speaker_mic, bluetooth, aux, or auto (default).",
    )
    parser.add_argument(
        "--speech-engine",
        default="auto",
        help="Call transcription: whisper, vosk, typed, or auto (default).",
    )
    parser.add_argument(
        "--owner-name",
        default="Commander",
        help="How Weronika refers to you when she speaks to a caller.",
    )
    parser.set_defaults(calls=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    service, adapters, watch, skills, tasks = create_messaging_service(
        args.profile_dir, brain_endpoint=args.brain_endpoint
    )
    calls = None
    if args.calls:
        try:
            calls = create_call_service(
                brain_endpoint=args.brain_endpoint,
                owner=args.owner_name,
                audio_route=args.call_audio_route,
                speech_engine=args.speech_engine,
                messaging=service,
                browser=getattr(adapters, "browser", None),
            )
        except Exception as exc:  # pragma: no cover - depends on local audio/adb install
            calls = None
            print(f"Call handling could not start ({exc}); everything else still works.")
    server = LocalServer(
        ("127.0.0.1", args.port),
        make_handler(service, adapters, watch=watch, skills=skills, tasks=tasks, calls=calls),
    )
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Weronika local messaging is running at {url}")
    print("It is loopback-only; browser sessions and message drafts stay on this device.")
    print("Reply watch reads only the chats you name, and every send still needs your confirmation.")
    print("Weronika's conversation memory is kept in ~/.weronika/memory on this device.")
    if calls is not None:
        audio = calls.capabilities()["audio"]
        print("Call handling is watching: she asks you about each call, and tells the caller she is an AI.")
        if audio.get("automatic"):
            print(f"Call audio: {audio.get('route')} — she can listen and speak by herself.")
        else:
            print(
                "Call audio: typed mode"
                + (f" ({audio.get('reason')})" if audio.get("reason") else "")
                + " — run setup-calls.bat to let her listen and speak."
            )
        print("Call audio is never written to disk; only the words are kept, in memory.")
    if args.open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Weronika local messaging.")
    finally:
        server.server_close()
        adapters.close()


if __name__ == "__main__":
    main()
