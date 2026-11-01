"""Optional, local-only single-image 3D reconstruction with TripoSR."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
from io import BytesIO
from pathlib import Path
from typing import Any

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_MODEL_BYTES = 80 * 1024 * 1024
MODEL_TIMEOUT_SECONDS = 30 * 60
MODEL_NAME = "TripoSR"
_MODEL_LOCK = threading.Lock()
_REQUIRED_MODULES = (
    "torch",
    "rembg",
    "xatlas",
    "torchmcubes",
    "trimesh",
    "transformers",
    "omegaconf",
    "einops",
    "imageio",
    "moderngl",
)


class BlueprintError(RuntimeError):
    """Safe, user-actionable local 3D reconstruction error."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def triposr_root() -> Path:
    configured = os.environ.get("WERONIKA_TRIPOSR_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".weronika" / "models" / "TripoSR").resolve()


def blueprint_status() -> dict[str, Any]:
    """Return setup readiness without importing heavy ML dependencies."""
    root = triposr_root()
    missing = [name for name in _REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    source_ready = (root / "run.py").is_file()
    ready = source_ready and not missing
    return {
        "model": MODEL_NAME,
        "available": ready,
        "source_ready": source_ready,
        "missing_packages": missing,
        "setup_command": "weronika-py\\setup-blueprint.bat",
        "weights": "download-on-first-use",
        "device": "cpu",
        "message": (
            "Local CPU 3D model is ready. The first generation downloads its model weights."
            if ready
            else "Install the optional TripoSR CPU model with setup-blueprint.bat."
        ),
    }


def _validate_image(image_bytes: bytes) -> None:
    if not image_bytes:
        raise BlueprintError("Choose a photo before starting 3D generation.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise BlueprintError("Photos must be 20 MB or smaller for local 3D generation.")
    try:
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
            if width < 32 or height < 32:
                raise BlueprintError("Choose a photo at least 32 by 32 pixels.")
            if width * height > 24_000_000:
                raise BlueprintError("This photo has too many pixels. Resize it to 24 megapixels or less.")
            image.verify()
    except BlueprintError:
        raise
    except Exception as exc:
        raise BlueprintError("That file is not a supported, readable photo. Try JPG or PNG.") from exc


def reconstruct_photo(image_bytes: bytes) -> tuple[bytes, str]:
    """Run TripoSR on CPU and return a generated GLB plus a safe status string."""
    status = blueprint_status()
    if not status["available"]:
        raise BlueprintError(
            "Local 3D AI is not installed. Run weronika-py\\setup-blueprint.bat, then reopen the orb.",
            status_code=503,
        )
    _validate_image(image_bytes)
    if not _MODEL_LOCK.acquire(blocking=False):
        raise BlueprintError(
            "A 3D generation is already running on this computer. Please wait for it to finish.",
            status_code=409,
        )

    try:
        root = triposr_root()
        with tempfile.TemporaryDirectory(prefix="weronika-triposr-") as temporary:
            temp = Path(temporary)
            input_path = temp / "input-photo"
            output_dir = temp / "output"
            output_dir.mkdir()
            input_path.write_bytes(image_bytes)
            environment = os.environ.copy()
            cpu_count = max(1, min(os.cpu_count() or 1, 8))
            environment["OMP_NUM_THREADS"] = str(cpu_count)
            environment["MKL_NUM_THREADS"] = str(cpu_count)
            command = [
                sys.executable,
                str(root / "run.py"),
                str(input_path),
                "--device",
                "cpu",
                "--output-dir",
                str(output_dir),
                "--model-save-format",
                "glb",
                "--chunk-size",
                "1024",
                "--mc-resolution",
                "128",
            ]
            try:
                result = subprocess.run(
                    command,
                    cwd=str(root),
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=MODEL_TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise BlueprintError(
                    "3D generation exceeded 30 minutes and was stopped. Try a smaller photo or a faster computer.",
                    status_code=504,
                ) from exc
            except OSError as exc:
                raise BlueprintError(
                    "The local TripoSR runtime could not start. Rerun setup-blueprint.bat.",
                    status_code=500,
                ) from exc
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip().splitlines()
                tail = " ".join(detail[-3:])[-700:]
                raise BlueprintError(
                    "The local 3D model failed. Check the setup and model download, then retry."
                    + (f" Details: {tail}" if tail else "")
                )
            model_path = output_dir / "0" / "mesh.glb"
            if not model_path.is_file():
                raise BlueprintError("TripoSR finished without producing a GLB model. Nothing was saved.")
            size = model_path.stat().st_size
            if size <= 0 or size > MAX_MODEL_BYTES:
                raise BlueprintError("The generated GLB is empty or over the 80 MB download limit.")
            model = model_path.read_bytes()
            if not model.startswith(b"glTF"):
                raise BlueprintError("The local model output was not a valid binary GLB.")
            return model, f"3D model created locally with {MODEL_NAME}; source photo and result were temporary."
    finally:
        _MODEL_LOCK.release()
