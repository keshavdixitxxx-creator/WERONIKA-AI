import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from weronika_agent.http_server import LocalServer, make_handler
from weronika_agent.memory_store import MAX_MEMORY_BYTES, MemoryStore, MemoryStoreError
from weronika_agent.workspace import LocalWorkspace


def sample_memory(turns=2):
    return {
        "v": 1,
        "enabled": True,
        "clearedAt": 0,
        "sessions": 3,
        "digest": "The user is Keshav. He is building a robot arm.",
        "turns": [
            {"id": f"t{index}", "role": "user" if index % 2 == 0 else "assistant", "content": f"line {index} — नमस्ते", "at": 1000 + index}
            for index in range(turns)
        ],
    }


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "memory"
        self.store = MemoryStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_nothing_is_created_until_memory_is_saved(self):
        self.assertIsNone(self.store.load())
        self.assertFalse(self.root.exists())

    def test_memory_survives_a_new_process(self):
        saved = self.store.save(sample_memory(4))
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["turns"], 4)
        # A restart is a fresh store object reading the same folder.
        reopened = MemoryStore(self.root).load()
        self.assertEqual(reopened, sample_memory(4))
        self.assertIn("नमस्ते", self.store.path.read_text(encoding="utf-8"))

    def test_saving_replaces_the_file_without_leaving_temporary_files(self):
        self.store.save(sample_memory(2))
        self.store.save(sample_memory(6))
        self.assertEqual(len(MemoryStore(self.root).load()["turns"]), 6)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["weronika-memory.json"])

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    def test_memory_file_is_private_to_the_user(self):
        self.store.save(sample_memory())
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)

    def test_only_memory_documents_are_accepted(self):
        for bad in (None, [], "text", {}, {"v": 2, "turns": []}, {"v": 1}, {"v": 1, "turns": "x"}):
            with self.subTest(bad=bad), self.assertRaises(MemoryStoreError):
                self.store.save(bad)
        self.assertFalse(self.store.path.exists())

    def test_oversized_memory_is_refused_and_the_old_copy_kept(self):
        self.store.save(sample_memory(2))
        huge = sample_memory(1)
        huge["turns"][0]["content"] = "x" * (MAX_MEMORY_BYTES + 1)
        with self.assertRaises(MemoryStoreError):
            self.store.save(huge)
        self.assertEqual(len(self.store.load()["turns"]), 2)

    def test_unreadable_file_is_set_aside_instead_of_overwritten(self):
        self.root.mkdir(parents=True)
        self.store.path.write_text("{ not json", encoding="utf-8")
        self.assertIsNone(self.store.load())
        self.assertFalse(self.store.path.exists())
        self.assertEqual((self.root / "weronika-memory.unreadable.json").read_text(encoding="utf-8"), "{ not json")
        # The orb can then write its own copy.
        self.store.save(sample_memory())
        self.assertEqual(len(self.store.load()["turns"]), 2)

    def test_a_wipe_is_stored_as_an_empty_document_with_its_time(self):
        self.store.save(sample_memory(4))
        wiped = {"v": 1, "enabled": True, "clearedAt": 5000, "turns": [], "digest": ""}
        self.assertEqual(self.store.save(wiped)["turns"], 0)
        self.assertEqual(MemoryStore(self.root).load(), wiped)
        self.assertNotIn("line 0", self.store.path.read_text(encoding="utf-8"))

    def test_a_symlinked_memory_file_is_refused(self):
        self.root.mkdir(parents=True)
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text(json.dumps(sample_memory()), encoding="utf-8")
        try:
            self.store.path.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available here")
        self.assertIsNone(self.store.load())
        with self.assertRaises(MemoryStoreError):
            self.store.save(sample_memory(4))
        self.assertEqual(len(json.loads(outside.read_text(encoding="utf-8"))["turns"]), 2)


