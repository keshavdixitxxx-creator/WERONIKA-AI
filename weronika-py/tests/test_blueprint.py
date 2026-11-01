import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from weronika_agent.blueprint import BlueprintError, reconstruct_photo


class BlueprintTests(unittest.TestCase):
    def test_model_is_opt_in_and_reports_setup_instructions(self):
        with patch("weronika_agent.blueprint.blueprint_status", return_value={"available": False}):
            with self.assertRaises(BlueprintError) as raised:
                reconstruct_photo(b"not an image")
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("setup-blueprint.bat", str(raised.exception))

    def test_rejects_large_photo_before_starting_inference(self):
        with patch("weronika_agent.blueprint.blueprint_status", return_value={"available": True}):
            with self.assertRaises(BlueprintError) as raised:
                reconstruct_photo(b"x" * (20 * 1024 * 1024 + 1))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("20 MB", str(raised.exception))

    def test_runs_triposr_on_cpu_and_returns_a_valid_glb(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "TripoSR"

            def fake_run(command, **kwargs):
                output = Path(command[command.index("--output-dir") + 1]) / "0"
                output.mkdir(parents=True)
                (output / "mesh.glb").write_bytes(b"glTF" + b"\x00" * 16)
                self.assertIn("cpu", command)
                self.assertEqual(kwargs["cwd"], str(root))
                self.assertLessEqual(kwargs["timeout"], 30 * 60)
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            with (
                patch("weronika_agent.blueprint.blueprint_status", return_value={"available": True}),
                patch("weronika_agent.blueprint._validate_image"),
                patch("weronika_agent.blueprint.triposr_root", return_value=root),
                patch("weronika_agent.blueprint.subprocess.run", side_effect=fake_run),
            ):
                glb, message = reconstruct_photo(b"fake image")

        self.assertTrue(glb.startswith(b"glTF"))
        self.assertIn("TripoSR", message)


if __name__ == "__main__":
    unittest.main()
