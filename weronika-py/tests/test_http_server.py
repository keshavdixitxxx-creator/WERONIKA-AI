import json
import threading
import unittest
import urllib.error
import urllib.request

from weronika_agent.http_server import LocalServer, make_handler
from weronika_agent.models import Platform, VisibleContact
from weronika_agent.workflow import MessagingService


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


class LocalHttpServerTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeAdapter()
        self.service = MessagingService(lambda _: self.adapter)
        self.server = LocalServer(("127.0.0.1", 0), make_handler(self.service, None))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

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
