"""Checks that proposals and call pickup never act without explicit approval."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        with open(target, encoding="utf-8") as diagnostics_file:
            self.assertIn("diagnostics", diagnostics_file.read())

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


class LocalPrivateBrainTests(unittest.TestCase):
    def test_private_completion_never_falls_back_to_cloud(self):
        import weronika_agent as agent

        with patch.object(agent, "ollama_ready", return_value=False), patch.object(agent, "stream_lovable") as cloud:
            with self.assertRaisesRegex(RuntimeError, "was not sent to the cloud"):
                agent.local_private_completion("Summarize this email", "The private message body.")
            cloud.assert_not_called()

        with patch.object(agent, "ollama_ready", return_value=True), patch.object(
            agent, "stream_ollama", return_value=iter(["Local summary."])
        ) as local_model:
            answer = agent.local_private_completion("Summarize this email", "The private message body.")
        self.assertEqual(answer, "Local summary.")
        self.assertIn("private message body", local_model.call_args.args[0][1]["content"].lower())


class DesktopActionTests(unittest.TestCase):
    def test_cursor_actions_are_screen_bounded(self):
        import weronika_agent as agent

        mouse = SimpleNamespace(
            size=Mock(return_value=(1920, 1080)),
            moveTo=Mock(),
            click=Mock(),
        )
        with patch.dict("sys.modules", {"pyautogui": mouse}):
            moved = agent.do_action("move", {"x": 800, "y": 450})
            clicked = agent.do_action("click", {"x": 800, "y": 450})
            with self.assertRaisesRegex(ValueError, "inside the 1920x1080 screen"):
                agent.do_action("move", {"x": 1920, "y": 1080})
            with self.assertRaisesRegex(ValueError, "require both x and y"):
                agent.do_action("click", {"x": 20})
        self.assertIn("800, 450", moved)
        self.assertIn("Clicked", clicked)
        mouse.moveTo.assert_called_once_with(800, 450, duration=0.12)
        mouse.click.assert_called_once_with(800, 450)

    def test_camera_cursor_gestures_are_normalized_bounded_and_clickable(self):
        import weronika_agent as agent

        mouse = SimpleNamespace(
            size=Mock(return_value=(1920, 1080)),
            moveTo=Mock(),
            click=Mock(),
            mouseDown=Mock(),
            mouseUp=Mock(),
        )
        with patch.dict("sys.modules", {"pyautogui": mouse}):
            moved = agent.do_action("cursor_gesture", {"gesture": "move", "x": 0.5, "y": 0.5})
            clicked = agent.do_action("cursor_gesture", {"gesture": "click", "x": 1, "y": 1})
            with self.assertRaisesRegex(ValueError, "between 0 and 1"):
                agent.do_action("cursor_gesture", {"gesture": "move", "x": 1.01, "y": 0.5})
            with self.assertRaisesRegex(ValueError, "must be numbers"):
                agent.do_action("cursor_gesture", {"gesture": "move", "x": True, "y": 0.5})
        self.assertIn("Moved", moved)
        self.assertIn("Clicked", clicked)
        mouse.moveTo.assert_any_call(960, 540, duration=0)
        mouse.moveTo.assert_any_call(1919, 1079, duration=0)
        mouse.click.assert_called_once_with()

    def test_fist_drag_releases_on_open_hand_and_has_timeout_watchdog(self):
        import weronika_agent as agent

        mouse = SimpleNamespace(
            size=Mock(return_value=(1000, 800)),
            moveTo=Mock(),
            click=Mock(),
            mouseDown=Mock(),
            mouseUp=Mock(),
        )
        agent._release_cursor_button()
        with patch.dict("sys.modules", {"pyautogui": mouse}):
            started = agent.do_action("cursor_gesture", {"gesture": "drag", "x": 0.25, "y": 0.5})
            self.assertIn("Dragging", started)
            self.assertTrue(agent._CURSOR_GESTURE_STATE["button_down"])
            self.assertIsNotNone(agent._CURSOR_GESTURE_STATE["timer"])
            released = agent.do_action("cursor_gesture", {"gesture": "release"})
        self.assertIn("Released", released)
        mouse.mouseDown.assert_called_once_with(button="left")
        mouse.mouseUp.assert_called_once_with(button="left")
        self.assertFalse(agent._CURSOR_GESTURE_STATE["button_down"])
        self.assertIsNone(agent._CURSOR_GESTURE_STATE["timer"])

    def test_desktop_control_rejects_nonlocal_browser_origins(self):
        import requests
        import weronika_agent as agent

        server = ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base_url = f"http://127.0.0.1:{port}/command"
            denied = requests.post(
                base_url,
                json={"action": "click"},
                headers={"Origin": "https://untrusted.example"},
                timeout=5,
            )
            self.assertEqual(denied.status_code, 403)
            self.assertIn("local browser origins", denied.json()["message"])
            with patch.object(agent, "do_action", return_value="Done on the PC.") as do_action:
                allowed = requests.post(
                    base_url,
                    json={"action": "click"},
                    headers={"Origin": "http://localhost:8080"},
                    timeout=5,
                )
            self.assertEqual(allowed.status_code, 200)
            self.assertTrue(allowed.json()["ok"])
            do_action.assert_called_once()
        finally:
            server.shutdown()
            server.server_close()


class RouteTests(unittest.TestCase):
    def test_signed_in_app_routes_are_local_origin_only(self):
        import requests
        import weronika_agent as agent

        server = ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{port}"
        try:
            denied = requests.get(
                f"{base_url}/api/apps/status",
                headers={"Origin": "https://untrusted.example"},
                timeout=5,
            )
            self.assertEqual(denied.status_code, 403)

            with patch.object(agent.APP_BROWSER, "perform", return_value={"ok": True, "app": "gmail"}) as perform:
                allowed = requests.post(
                    f"{base_url}/api/apps/action",
                    json={"action": "open", "app": "gmail"},
                    headers={"Origin": "http://localhost:8080"},
                    timeout=5,
                )
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.json()["app"], "gmail")
            perform.assert_called_once_with("open", {"action": "open", "app": "gmail"})
        finally:
            server.shutdown()
            server.server_close()

    def test_private_brain_requires_local_origin_and_never_uses_hosted_brain(self):
        import requests
        import weronika_agent as agent

        server = ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{port}/api/local/brain"
        try:
            denied = requests.post(
                url,
                json={"task": "summarize", "content": "private message"},
                headers={"Origin": "https://untrusted.example"},
                timeout=5,
            )
            self.assertEqual(denied.status_code, 403)

            with patch.object(agent, "ollama_ready", return_value=False), patch.object(
                agent, "stream_lovable"
            ) as hosted:
                unavailable = requests.post(
                    url,
                    json={"task": "summarize", "content": "private message"},
                    headers={"Origin": "http://localhost:8080"},
                    timeout=5,
                )
            self.assertEqual(unavailable.status_code, 503)
            self.assertIn("not sent to the cloud", unavailable.json()["error"])
            hosted.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()

    def test_local_code_workspace_endpoints_are_confined_and_open_vs_code(self):
        import requests
        import weronika_agent as agent

        with tempfile.TemporaryDirectory(prefix="weronika-workspace-test-") as workspace_root:
            with patch.object(agent, "WORKSPACE", workspace_root):
                server = ThreadingHTTPServer(("127.0.0.1", 0), agent.Handler)
                port = server.server_address[1]
                threading.Thread(target=server.serve_forever, daemon=True).start()
                base_url = f"http://127.0.0.1:{port}"
                html = "<!doctype html><html><body><h1>Local page</h1></body></html>"
                try:
                    saved = requests.post(
                        f"{base_url}/api/workspace/save",
                        json={"content": html, "path": "../../outside.html"},
                        timeout=5,
                    )
                    self.assertEqual(saved.status_code, 200)
                    self.assertTrue(saved.json()["ok"])
                    target = os.path.join(workspace_root, "weronika-site", "index.html")
                    self.assertTrue(os.path.isfile(target))
                    with open(target, encoding="utf-8") as saved_file:
                        self.assertEqual(saved_file.read(), html)
                    self.assertFalse(os.path.exists(os.path.join(workspace_root, "outside.html")))

                    source = requests.get(f"{base_url}/api/workspace/source", timeout=5)
                    self.assertEqual(source.status_code, 200)
                    self.assertEqual(source.json()["content"], html)
                    preview = requests.get(f"{base_url}/api/workspace/preview?t=1", timeout=5)
                    self.assertEqual(preview.status_code, 200)
                    self.assertIn("default-src 'none'", preview.headers["Content-Security-Policy"])
                    self.assertIn("<h1>Local page</h1>", preview.text)
                    self.assertIn('<base href="/api/workspace/preview-files/">', preview.text)

                    python_source = "print('hello from Python')\\n"
                    python_save = requests.post(
                        f"{base_url}/api/workspace/save",
                        json={"filename": "main.py", "content": python_source},
                        timeout=5,
                    )
                    self.assertEqual(python_save.status_code, 200)
                    self.assertEqual(python_save.json()["filename"], "main.py")
                    python_read = requests.get(
                        f"{base_url}/api/workspace/source?name=main.py", timeout=5
                    )
                    self.assertEqual(python_read.json()["content"], python_source)

                    for folder in ("src", "src/ui", "src/assets"):
                        created_folder = requests.post(
                            f"{base_url}/api/workspace/mkdir", json={"path": folder}, timeout=5
                        )
                        self.assertEqual(created_folder.status_code, 200)
                    duplicate_folder = requests.post(
                        f"{base_url}/api/workspace/mkdir", json={"path": "src"}, timeout=5
                    )
                    self.assertEqual(duplicate_folder.status_code, 409)
                    invalid_folder = requests.post(
                        f"{base_url}/api/workspace/mkdir", json={"path": "../escape"}, timeout=5
                    )
                    self.assertEqual(invalid_folder.status_code, 400)

                    nested_html = (
                        '<!doctype html><html><head><link rel="stylesheet" href="styles.css">'
                        '</head><body><h1>Nested preview</h1><script src="assets/app.js"></script></body></html>'
                    )
                    for filename, content in (
                        ("src/index.html", nested_html),
                        ("src/styles.css", "h1 { color: rebeccapurple; }"),
                        ("src/assets/app.js", "console.log('nested project');"),
                        ("src/ui/App.tsx", "export const App = () => <main>Hello</main>;"),
                    ):
                        saved_nested = requests.post(
                            f"{base_url}/api/workspace/save",
                            json={"filename": filename, "content": content},
                            timeout=5,
                        )
                        self.assertEqual(saved_nested.status_code, 200)
                        self.assertEqual(saved_nested.json()["filename"], filename)

                    nested_source = requests.get(
                        f"{base_url}/api/workspace/source?name=src%2Fui%2FApp.tsx", timeout=5
                    )
                    self.assertEqual(nested_source.status_code, 200)
                    self.assertEqual(nested_source.json()["content"], "export const App = () => <main>Hello</main>;")
                    nested_preview = requests.get(
                        f"{base_url}/api/workspace/preview?name=src%2Findex.html", timeout=5
                    )
                    self.assertEqual(nested_preview.status_code, 200)
                    self.assertIn('<base href="/api/workspace/preview-files/src/">', nested_preview.text)
                    self.assertIn("Nested preview", nested_preview.text)
                    proxied_preview = requests.get(
                        f"{base_url}/api/workspace/preview?name=src%2Findex.html"
                        "&asset_prefix=%2Fapi%2Fweronika-agent%2Fapi%2Fworkspace%2Fpreview-files%2F",
                        timeout=5,
                    )
                    self.assertIn(
                        '<base href="/api/weronika-agent/api/workspace/preview-files/src/">',
                        proxied_preview.text,
                    )
                    nested_asset = requests.get(
                        f"{base_url}/api/workspace/preview-files/src/assets/app.js", timeout=5
                    )
                    self.assertEqual(nested_asset.status_code, 200)
                    self.assertEqual(nested_asset.text, "console.log('nested project');")

                    file_list = requests.get(f"{base_url}/api/workspace/files", timeout=5)
                    self.assertEqual(
                        {item["filename"] for item in file_list.json()["files"]},
                        {"index.html", "main.py", "src/index.html", "src/styles.css", "src/assets/app.js", "src/ui/App.tsx"},
                    )
                    self.assertEqual(set(file_list.json()["directories"]), {"src", "src/assets", "src/ui"})
                    non_html_preview = requests.get(
                        f"{base_url}/api/workspace/preview?name=main.py", timeout=5
                    )
                    self.assertEqual(non_html_preview.status_code, 415)
                    invalid_name = requests.post(
                        f"{base_url}/api/workspace/save",
                        json={"filename": "../../outside.py", "content": "bad"},
                        timeout=5,
                    )
                    self.assertEqual(invalid_name.status_code, 400)
                    symlink_path = os.path.join(workspace_root, "weronika-site", "outside-link")
                    try:
                        os.symlink(tempfile.gettempdir(), symlink_path, target_is_directory=True)
                    except (OSError, NotImplementedError):
                        pass
                    else:
                        symlink_save = requests.post(
                            f"{base_url}/api/workspace/save",
                            json={"filename": "outside-link/stolen.py", "content": "bad"},
                            timeout=5,
                        )
                        self.assertEqual(symlink_save.status_code, 400)
                    rename = requests.post(
                        f"{base_url}/api/workspace/rename",
                        json={"old_name": "main.py", "new_name": "app.py"},
                        timeout=5,
                    )
                    self.assertEqual(rename.status_code, 200)
                    self.assertTrue(os.path.isfile(os.path.join(workspace_root, "weronika-site", "app.py")))
                    denied_delete = requests.post(
                        f"{base_url}/api/workspace/delete",
                        json={"filename": "app.py", "confirm": False},
                        timeout=5,
                    )
                    self.assertEqual(denied_delete.status_code, 409)
                    deleted = requests.post(
                        f"{base_url}/api/workspace/delete",
                        json={"filename": "app.py", "confirm": True},
                        timeout=5,
                    )
                    self.assertEqual(deleted.status_code, 200)
                    folder_rename = requests.post(
                        f"{base_url}/api/workspace/rename",
                        json={"old_name": "src/ui", "new_name": "src/components", "directory": True},
                        timeout=5,
                    )
                    self.assertEqual(folder_rename.status_code, 200)
                    self.assertTrue(
                        os.path.isfile(os.path.join(workspace_root, "weronika-site", "src", "components", "App.tsx"))
                    )
                    nonempty_folder_delete = requests.post(
                        f"{base_url}/api/workspace/delete",
                        json={"path": "src", "directory": True, "confirm": True},
                        timeout=5,
                    )
                    self.assertEqual(nonempty_folder_delete.status_code, 409)
                    empty_folder = requests.post(
                        f"{base_url}/api/workspace/mkdir", json={"path": "src/empty"}, timeout=5
                    )
                    self.assertEqual(empty_folder.status_code, 200)
                    denied_folder_delete = requests.post(
                        f"{base_url}/api/workspace/delete",
                        json={"path": "src/empty", "directory": True, "confirm": False},
                        timeout=5,
                    )
                    self.assertEqual(denied_folder_delete.status_code, 409)
                    empty_folder_delete = requests.post(
                        f"{base_url}/api/workspace/delete",
                        json={"path": "src/empty", "directory": True, "confirm": True},
                        timeout=5,
                    )
                    self.assertEqual(empty_folder_delete.status_code, 200)

                    local_origin = requests.get(
                        f"{base_url}/api/workspace/source",
                        headers={"Origin": "http://localhost:8081"},
                        timeout=5,
                    )
                    self.assertEqual(local_origin.status_code, 200)
                    denied = requests.get(
                        f"{base_url}/api/workspace/source",
                        headers={"Origin": "https://untrusted.example"},
                        timeout=5,
                    )
                    self.assertEqual(denied.status_code, 403)
                    denied_save = requests.post(
                        f"{base_url}/api/workspace/save",
                        json={"content": "bad"},
                        headers={"Origin": "https://untrusted.example"},
                        timeout=5,
                    )
                    self.assertEqual(denied_save.status_code, 403)

                    with patch.object(agent, "find_vscode_executable", return_value="/fake/Code") as finder:
                        with patch("weronika_agent.subprocess.Popen") as popen:
                            opened = requests.post(f"{base_url}/api/workspace/open-vscode", json={}, timeout=5)
                    self.assertEqual(opened.status_code, 200)
                    self.assertTrue(opened.json()["ok"])
                    finder.assert_called_once()
                    self.assertEqual(popen.call_args.args[0], ["/fake/Code", "--reuse-window", os.path.dirname(target)])
                    popen.assert_called_once()
                finally:
                    server.shutdown()
                    server.server_close()

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
            page = requests.get(f"http://127.0.0.1:{port}/", timeout=5)
            self.assertEqual(page.status_code, 200)
            self.assertNotIn('id="speechLanguageSelect"', page.text)
            self.assertIn("detectSpokenLanguage(transcript)", page.text)
            self.assertIn('sendChatMessage({ language: spokenLang, source: "voice" })', page.text)
            self.assertIn('continuous: false, mode: "turn"', page.text)
            self.assertIn('function splitWakeWord(text)', page.text)
            self.assertIn('id="wakeWordBtn"', page.text)
            self.assertIn('id="answerBannerMedia"', page.text)
            self.assertIn('id="workspaceSidePane"', page.text)
            self.assertIn('id="workspaceAIChat"', page.text)
            self.assertIn('id="workspaceTerminalForm"', page.text)
            self.assertIn('action: \'move\'', page.text)
            self.assertIn('const PC_AGENT_PREFIX', page.text)
            self.assertIn('const openAndType', page.text)
            self.assertNotIn('/api/shell', page.text)
            self.assertIn('id="codeWorkspace"', page.text)
            self.assertIn('createCodeWorkspace', page.text)
            static = requests.get(f"http://127.0.0.1:{port}/weronika-commands.js", timeout=5)
            self.assertEqual(static.status_code, 200)
            self.assertIn("parseBlueprintCommand", static.text)
            workspace_js = requests.get(f"http://127.0.0.1:{port}/weronika-workspace.js", timeout=5)
            self.assertEqual(workspace_js.status_code, 200)
            self.assertIn("createCodeWorkspace", workspace_js.text)
            models = requests.get(f"http://127.0.0.1:{port}/technical-models.js", timeout=5)
            self.assertEqual(models.status_code, 200)
            self.assertIn("buildCatalog", models.text)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
