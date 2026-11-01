"""Install optional TripoSR dependencies for local CPU photo-to-3D."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

TRIPOSR_COMMIT = "107cefdc244c39106fa830359024f6a2f1c78871"
TORCHMCUBES_COMMIT = "a9ac95aa329957ba646e7bb057f825f5dfa77f38"
TRIPOSR_URL = f"https://codeload.github.com/VAST-AI-Research/TripoSR/zip/{TRIPOSR_COMMIT}"
TORCHMCUBES_URL = f"https://codeload.github.com/tatsy/torchmcubes/zip/{TORCHMCUBES_COMMIT}"
MODEL_ROOT = Path.home() / ".weronika" / "models" / "TripoSR"


def run(*args: str) -> None:
    print("\n> " + " ".join(args), flush=True)
    subprocess.run(args, check=True)


def download_zip(url: str, destination: Path, limit: int = 100 * 1024 * 1024) -> Path:
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("The model source archive exceeded its safety limit.")
    archive = destination / "source.zip"
    archive.write_bytes(data)
    return archive


def extract_archive(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        roots = set()
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("The source archive contains an unsafe path.")
            if path.parts:
                roots.add(path.parts[0])
        if len(roots) != 1:
            raise RuntimeError("The source archive has an unexpected layout.")
        zipped.extractall(destination)
        return destination / roots.pop()


def main() -> int:
    python = sys.executable
    weronika_root = Path(__file__).resolve().parent
    if not Path(python).is_file():
        raise RuntimeError("Could not locate the active Weronika Python environment.")

    MODEL_ROOT.parent.mkdir(parents=True, exist_ok=True)
    if (MODEL_ROOT / "run.py").is_file():
        print(f"TripoSR source is already present at {MODEL_ROOT}", flush=True)
    else:
        if MODEL_ROOT.exists():
            raise RuntimeError(
                f"An incomplete folder already exists at {MODEL_ROOT}. Move it aside manually, then retry."
            )
        with tempfile.TemporaryDirectory(prefix="weronika-model-setup-") as temp_name:
            temp = Path(temp_name)
            triposr_source = extract_archive(download_zip(TRIPOSR_URL, temp), temp / "triposr")
            shutil.move(str(triposr_source), str(MODEL_ROOT))

    print("Installing CPU-only PyTorch. This is a large download.", flush=True)
    run(
        python,
        "-m",
        "pip",
        "install",
        "torch",
        "torchvision",
        "--index-url",
        "https://download.pytorch.org/whl/cpu",
        "--extra-index-url",
        "https://pypi.org/simple",
    )

    # TripoSR's requirements reference torchmcubes through git. Download its
    # pinned GitHub source archive instead so Git is not required on Windows.
    requirements = (MODEL_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    other_requirements = [
        line
        for line in requirements
        if line.strip() and not line.lstrip().startswith("git+")
    ]
    temp_requirements = weronika_root / ".blueprint-requirements.tmp.txt"
    try:
        temp_requirements.write_text("\n".join(other_requirements) + "\n", encoding="utf-8")
        run(python, "-m", "pip", "install", "-r", str(temp_requirements))
    finally:
        temp_requirements.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="weronika-torchmcubes-") as temp_name:
        temp = Path(temp_name)
        source = extract_archive(download_zip(TORCHMCUBES_URL, temp), temp / "torchmcubes")
        run(python, "-m", "pip", "install", "scikit-build-core>=1.0", "pybind11>=2.10", "cmake>=3.24")
        run(python, "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(source))

    print("\nTripoSR setup is complete.", flush=True)
    print("The first generation downloads the pretrained model weights from Hugging Face.", flush=True)
    print("This CPU-only setup can take several minutes per image and needs a C++ build toolchain.", flush=True)
    print("Restart Weronika with start.bat, then choose GENERATE 3D MODEL in Blueprint.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"\nBlueprint setup failed: {exc}", file=sys.stderr)
        print("Install Visual Studio Build Tools (C++ workload) and rerun setup-blueprint.bat if compilation failed.", file=sys.stderr)
        raise SystemExit(1)
