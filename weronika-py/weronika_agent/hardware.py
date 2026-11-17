"""Best-effort local hardware inventory for Blueprint model selection."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess

from .blueprint import blueprint_status


def _total_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except (AttributeError, OSError):
            return None
        return None

    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _nvidia_gpus() -> list[dict[str, str]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            check=False,
            timeout=3,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    gpus = []
    for line in result.stdout.splitlines():
        name, separator, memory = line.partition(",")
        if not name.strip():
            continue
        gpu = {"name": name.strip()}
        if separator and memory.strip().isdigit():
            gpu["memory_mb"] = memory.strip()
        gpus.append(gpu)
    return gpus


def call_setup_status() -> dict[str, object]:
    """Call readiness: the audio side plus whether a phone can be reached over a cable.

    Both halves are cheap and best-effort. Nothing is installed, no browser is opened, and
    a missing piece is reported as a reason rather than a silent ``False``.
    """
    from .adb_calls import find_adb
    from .call_audio import speech_setup_status

    speech = speech_setup_status()
    adb = find_adb()
    speech["adb"] = str(adb) if adb else ""
    speech["adb_ready"] = bool(adb)
    speech["channels"] = ["phone (SIM)", "WhatsApp"]
    speech["telegram"] = (
        "Telegram calling is not possible on any surface Weronika can reach: Telegram Web has "
        "no calls and the Bot API cannot make or receive them. Telegram stays text-only."
    )
    return speech


def detect_hardware() -> dict[str, object]:
    """Return a non-sensitive, best-effort inventory; no model is run or downloaded."""
    total_memory = _total_memory_bytes()
    model = blueprint_status()
    return {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "processor": platform.processor() or "Unknown CPU",
        "cpu_threads": os.cpu_count() or 1,
        "memory_gb": round(total_memory / (1024**3), 1) if total_memory else None,
        "nvidia_gpus": _nvidia_gpus(),
        "model_runtime": "triposr-cpu-ready" if model["available"] else "not-configured",
        "blueprint_model": model,
        "call_setup": call_setup_status(),
    }
