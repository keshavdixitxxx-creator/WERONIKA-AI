"""Checks that proposals and call pickup never act without explicit approval."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from weronika_calls import CallAssistant, prompt_for
from weronika_upgrade import apply_patch, approve_proposal, create_proposal, inspect_project


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="weronika-upgrade-")
        os.makedirs(os.path.join(self.tmp, "weronika-local"), exist_ok=True)
        with open(os.path.join(self.tmp, "weronika-local", "weronika_agent.py"), "w", encoding="utf-8") as fh:
            fh.write("print('agent')\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_propose_does_not_write_project_files(self):
        before = inspect_project(self.tmp)
        proposal = create_proposal("note the inspection", address_name="Captain", lang="en", root=self.tmp)
        self.assertTrue(proposal["applicable"])
        self.assertFalse(proposal["written"])
        self.assertFalse(proposal["executed"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "weronika-local", "assistant_diagnostics.md")))
        self.assertIn("Captain", proposal["say"])
        after = inspect_project(self.tmp)
        self.assertEqual(before["files"][0]["lines"], after["files"][0]["lines"])

    def test_approve_without_confirm_writes_nothing(self):
        proposal = create_proposal("", root=self.tmp)
        result = approve_proposal(proposal["id"], confirm=False, root=os.path.join(self.tmp, "weronika-local"))
        self.assertFalse(result["written"])
        self.assertFalse(result["executed"])
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "weronika-local", "assistant_diagnostics.md")))

    def test_approve_writes_but_does_not_execute(self):
        proposal = create_proposal("diagnostics", address_name="Commander", root=self.tmp)
        result = approve_proposal(proposal["id"], confirm=True, root=os.path.join(self.tmp, "weronika-local"))
        self.assertTrue(result["ok"])
        self.assertTrue(result["written"])
        self.assertFalse(result["executed"])
        target = os.path.join(self.tmp, "weronika-local", "assistant_diagnostics.md")
        self.assertTrue(os.path.isfile(target))
        self.assertIn("diagnostics", open(target, encoding="utf-8").read())

    def test_rejects_path_escape(self):
        with self.assertRaises(ValueError):
            apply_patch("--- a/../secret.txt\n+++ b/../secret.txt\n@@ -0,0 +1 @@\n+nope\n", self.tmp, write=False)


class CallTests(unittest.TestCase):
    def test_linux_detector_never_claims_an_answer(self):
        assistant = CallAssistant(platform="linux", scanner=lambda: {
            "supported": False,
            "capability": "unsupported",
            "detected": False,
            "window": None,
            "reason": "unsupported test",
        })
        status = assistant.detect()
        self.assertEqual(status["capability"], "unsupported")
        self.assertFalse(status["answered"])
        self.assertNotEqual(status["state"], "handling")
        denied = assistant.approve(confirm=True)
        self.assertFalse(denied["answered"])
        self.assertNotEqual(denied.get("status"), "handling")

    def test_approval_is_required_and_honest_when_click_fails(self):
        clicks = {"n": 0}

        def scanner():
            return {
                "supported": True,
                "capability": "available",
                "detected": True,
                "window": "WhatsApp Incoming voice call",
                "reason": "simulated window, not a real call",
                "simulated": True,
            }

        def answerer(window):
            clicks["n"] += 1
            return {"answered": False, "status": "error", "reason": "Accept control was not exposed. The call was not answered."}

        assistant = CallAssistant(scanner=scanner, answerer=answerer, platform="windows")
        assistant.set_identity("Captain", "en")
        found = assistant.detect()
        self.assertEqual(found["state"], "awaiting_approval")
        self.assertEqual(found["prompt"], "May I pick up and handle the conversation, Captain?")
        self.assertEqual(clicks["n"], 0)
        blocked = assistant.approve(confirm=False)
        self.assertFalse(blocked["answered"])
        self.assertEqual(clicks["n"], 0)
        failed = assistant.approve(confirm=True)
        self.assertEqual(clicks["n"], 1)
        self.assertFalse(failed["answered"])
        self.assertIn("not answered", failed["reason"])
        self.assertFalse(assistant.listen()["listening"])
        spoken = assistant.speak("hello")
        self.assertFalse(spoken["spoken"])
        self.assertFalse(spoken["routed_to_call"])

    def test_hindi_prompt_uses_saved_title(self):
        self.assertEqual(prompt_for("कमांडर", "hi"), "क्या मैं कॉल उठाकर बातचीत संभाल लूँ, कमांडर?")
        self.assertEqual(
            prompt_for("Commander", "en"),
            "May I pick up and handle the conversation, Commander?",
        )


class RouteTests(unittest.TestCase):
    def test_health_and_unapproved_call_route(self):
        from weronika_agent import Handler

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            import requests

            health = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)
            self.assertEqual(health.status_code, 200)
            body = health.json()
            self.assertIn(body["features"]["upgrade_proposals"]["state"], {"available"})
            self.assertIn(body["features"]["whatsapp_calls"]["state"], {"unsupported", "permission-required", "available"})
            call = requests.post(
                f"http://127.0.0.1:{port}/api/call/approve",
                json={"confirm": True, "addressName": "Commander"},
                timeout=5,
            )
            self.assertFalse(call.json().get("answered"))
            static = requests.get(f"http://127.0.0.1:{port}/weronika-commands.js", timeout=5)
            self.assertEqual(static.status_code, 200)
            self.assertIn("parseBlueprintCommand", static.text)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
