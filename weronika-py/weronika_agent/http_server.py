"""Loopback-only static UI and JSON API for local messaging automation."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .intents import parse_message_request
from .models import Platform
from .service import create_messaging_service
from .workflow import MessagingError

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "public"
MAX_REQUEST_BYTES = 16_384


class LocalServer(HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(service, adapters):
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

        def _read_json(self) -> dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid content length.") from exc
            if length < 0 or length > MAX_REQUEST_BYTES:
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
                self._send_json(200, {"connected": True, "worker": "weronika-py", "mode": "loopback-only"})
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
                data = self._read_json()
                path = urlparse(self.path).path
                if path in {
                    "/api/automation/prepare",
                    "/api/automation/recipient",
                    "/api/automation/confirm",
                    "/api/automation/cancel",
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
                else:
                    self._send_json(404, {"error": "Unknown local API route."})
                    return
                self._send_json(200, result)
            except (ValueError, MessagingError) as exc:
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
                else:
                    result = service.cancel(self._text(data, "draft_id"), progress=progress)
                emit({"type": "result", "workflow": result.to_dict()})
            except (ValueError, MessagingError) as exc:
                emit({"type": "error", "message": str(exc)})
            except Exception:
                emit({"type": "error", "message": "The local automation worker encountered an unexpected error."})

        @staticmethod
        def _text(data: dict[str, object], key: str) -> str:
            value = data.get(key, "")
            return value.strip() if isinstance(value, str) else ""

        def _prepare(self, data: dict[str, object]) -> dict[str, object]:
            text = self._text(data, "text")
            if not text:
                raise ValueError("Enter a message request first.")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Weronika's local, confirmation-first messaging UI.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile-dir", type=Path, default=None, help="Override the local persistent browser-profile directory.")
    parser.add_argument("--open-browser", action="store_true", help="Open the local messaging page in the default browser.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    service, adapters = create_messaging_service(args.profile_dir)
    server = LocalServer(("127.0.0.1", args.port), make_handler(service, adapters))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Weronika local messaging is running at {url}")
    print("It is loopback-only; browser sessions and message drafts stay on this device.")
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
