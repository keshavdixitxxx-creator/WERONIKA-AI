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
from weronika_agent.task_service import TaskService
from weronika_agent.tasks import PageReading
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


class FakeWeb:
    """Stands in for the visible Chromium window used for web tasks."""

    def __init__(self):
        self.calls = []
        self.submitted = []

    def search(self, query):
        self.calls.append(("search", query))
        return f"https://duckduckgo.com/?q={query}"

    def open_url(self, url):
        self.calls.append(("open_url", url))
        return url

    def click_result(self, index=0):
        self.calls.append(("open_result", str(index)))
        return "Example — https://example.com/"

    def read_page(self):
        self.calls.append(("read_page", ""))
        return PageReading("https://example.com/", "Example", "Example article text.")

    def play(self, query, *, context=""):
        self.calls.append(("play_video", query))
        return f"Playing on YouTube: “{query}”", "https://www.youtube.com/watch?v=1"

    def prepare_account_action(self, action, text, context):
        self.calls.append(("prepare", f"{action}:{text}"))
        return f"{action} typed: {text}"

    def submit_account_action(self, action, text):
        self.submitted.append(text)
        return SimpleNamespace(submitted=True, detail=f"{action} submitted")

    def open_in_system_browser(self, url, preferred=""):
        self.calls.append(("system", f"{preferred}|{url}"))
        return f"Opened in Microsoft Edge: {url}"


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


