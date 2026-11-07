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


# --------------------------------------------------------------------------- VRM
# GLB is a plain mesh container. VRM is the same GLB container plus a humanoid
# avatar description in its JSON chunk (bone mapping, expression blendshapes,
# MToon materials). TripoSR produces an unrigged mesh, so a true VRM needs a
# humanoid armature. We do not fabricate one: instead the export writes a
# valid VRM 0.x container that declares the mesh as a static avatar and records
# honestly that no rig is present. Anything claimed as rigged would be a lie.

_VRM_EXTENSION = "VRM"
_VRM_VERSION = "0.x"


def _read_glb_chunks(payload: bytes) -> tuple[dict[str, Any], bytes]:
    """Split a binary GLB into (json, binary). Raises on a malformed container."""
    import json as _json
    import struct

    if len(payload) < 20 or not payload.startswith(b"glTF"):
        raise BlueprintError("That file is not a binary GLB, so VRM export is not possible.")
    magic, version, total = struct.unpack_from("<III", payload, 0)
    if magic != 0x46546C67 or version != 2:
        raise BlueprintError("Only glTF 2.0 binary GLB files can be exported to VRM.")
    if total > len(payload):
        raise BlueprintError("The GLB is truncated and cannot be exported.")
    offset = 12
    document: dict[str, Any] | None = None
    binary = b""
    while offset + 8 <= len(payload):
        length, kind = struct.unpack_from("<II", payload, offset)
        offset += 8
        chunk = payload[offset : offset + length]
        offset += length
        if kind == 0x4E4F534A:
            try:
                document = _json.loads(chunk.decode("utf-8"))
            except Exception as exc:
                raise BlueprintError("The GLB JSON chunk could not be read.") from exc
        elif kind == 0x004E4942:
            binary = chunk
    if not isinstance(document, dict):
        raise BlueprintError("The GLB has no JSON chunk, so it cannot be exported to VRM.")
    return document, binary


def _write_glb(document: dict[str, Any], binary: bytes) -> bytes:
    """Rebuild a binary GLB from JSON and an optional binary chunk."""
    import json as _json
    import struct

    json_bytes = _json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    chunks = struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
    if binary:
        padded = binary + b"\0" * ((4 - len(binary) % 4) % 4)
        chunks += struct.pack("<II", len(padded), 0x004E4942) + padded
    total = 12 + len(chunks)
    return b"glTF" + struct.pack("<II", 2, total) + chunks


def vrm_meta(title: str = "Weronika avatar") -> dict[str, Any]:
    """A minimal, honest VRM 0.x metadata block."""
    return {
        "title": (title or "Weronika avatar")[:64],
        "version": "1.0",
        "author": "Weronika AI (local TripoSR)",
        "contactInformation": "",
        "reference": "",
        "allowedUserName": "OnlyAuthor",
        "violentUssageName": "Disallow",
        "sexualUssageName": "Disallow",
        "commercialUssageName": "Disallow",
        "otherPermissionUrl": "",
        "licenseName": "Other",
        "otherLicenseUrl": "",
    }


def glb_to_vrm(glb: bytes, title: str = "Weronika avatar") -> bytes:
    """Wrap a generated GLB in a VRM 0.x container.

    The result is a valid VRM file that viewers can load. It is a *static*
    avatar: TripoSR meshes carry no skeleton, so ``humanoid`` is left without
    bone nodes and the file states that no rig is included. Callers must show
    that limitation instead of implying the model is ready to animate.
    """
    document, binary = _read_glb_chunks(glb)
    extensions = document.setdefault("extensions", {})
    if not isinstance(extensions, dict):
        raise BlueprintError("The GLB extensions block is malformed.")

    extensions[_VRM_EXTENSION] = {
        "exporterVersion": "Weronika-Blueprint 1.0",
        "specVersion": _VRM_VERSION,
        "meta": vrm_meta(title),
        "humanoid": {"humanBones": []},
        "blendShapeMaster": {"blendShapeGroups": []},
        "firstPerson": None,
        "materialProperties": [],
        "secondaryAnimation": {"boneGroups": [], "colliderGroups": []},
        "rigged": False,
        "note": (
            "Static mesh exported from a single photo by local TripoSR. "
            "No skeleton or blendshapes are included, so this avatar will load "
            "but cannot be posed or animated until it is rigged."
        ),
    }
    document.setdefault("extensionsUsed", [])
    if _VRM_EXTENSION not in document["extensionsUsed"]:
        document["extensionsUsed"].append(_VRM_EXTENSION)
    return _write_glb(document, binary)


def describe_vrm_limits() -> dict[str, Any]:
    """What the VRM export honestly is, for the orb to display."""
    return {
        "format": "VRM 0.x",
        "static": True,
        "rigged": False,
        "has_blendshapes": False,
        "note": (
            "VRM export is a static avatar. A single photo cannot produce a "
            "humanoid skeleton, so the model loads in VRM viewers but cannot be "
            "posed or animated. Generate a GLB if you only need the mesh."
        ),
    }