class MemoryRouteTests(unittest.TestCase):
    """The memory endpoints on a real loopback server."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = MemoryStore(Path(self.temp.name) / "memory")
        self.server = LocalServer(
            ("127.0.0.1", 0),
            make_handler(
                SimpleNamespace(),
                SimpleNamespace(browser=None),
                LocalWorkspace(Path(self.temp.name) / "workspace"),
                memory=self.memory,
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

    def request(self, path, payload=None, origin=None, host=None):
        headers = {}
        if host is not None:
            headers["Host"] = host
        data = None
        method = "GET"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        if origin is not None:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_status_announces_memory_support(self):
        self.assertTrue(self.request("/api/automation/status")["memory"])

    def test_memory_round_trips_through_the_worker(self):
        empty = self.request("/api/memory")
        self.assertIsNone(empty["memory"])
        self.assertTrue(empty["path"].endswith("weronika-memory.json"))

        saved = self.request("/api/memory", {"memory": sample_memory(6)}, origin=self.base)
        self.assertTrue(saved["saved"])
        self.assertEqual(saved["turns"], 6)
        self.assertEqual(self.request("/api/memory")["memory"], sample_memory(6))
        # A restart reads the same file from disk.
        self.assertEqual(MemoryStore(self.memory.root).load(), sample_memory(6))

        # Forgetting is a write of the emptied document, which keeps the time of the wipe.
        wiped = {"v": 1, "enabled": True, "clearedAt": 9000, "turns": [], "digest": ""}
        self.assertEqual(self.request("/api/memory", {"memory": wiped}, origin=self.base)["turns"], 0)
        self.assertEqual(self.request("/api/memory")["memory"], wiped)

    def test_a_large_conversation_fits_the_request_limit(self):
        memory = sample_memory(300)
        for turn in memory["turns"]:
            turn["content"] = "word " * 700
        saved = self.request("/api/memory", {"memory": memory}, origin=self.base)
        self.assertEqual(saved["turns"], 300)
        self.assertGreater(saved["bytes"], 1_000_000)

    def test_invalid_memory_is_rejected(self):
        for payload in ({}, {"memory": []}, {"memory": {"v": 1}}):
            with self.subTest(payload=payload), self.assertRaises(urllib.error.HTTPError) as raised:
                self.request("/api/memory", payload, origin=self.base)
            self.assertEqual(raised.exception.code, 400)
        self.assertIsNone(self.memory.load())

    def test_other_origins_cannot_read_or_write_memory(self):
        self.memory.save(sample_memory())
        for payload in (None, {"memory": sample_memory(4)}):
            with self.subTest(write=payload is not None), self.assertRaises(urllib.error.HTTPError) as raised:
                self.request("/api/memory", payload, origin="https://example.com")
            self.assertEqual(raised.exception.code, 403)
        self.assertEqual(len(self.memory.load()["turns"]), 2)

    def test_a_rebound_hostname_cannot_read_or_write_memory(self):
        # DNS rebinding: another site's hostname resolves to 127.0.0.1, so the browser
        # treats the request as same-origin and sends no Origin header on a GET.
        self.memory.save(sample_memory())
        port = self.server.server_port
        for host in (f"evil.example:{port}", "evil.example", f"127.0.0.1:{port + 1}", f"127.0.0.1.evil.example:{port}", ""):
            for payload in (None, {"memory": sample_memory(4)}):
                with self.subTest(host=host, write=payload is not None), self.assertRaises(urllib.error.HTTPError) as raised:
                    self.request("/api/memory", payload, host=host)
                self.assertEqual(raised.exception.code, 403)
        self.assertEqual(len(self.memory.load()["turns"]), 2)
        for host in (f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}", f"LOCALHOST:{port}"):
            with self.subTest(host=host):
                self.assertEqual(len(self.request("/api/memory", host=host)["memory"]["turns"]), 2)

    def test_there_is_no_delete_route(self):
        self.memory.save(sample_memory())
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/memory/clear", {}, origin=self.base)
        self.assertEqual(raised.exception.code, 404)
        self.assertEqual(len(self.memory.load()["turns"]), 2)


if __name__ == "__main__":
    unittest.main()
