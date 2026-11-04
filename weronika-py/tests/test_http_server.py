import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import patch

from weronika_agent.blueprint import BlueprintError
from weronika_agent.http_server import LocalServer, make_handler
from weronika_agent.models import Platform, VisibleContact
from weronika_agent.reply_watch import ChatReading, ChatSnapshot, IncomingMessage, ReplyWatchService
from weronika_agent.watch_skills import SkillRegistry
from weronika_agent.workflow import MessagingService
from weronika_agent.workspace import LocalWorkspace


class FakeAdapter:
    def __init__(self):
        self.sent = []

    def find_recipients(self, query):
        return [VisibleContact("0:0", "Boss")]

    def open_chat_and_draft(self, candidate, message):
        pass

    def send_and_verify(self, message):
        self.sent.append(message)
        return True

    def clear_draft_if_unchanged(self, message):
        return True


class FakeActivity:
    """Stands in for the visible WhatsApp/Telegram browser window."""

    def __init__(self):
        self.chats = [ChatSnapshot(Platform.WHATSAPP, "Boss")]
        self.last = ""

    def list_chats(self, platform):
        return list(self.chats)

    def read_latest(self, platform, chat_name):
        return getattr(self, "reading", ChatReading(chat_name=chat_name, messages=(), last_is_incoming=None))

    def deliver(self, text, sender="Boss"):
        self.last = text
        self.reading = ChatReading(
            chat_name="Boss",
            messages=(
                IncomingMessage(
                    platform=Platform.WHATSAPP,
                    chat_name="Boss",
                    message_id="m1",
                    text=text,
                    sender=sender,
                ),
            ),
            last_is_incoming=True,
        )

    def __call__(self, platform):
        return self


class FakeBrowser:
    def __init__(self):
        self.tabs = []

    def workspace_tabs(self):
        return self.tabs

    def open_workspace_urls(self, urls):
        self.tabs = [{"id": str(index), "url": url, "title": ""} for index, url in enumerate(urls)]
        return self.tabs

    def activate_workspace_tab(self, tab_id):
        return any(tab["id"] == tab_id for tab in self.tabs)

    def close_workspace_tab(self, tab_id):
        before = len(self.tabs)
        self.tabs = [tab for tab in self.tabs if tab["id"] != tab_id]
        return len(self.tabs) < before


class LocalHttpServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = LocalWorkspace(self.temp.name)
        self.adapter = FakeAdapter()
        self.browser = FakeBrowser()
        self.service = MessagingService(lambda _: self.adapter)
        self.adapters = SimpleNamespace(browser=self.browser)
        self.activity = FakeActivity()
        self.watch = ReplyWatchService(self.activity, self.service, suggester=lambda chat, text: "")
        self.skills = SkillRegistry()
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                self.service,
                self.adapters,
                self.workspace,
                watch=self.watch,
                skills=self.skills,
            ),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, payload=None, origin=None):
        headers = {}
        data = None
        method = "GET"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        if origin is not None:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        return urllib.request.urlopen(request, timeout=5)

    @staticmethod
    def events(response):
        result = []
        for block in response.read().decode("utf-8").split("\n\n"):
            if block.startswith("data: "):
                result.append(json.loads(block[6:]))
        return result

    def test_blueprint_capabilities_reports_hardware_and_optional_model_state(self):
        with patch(
            "weronika_agent.hardware.blueprint_status",
            return_value={"model": "TripoSR", "available": False},
        ):
            with self.request("/api/blueprint/capabilities") as response:
                capabilities = json.load(response)
        self.assertIn("platform", capabilities)
        self.assertGreaterEqual(capabilities["cpu_threads"], 1)
        self.assertIn("nvidia_gpus", capabilities)
        self.assertEqual(capabilities["model_runtime"], "not-configured")
        self.assertFalse(capabilities["blueprint_model"]["available"])

    def test_blueprint_reconstruction_returns_local_glb_bytes(self):
        glb = b"glTF" + bytes(16)
        request = urllib.request.Request(
            self.base + "/api/blueprint/reconstruct",
            data=b"image bytes",
            headers={"Content-Type": "image/jpeg", "Origin": self.base},
            method="POST",
        )
        with patch(
            "weronika_agent.http_server.reconstruct_photo",
            return_value=(glb, "created locally"),
        ):
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.headers.get_content_type(), "model/gltf-binary")
                self.assertEqual(response.read(), glb)

    def test_blueprint_reconstruction_reports_when_model_is_not_installed(self):
        request = urllib.request.Request(
            self.base + "/api/blueprint/reconstruct",
            data=b"image bytes",
            headers={"Content-Type": "image/jpeg", "Origin": self.base},
            method="POST",
        )
        error = BlueprintError("Install the local model first.", status_code=503)
        with patch("weronika_agent.http_server.reconstruct_photo", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 503)
        self.assertIn("Install the local model", raised.exception.read().decode("utf-8"))

    def test_root_serves_original_orb_and_worker_status(self):
        with self.request("/") as response:
            html = response.read().decode("utf-8")
        self.assertIn('id="orbRoot"', html)
        self.assertIn("weronika-commands.js", html)
        with self.request("/api/automation/status") as response:
            status = json.load(response)
        self.assertTrue(status["connected"])
        self.assertEqual(status["worker"], "weronika-py")

    def test_local_plan_streams_progress_and_requires_confirmation(self):
        plan = {
            "intent": "message",
            "platform": Platform.WHATSAPP.value,
            "recipient": "Boss",
            "message": "I will be on leave tomorrow",
        }
        with self.request("/api/automation/prepare", {"plan": plan}, origin=self.base) as response:
            events = self.events(response)
        self.assertTrue(any(event["type"] == "progress" for event in events))
        workflow = next(event["workflow"] for event in events if event["type"] == "result")
        self.assertEqual(workflow["stage"], "awaiting_confirmation")
        self.assertEqual(self.adapter.sent, [])

        payload = {"draft_id": workflow["draft_id"], "confirmation": "confirm send"}
        with self.request("/api/automation/confirm", payload, origin=self.base) as response:
            sent_events = self.events(response)
        sent = next(event["workflow"] for event in sent_events if event["type"] == "result")
        self.assertEqual(sent["stage"], "sent")
        self.assertEqual(self.adapter.sent, ["I will be on leave tomorrow"])

    def test_workspace_api_saves_reads_and_only_runs_after_explicit_confirmation(self):
        with self.request("/api/workspace/file", {"path": "hello.py", "content": "print('ok')", "overwrite": False}, origin=self.base) as response:
            self.assertTrue(json.load(response)["saved"])
        with self.request("/api/workspace/files") as response:
            self.assertEqual(json.load(response)["items"][0]["path"], "hello.py")
        with self.request("/api/workspace/file?path=hello.py") as response:
            self.assertEqual(json.load(response)["content"], "print('ok')")
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/workspace/run", {"path": "hello.py", "confirmed": False}, origin=self.base)
        self.assertEqual(raised.exception.code, 400)
        with self.request("/api/workspace/run", {"path": "hello.py", "confirmed": True}, origin=self.base) as response:
            self.assertEqual(json.load(response)["stdout"].strip(), "ok")

    def test_browser_workspace_api_exposes_and_manages_multiple_tabs(self):
        with self.request("/api/workspace/browser/open", {"urls": ["http://localhost:5173/", "https://example.com"]}, origin=self.base) as response:
            tabs = json.load(response)["tabs"]
        self.assertEqual(len(tabs), 2)
        with self.request("/api/workspace/browser/tabs") as response:
            self.assertEqual(len(json.load(response)["tabs"]), 2)
        with self.request("/api/workspace/browser/activate", {"tab_id": "0"}, origin=self.base) as response:
            self.assertTrue(json.load(response)["activated"])
        with self.request("/api/workspace/browser/close", {"tab_id": "0"}, origin=self.base) as response:
            self.assertTrue(json.load(response)["closed"])

    def test_status_reports_reply_watch_and_skills(self):
        with self.request("/api/automation/status") as response:
            status = json.load(response)
        self.assertTrue(status["reply_watch"])
        self.assertTrue(status["skills"])
        self.assertGreaterEqual(status["skill_count"], 5)

    def test_skills_catalog_lists_only_implemented_capabilities(self):
        with self.request("/api/skills") as response:
            catalog = json.load(response)
        ids = {skill["id"] for skill in catalog["skills"]}
        self.assertIn("reply-watch-propose", ids)
        self.assertIn("send-message", ids)
        reasons = {entry["id"] for entry in catalog["unavailable"]}
        self.assertIn("auto-send", reasons)
        self.assertIn("calls", reasons)

    def test_reply_watch_adds_scans_and_prepares_a_confirmed_reply(self):
        with self.request(
            "/api/watch/add",
            {"platform": "whatsapp", "chat": "Boss", "mode": "ask", "unanswered_after_seconds": 0},
            origin=self.base,
        ) as response:
            added = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertEqual(added["state"], "new")
        self.assertIn("Watching", added["prompt"])

        self.activity.deliver("Are you coming today?")
        with self.request("/api/watch/scan", {}, origin=self.base) as response:
            scan = next(event["workflow"] for event in self.events(response) if event["type"] == "result")
        self.assertEqual(len(scan["detected"]), 1)
        item_id = scan["detected"][0]["item_id"]
        self.assertEqual(self.adapter.sent, [])

        with self.request(
            "/api/watch/reply",
            {"draft_id": item_id, "reply": "I won't be able to come today"},
            origin=self.base,
        ) as response:
            prepared = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertEqual(prepared["state"], "awaiting_review")
        self.assertIn("NOT been sent", prepared["prompt"])
        self.assertEqual(self.adapter.sent, [])

        with self.request(
            "/api/watch/confirm",
            {"draft_id": item_id, "confirmation": "confirm send"},
            origin=self.base,
        ) as response:
            sent = next(event["workflow"] for event in self.events(response) if event["type"] == "result")
        self.assertEqual(sent["state"], "sent")
        self.assertEqual(self.adapter.sent, ["I won't be able to come today"])

    def test_watch_status_and_leave_it_routes(self):
        with self.request(
            "/api/watch/add",
            {"platform": "whatsapp", "chat": "Boss", "mode": "ask", "unanswered_after_seconds": 0},
            origin=self.base,
        ) as response:
            self.events(response)
        self.activity.deliver("Hello?")
        with self.request("/api/watch/scan", {}, origin=self.base) as response:
            scan = next(event["workflow"] for event in self.events(response) if event["type"] == "result")
        item_id = scan["detected"][0]["item_id"]

        with self.request("/api/watch/status") as response:
            status = json.load(response)
        self.assertEqual(status["watched"], 1)
        self.assertEqual(status["items"][0]["state"], "awaiting_user")

        with self.request(
            "/api/watch/leave", {"draft_id": item_id}, origin=self.base
        ) as response:
            left = next(event["workflow"] for event in self.events(response) if event["type"] == "result")
        self.assertEqual(left["state"], "declined")
        self.assertEqual(self.adapter.sent, [])

    def test_plain_message_route_routes_watch_phrases(self):
        with self.request(
            "/api/message", {"text": "Watch my WhatsApp chat with Boss"}, origin=self.base
        ) as response:
            result = json.load(response)
        self.assertTrue(result["handled"])
        self.assertEqual(result["kind"], "watch")
        self.assertEqual(result["chat_name"], "Boss")

    def test_cross_origin_is_rejected(self):
        request = urllib.request.Request(
            self.base + "/api/automation/status",
            headers={"Origin": "https://example.com"},
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
