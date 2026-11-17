"""Install the optional call-audio dependencies for handling phone and WhatsApp calls.

This is opt-in on purpose. Hearing a caller and speaking Weronika's lines needs a speech
engine and an audio library, and those are large downloads that most people never touch.
Weronika works without them: she answers in **typed mode** and says so out loud, rather
than pretending to hear something she did not.

Run it with ``setup-calls.bat`` (Windows) or ``python setup_calls.py`` directly.

What it installs
    ``sounddevice``     hears the caller through a microphone, a Bluetooth pairing or line-in
    ``faster-whisper``  the accurate speech engine — best on Hinglish and Indian English
    ``vosk``            the light fallback engine, used when Whisper is not installed
    ``pyttsx3``         Weronika's spoken voice on Windows (other systems use their own)

It also fetches a small Vosk model so the fallback works without a second trip online.
Whisper downloads its own weights on first use.

Privacy: nothing here records a call. Audio lives in memory only for the length of one
utterance, the words go into the in-memory transcript, and the samples are dropped. No
waveform is ever written to disk.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

# Package import name → PyPI name → why it is wanted. Kept here rather than read from the
# worker so this script still runs when the worker cannot be imported.
PACKAGES: tuple[tuple[str, str, str], ...] = (
    ("sounddevice", "sounddevice>=0.4.6", "hears the caller through a microphone, Bluetooth pairing or line-in"),
    ("faster_whisper", "faster-whisper>=1.0", "the accurate speech engine (best on Hinglish and Indian English)"),
    ("vosk", "vosk>=0.3.45", "the light speech engine, used when Whisper is absent"),
    ("pyttsx3", "pyttsx3>=2.90", "Weronika's spoken voice on Windows"),
)

#: The light Vosk model. Small on purpose: it is the fallback, not the good engine.
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
MODEL_ROOT = Path.home() / ".weronika" / "models"
DOWNLOAD_LIMIT_BYTES = 400 * 1024 * 1024


class SetupError(RuntimeError):
    """Something the installer could not do, phrased for a person."""


def plan_packages(
    engines: tuple[str, ...] = ("whisper", "vosk"),
    *,
    with_audio: bool = True,
    with_voice: bool = True,
) -> list[tuple[str, str]]:
    """Return the (PyPI name, reason) pairs this run should install.

    Pure and side-effect free, so the orb's readiness check and the tests can ask what a
    given choice would install without touching pip.
    """
    wanted = {str(engine).strip().casefold() for engine in engines if str(engine).strip()}
    plan: list[tuple[str, str]] = []
    for import_name, pip_name, reason in PACKAGES:
        if import_name == "sounddevice" and not with_audio:
            continue
        if import_name == "pyttsx3" and not with_voice:
            continue
        if import_name in {"faster_whisper", "vosk"} and (
            {"whisper", "vosk"} & wanted and import_name not in _engine_modules(wanted)
        ):
            continue
        plan.append((pip_name, reason))
    return plan


def _engine_modules(wanted: set[str]) -> set[str]:
    """Map engine choices onto the modules they need."""
    modules: set[str] = set()
    if "whisper" in wanted or "auto" in wanted or "both" in wanted:
        modules.add("faster_whisper")
    if "vosk" in wanted or "auto" in wanted or "both" in wanted:
        modules.add("vosk")
    return modules


def missing_packages(plan: tuple[tuple[str, str], ...] | list[tuple[str, str]]) -> list[str]:
    """Which of the planned packages are not importable yet."""
    import_names = {base_name(pip_name): import_name for import_name, pip_name, _reason in PACKAGES}
    missing = []
    for pip_name, _reason in plan:
        import_name = import_names.get(base_name(pip_name), base_name(pip_name))
        try:
            if importlib.util.find_spec(import_name) is None:
                missing.append(pip_name)
        except (ImportError, ValueError):
            missing.append(pip_name)
    return missing


def vosk_model_root() -> Path:
    return MODEL_ROOT / "vosk"


def vosk_model_present() -> bool:
    """True when a usable Vosk model folder already sits in the model root."""
    root = vosk_model_root()
    return root.is_dir() and any(item.is_dir() and item.name.startswith("vosk-model") for item in root.iterdir())


def run(*args: str) -> None:
    print("\n> " + " ".join(args), flush=True)
    subprocess.run(args, check=True)


def download_zip(url: str, destination: Path, limit: int = DOWNLOAD_LIMIT_BYTES) -> Path:
    print(f"Downloading {url}", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=180) as response:  # noqa: S310 - https URL only
            data = response.read(limit + 1)
    except urllib.error.URLError as exc:
        raise SetupError(f"Could not download {url}: {exc}") from exc
    if len(data) > limit:
        raise SetupError("The download was larger than the safety limit, so it was rejected.")
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "download.zip"
    archive.write_bytes(data)
    return archive


def extract_archive(archive: Path, destination: Path) -> Path:
    """Unzip into ``destination`` and return the single top-level folder inside.

    The checks mirror ``setup_blueprint.py``: a model archive that tries to write outside
    its own folder, or that does not have exactly one root, is rejected outright.
    """
    with zipfile.ZipFile(archive) as zipped:
        roots: set[str] = set()
        for name in zipped.namelist():
            entry = PurePosixPath(name)
            if entry.is_absolute() or ".." in entry.parts:
                raise SetupError("The archive contains an unsafe path, so it was not extracted.")
            if entry.parts:
                roots.add(entry.parts[0])
        if len(roots) != 1:
            raise SetupError("The archive has an unexpected layout, so it was not extracted.")
        # Only a fully inspected archive earns a folder of its own.
        destination.mkdir(parents=True, exist_ok=True)
        zipped.extractall(destination)
        return destination / roots.pop()


def install_packages(python: str, plan: list[tuple[str, str]]) -> list[str]:
    todo = missing_packages(plan)
    if not todo:
        print("Every planned package is already installed.", flush=True)
        return []
    print("\nInstalling: " + ", ".join(todo), flush=True)
    for pip_name, _reason in plan:
        if pip_name not in todo:
            continue
        run(python, "-m", "pip", "install", pip_name)
    return todo


def install_vosk_model() -> str:
    """Fetch the small Vosk model so the fallback engine works offline afterwards."""
    if vosk_model_present():
        return f"A Vosk model is already present in {vosk_model_root()}."
    with tempfile.TemporaryDirectory(prefix="weronika-vosk-") as temp_name:
        temp = Path(temp_name)
        archive = download_zip(VOSK_MODEL_URL, temp)
        extracted = extract_archive(archive, temp / "unpacked")
        target = vosk_model_root() / extracted.name
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extracted), str(target))
    return f"Installed the Vosk model at {target}."


def base_name(pip_name: str) -> str:
    """``faster-whisper>=1.0`` → ``faster-whisper``, so versions never confuse a comparison."""
    return str(pip_name).split(">")[0].split("=")[0].split("<")[0].strip()


def best_engine(planned: list[str], missing: list[str]) -> str:
    """The best speech engine that actually installed, or ``typed`` when none did."""
    have = {base_name(name) for name in planned if name not in missing}
    if "faster-whisper" in have:
        return "whisper"
    if "vosk" in have:
        return "vosk"
    return "typed"


def summarise(
    plan: list[tuple[str, str]],
    *,
    installed: list[str],
    model_note: str,
    engine_choice: str,
) -> dict[str, object]:
    """The final report, as data, so the orb can show it and the tests can check it."""
    planned = [name for name, _ in plan]
    still_missing = missing_packages(plan)
    engine = best_engine(planned, still_missing)
    if not still_missing:
        message = (
            f"Call audio is ready. Weronika will hear callers with {engine} and speak with the "
            "system voice. Restart Weronika with start.bat, then say “handle my calls”."
        )
    elif len(still_missing) == len(planned):
        message = (
            "Nothing was installed, so Weronika stays in typed mode: she still answers, still "
            "says she is an AI, and you type what the caller says."
        )
    else:
        message = (
            "Part of the call audio support installed ("
            + ", ".join(still_missing)
            + f" did not). Weronika will use {engine} and say so."
        )
    return {
        "engine": engine,
        "planned": planned,
        "installed": installed,
        "still_missing": still_missing,
        "model": model_note,
        "engine_choice": engine_choice,
        "message": message,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--engines",
        default="auto",
        choices=("auto", "whisper", "vosk"),
        help="Which speech engine to install. Default installs both: Whisper first, Vosk as the fallback.",
    )
    parser.add_argument("--no-models", action="store_true", help="Skip the small Vosk model download.")
    parser.add_argument("--no-voice", action="store_true", help="Skip the text-to-speech package.")
    parser.add_argument("--no-audio", action="store_true", help="Skip the microphone/line-in package.")
    parser.add_argument("--report", action="store_true", help="Print what is installed and exit; installs nothing.")
    return parser


def report_only() -> dict[str, object]:
    plan = [(pip_name, reason) for _import_name, pip_name, reason in PACKAGES]
    return summarise(plan, installed=[], model_note=(
        f"Vosk model present in {vosk_model_root()}." if vosk_model_present() else "No Vosk model installed yet."
    ), engine_choice="report")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    python = sys.executable
    if not Path(python).is_file():
        raise SetupError("Could not locate the active Weronika Python environment.")

    if args.report:
        report = report_only()
        print(f"Speech engines installed: {report['engine']}")
        print(f"Planned packages: {', '.join(str(name) for name in report['planned'])}")
        print(f"Missing packages: {', '.join(str(name) for name in report['still_missing']) or 'none'}")
        print(str(report["model"]))
        return 0

    plan = plan_packages(
        ("whisper", "vosk") if args.engines == "auto" else (args.engines,),
        with_audio=not args.no_audio,
        with_voice=not args.no_voice,
    )
    print("Weronika will install:", flush=True)
    for pip_name, reason in plan:
        print(f"  - {pip_name}: {reason}", flush=True)

    installed = install_packages(python, plan)

    model_note = "Skipped the Vosk model download (--no-models)."
    if not args.no_models and any(name == "vosk" for name, _ in plan):
        try:
            model_note = install_vosk_model()
        except SetupError as exc:
            # A failed model download must not undo the packages that did install; the
            # fallback simply stays unavailable and the report says so.
            model_note = f"The Vosk model could not be downloaded: {exc}"

    report = summarise(plan, installed=installed, model_note=model_note, engine_choice=args.engines)
    print("\n" + str(report["message"]), flush=True)
    print(str(report["model"]), flush=True)
    print("Audio from a call is never written to disk: it lives in memory for one utterance.", flush=True)
    print("Restart Weronika with start.bat, then say “handle my calls” in the orb.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, SetupError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"\nCall audio setup failed: {exc}", file=sys.stderr)
        print(
            "Weronika still works in typed mode. Rerun setup-calls.bat after installing a C/C++ "
            "build toolchain if a package failed to compile, or with --engines vosk for a lighter install.",
            file=sys.stderr,
        )
        raise SystemExit(1)
