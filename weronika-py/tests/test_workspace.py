import tempfile
import unittest
from pathlib import Path

from weronika_agent.workspace import LocalWorkspace, WorkspaceError
from weronika_agent.playwright_adapter import BrowserManager


class LocalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = LocalWorkspace(Path(self.temp.name) / "workspace")

    def tearDown(self):
        self.temp.cleanup()

    def test_save_tree_and_read_round_trip(self):
        saved = self.workspace.save("src/main.py", "print('hello')", overwrite=False)
        self.assertEqual(saved["path"], "src/main.py")
        self.assertEqual(self.workspace.read("src/main.py")["content"], "print('hello')")
        tree = self.workspace.tree()
        self.assertEqual(tree[0]["name"], "src")
        self.assertEqual(tree[0]["children"][0]["path"], "src/main.py")

    def test_paths_and_extensions_are_confined(self):
        for path in ("../escape.py", "/tmp/escape.py", "folder/../../escape.py"):
            with self.subTest(path=path), self.assertRaises(WorkspaceError):
                self.workspace.save(path, "nope")
        with self.assertRaises(WorkspaceError):
            self.workspace.save("notes.bin", "binary")
        self.workspace.save("main.py", "one")
        with self.assertRaises(WorkspaceError):
            self.workspace.save("main.py", "two", overwrite=False)

    def test_run_requires_explicit_confirmation_and_bounds_output(self):
        self.workspace.save("hello.py", "print('hello')")
        with self.assertRaises(WorkspaceError):
            self.workspace.run_python("hello.py", confirmed=False)
        result = self.workspace.run_python("hello.py", confirmed=True)
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"].strip(), "hello")

    def test_managed_browser_only_accepts_http_and_https(self):
        normalize = BrowserManager._normalize_web_url
        self.assertEqual(normalize("localhost:5173"), "http://localhost:5173/")
        self.assertEqual(normalize("127.0.0.1:8000/app"), "http://127.0.0.1:8000/app")
        self.assertEqual(normalize("example.com"), "https://example.com/")
        for value in ("file:///etc/passwd", "javascript:alert(1)", "https://user:pass@example.com", "bad url"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize(value)


if __name__ == "__main__":
    unittest.main()