class SiteRouteTests(unittest.TestCase):
    """The site registry endpoints on a real loopback server with a fake browser."""

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
        self.web = FakeWeb()
        self.tasks = TaskService(lambda: self.web)
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                self.service,
                self.adapters,
                self.workspace,
                watch=self.watch,
                skills=self.skills,
                tasks=self.tasks,
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

    def get(self, path):
        with urllib.request.urlopen(f"{self.base}{path}", timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def post(self, path, payload):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
        events = [
            line[len("data: "):]
            for line in body.splitlines()
            if line.startswith("data: ")
        ]
        return [json.loads(event) for event in events]

    def test_catalog_lists_sites_and_refusals(self):
        status, data = self.get("/api/sites/catalog")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["count"], 80)
        self.assertTrue(data["refused"])
        self.assertIn("google", data["categories"])
        self.assertEqual(data["tabs"], [])

    def test_search_returns_matching_sites(self):
        status, data = self.get("/api/sites/search?q=drive")
        self.assertEqual(status, 200)
        names = [site["name"] for site in data["sites"]]
        self.assertIn("Google Drive", names)
        self.assertIn("OneDrive", names)

    def test_open_creates_tabs_in_the_managed_browser(self):
        events = self.post("/api/sites/open", {"names": ["radio garden", "github"]})
        result = next(event for event in events if event["type"] == "result")["workflow"]
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(self.browser.tabs), 2)
        status, data = self.get("/api/sites/tabs")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["tabs"]), 2)

    def test_open_accepts_a_single_name_string(self):
        events = self.post("/api/sites/open", {"site": "youtube"})
        result = next(event for event in events if event["type"] == "result")["workflow"]
        self.assertEqual(result["count"], 1)
        self.assertEqual(self.browser.tabs[0]["url"], "https://www.youtube.com/")

    def test_refused_site_returns_a_stated_reason(self):
        events = self.post("/api/sites/open", {"names": ["vegamovies"]})
        error = next(event for event in events if event["type"] == "error")
        self.assertIn("will not automate", error["message"])
        self.assertEqual(self.browser.tabs, [])

    def test_close_then_tabs_reflects_it(self):
        self.post("/api/sites/open", {"names": ["github"]})
        tab_id = self.browser.tabs[0]["id"]
        self.post("/api/sites/close", {"tab_id": tab_id})
        self.assertEqual(self.browser.tabs, [])

    def test_close_without_a_target_is_an_error(self):
        events = self.post("/api/sites/close", {})
        self.assertEqual(events[-1]["type"], "error")

    def test_focus_switches_a_tab(self):
        self.post("/api/sites/open", {"names": ["github"]})
        tab_id = self.browser.tabs[0]["id"]
        events = self.post("/api/sites/focus", {"tab_id": tab_id})
        result = next(event for event in events if event["type"] == "result")["workflow"]
        self.assertEqual(result["focused"], tab_id)

    def test_vrm_export_wraps_a_glb(self):
        from weronika_agent.blueprint import _read_glb_chunks, _write_glb

        glb = _write_glb({"asset": {"version": "2.0"}, "scene": 0}, b"")
        request = urllib.request.Request(
            f"{self.base}/api/blueprint/vrm",
            data=glb,
            headers={"Content-Type": "application/octet-stream", "X-Weronika-Title": "Hero"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("X-Weronika-VRM-Static"), "1")
            self.assertIn("weronika-avatar.vrm", response.headers.get("Content-Disposition", ""))
        document, _binary = _read_glb_chunks(body)
        block = document["extensions"]["VRM"]
        self.assertEqual(block["meta"]["title"], "Hero")
        self.assertFalse(block["rigged"])

    def test_vrm_export_rejects_a_non_glb(self):
        request = urllib.request.Request(
            f"{self.base}/api/blueprint/vrm",
            data=b"not a model at all",
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)

    def test_capabilities_report_the_vrm_contract(self):
        status, data = self.get("/api/blueprint/capabilities")
        self.assertEqual(status, 200)
        self.assertIn("vrm_export", data)
        self.assertFalse(data["vrm_export"]["rigged"])

    def test_status_reports_site_support(self):
        with urllib.request.urlopen(f"{self.base}/api/automation/status", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertTrue(data["sites"])


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
        self.web = FakeWeb()
        self.tasks = TaskService(lambda: self.web)
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                self.service,
                self.adapters,
                self.workspace,
                watch=self.watch,
                skills=self.skills,
                tasks=self.tasks,
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

    def test_browse_capabilities_lists_actions_and_browsers(self):
        with self.request("/api/browse/capabilities") as response:
            caps = json.load(response)
        actions = {action["kind"] for action in caps["actions"]}
        self.assertIn("play_video", actions)
        self.assertIn("comment", actions)
        self.assertTrue(any(action["needs_approval"] for action in caps["actions"]))
        self.assertTrue(caps["local_planning"])

    def test_multi_step_task_runs_search_open_and_read(self):
        task = result = None
        with self.request(
            "/api/task/start",
            {
                "message": "search and summarize",
                "steps": [
                    {"action": "search", "target": "best laptop"},
                    {"action": "open_result", "target": ""},
                    {"action": "read_page", "target": ""},
                ],
            },
            origin=self.base,
        ) as response:
            result = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertEqual(result["stage"], "done")
        self.assertEqual([call[0] for call in self.web.calls], ["search", "open_result", "read_page"])
        self.assertIn("Example", result["result"])

    def test_comment_waits_for_approval_then_submits(self):
        with self.request(
            "/api/task/start",
            {"message": "comment", "steps": [{"action": "comment", "target": "Great explanation"}]},
            origin=self.base,
        ) as response:
            pending = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertEqual(pending["stage"], "awaiting_approval")
        self.assertEqual(self.web.submitted, [])

        with self.request(
            "/api/task/approve",
            {"task_id": pending["task_id"], "confirmation": "confirm"},
            origin=self.base,
        ) as response:
            done = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertEqual(done["stage"], "done")
        self.assertEqual(self.web.submitted, ["Great explanation"])

    def test_task_status_and_cancel(self):
        with self.request(
            "/api/task/start",
            {"message": "comment", "steps": [{"action": "comment", "target": "hi"}]},
            origin=self.base,
        ) as response:
            pending = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        with self.request(f"/api/task/status?task_id={pending['task_id']}") as response:
            self.assertEqual(json.load(response)["task"]["stage"], "awaiting_approval")
        with self.request(
            "/api/task/cancel", {"task_id": pending["task_id"]}, origin=self.base
        ) as response:
            cancelled = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertEqual(cancelled["stage"], "cancelled")
        self.assertEqual(self.web.submitted, [])

    def test_open_in_own_browser_route(self):
        with self.request(
            "/api/browse/open", {"url": "https://github.com", "browser": "edge"}, origin=self.base
        ) as response:
            opened = next(
                event["workflow"] for event in self.events(response) if event["type"] == "result"
            )
        self.assertIn("Microsoft Edge", opened["result"])
        self.assertEqual(self.web.calls[-1], ("system", "edge|https://github.com"))

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
