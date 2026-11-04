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

from .blueprint import BlueprintError, MAX_IMAGE_BYTES, reconstruct_photo
from .hardware import detect_hardware
from .intents import parse_message_request
from .models import Platform
from .reply_watch import ReplyWatchError
from .service import create_messaging_service
from .watch_intents import has_watch_intent, parse_watch_request
from .workflow import MessagingError
from .workspace import LocalWorkspace, WorkspaceError

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "public"
MAX_REQUEST_BYTES = 16_384
MAX_WORKSPACE_REQUEST_BYTES = 1_100_000


class LocalServer(HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(service, adapters, workspace: LocalWorkspace | None = None, watch=None, skills=None):
    local_workspace = workspace or LocalWorkspace()

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
            if parsed.path == "/api/skills":
                self._send_json(200, skills.catalog() if skills is not None else {"skills": [], "unavailable": []})
                return
            if parsed.path == "/api/blueprint/capabilities":
                self._send_json(200, detect_hardware())
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
                workspace_routes = {
                    "/api/workspace/file",
                    "/api/workspace/run",
                    "/api/workspace/browser/open",
                    "/api/workspace/browser/activate",
                    "/api/workspace/browser/close",
                }
                data = self._read_json(MAX_WORKSPACE_REQUEST_BYTES if path in workspace_routes else MAX_REQUEST_BYTES)
                if path in {
                    "/api/automation/prepare",
                    "/api/automation/recipient",
                    "/api/automation/confirm",
                    "/api/automation/cancel",
                    "/api/watch/add",
                    "/api/watch/scan",
                    "/api/watch/reply",
                    "/api/watch/choose",
                    "/api/watch/confirm",
                    "/api/watch/leave",
                    "/api/watch/hold",
                    "/api/watch/stop",
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
            except (ValueError, MessagingError, ReplyWatchError, WorkspaceError) as exc:
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
                else:
                    result = service.cancel(self._text(data, "draft_id"), progress=progress)
                payload = result.to_dict() if hasattr(result, "to_dict") else result
                emit({"type": "result", "workflow": payload})
            except (ValueError, MessagingError, ReplyWatchError) as exc:
                emit({"type": "error", "message": str(exc)})
            except Exception:
                emit({"type": "error", "message": "The local automation worker encountered an unexpected error."})

        def _status_payload(self) -> dict[str, object]:
            payload: dict[str, object] = {
                "connected": True,
                "worker": "weronika-py",
                "mode": "loopback-only",
                "reply_watch": watch is not None,
                "skills": skills is not None,
            }
            if skills is not None:
                payload["skill_count"] = len(skills.catalog()["skills"])
            return payload

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

        @staticmethod
        def _text(data: dict[str, object], key: str) -> str:
            value = data.get(key, "")
            return value.strip() if isinstance(value, str) else ""

        def _prepare(self, data: dict[str, object]) -> dict[str, object]:
            text = self._text(data, "text")
            if not text:
                raise ValueError("Enter a message request first.")
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
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    service, adapters, watch, skills = create_messaging_service(
        args.profile_dir, brain_endpoint=args.brain_endpoint
    )
    server = LocalServer(
        ("127.0.0.1", args.port), make_handler(service, adapters, watch=watch, skills=skills)
    )
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Weronika local messaging is running at {url}")
    print("It is loopback-only; browser sessions and message drafts stay on this device.")
    print("Reply watch reads only the chats you name, and every send still needs your confirmation.")
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
