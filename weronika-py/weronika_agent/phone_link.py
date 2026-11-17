"""Which phones this computer can see over a cable, and what each one really allows.

The point of this module is to answer one question honestly before a call ever rings:
*can Weronika take a SIM call on this phone?* The answer differs by platform, and the
difference is not a matter of effort:

* **Android over USB debugging** — yes. ``adb`` reports the ringing call and accepts the
  key events that answer and end it, which is what :mod:`adb_calls` drives. The call's
  audio still has to travel by speaker, Bluetooth, or cable, because Android does not
  send call audio over adb.
* **iPhone** — no. iOS exposes nothing equivalent to adb for telephony: a laptop cannot
  read a ringing cellular call, answer it, or hear it through the cable. Weronika can
  still handle the owner's **WhatsApp** calls in the signed-in browser window, and can
  read and answer iPhone messages through the existing messaging flows. Saying so here,
  in the setup panel, is better than a button that silently does nothing.

Detection is best-effort and never invents a device: an Android phone that is connected
but has not allowed USB debugging is reported as connected and unusable, with the exact
tap that fixes it.
"""

from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass
from typing import Callable, Sequence

from .adb_calls import ADB_COMMAND_TIMEOUT_SECONDS, CommandResult, PhoneDevice, find_adb, list_phones

IPHONE_SIM_REASON = (
    "An iPhone cannot be driven over the cable: iOS has no equivalent of adb for telephony, "
    "so a laptop cannot see a ringing SIM call, answer it, or hear it. Weronika can handle "
    "your WhatsApp calls in the signed-in browser window instead, and can still send and read "
    "your messages."
)

ANDROID_UNAUTHORIZED_REASON = (
    "The phone is connected but has not allowed USB debugging. Unlock it, tap “Allow” on the "
    "“Allow USB debugging?” prompt (tick “Always allow from this computer”), and scan again."
)


@dataclass(frozen=True)
class PhoneLink:
    """One phone this computer can see, and what it can be asked to do."""

    kind: str  # "android" or "iphone"
    name: str
    identifier: str
    connected: bool
    usable: bool
    can_handle_sim_calls: bool
    reason: str = ""
    channels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "name": self.name or ("Android phone" if self.kind == "android" else "iPhone"),
            "identifier": self.identifier,
            "connected": self.connected,
            "usable": self.usable,
            "can_handle_sim_calls": self.can_handle_sim_calls,
            "reason": self.reason,
            "channels": list(self.channels),
        }


def android_links(
    adb: str | None = None, runner: Callable[[Sequence[str], float], CommandResult] | None = None
) -> list[PhoneLink]:
    """Every Android device on the cable, with its debugging state turned into a verdict."""
    executable = adb if adb is not None else find_adb()
    if not executable:
        return [
            PhoneLink(
                kind="android",
                name="Android phone",
                identifier="",
                connected=False,
                usable=False,
                can_handle_sim_calls=False,
                reason=(
                    "adb was not found on this computer, so no Android phone can be driven. "
                    "Install Android platform-tools, or point WERONIKA_ADB at the adb executable."
                ),
                channels=("whatsapp",),
            )
        ]
    devices: list[PhoneDevice] = list_phones(adb=executable, runner=runner)
    if not devices:
        return [
            PhoneLink(
                kind="android",
                name="Android phone",
                identifier="",
                connected=False,
                usable=False,
                can_handle_sim_calls=False,
                reason=(
                    "No Android phone is linked over the cable. Plug it in, choose “File transfer” "
                    "for the USB mode, and switch on USB debugging in Developer options."
                ),
                channels=("whatsapp",),
            )
        ]
    links: list[PhoneLink] = []
    for device in devices:
        if not device.authorized:
            links.append(
                PhoneLink(
                    kind="android",
                    name=device.model or "Android phone",
                    identifier=device.serial,
                    connected=True,
                    usable=False,
                    can_handle_sim_calls=False,
                    reason=ANDROID_UNAUTHORIZED_REASON,
                    channels=("whatsapp",),
                )
            )
            continue
        label = " · ".join(part for part in (device.model, device.android_version) if part)
        links.append(
            PhoneLink(
                kind="android",
                name=label or "Android phone",
                identifier=device.serial,
                connected=True,
                usable=True,
                can_handle_sim_calls=True,
                reason=(
                    "SIM calls can be seen and answered over the cable. Their audio cannot: use the "
                    "phone's speaker with this computer's microphone, a Bluetooth hands-free pairing, "
                    "or a 3.5 mm cable into line-in."
                ),
                channels=("sim", "whatsapp"),
            )
        )
    return links


def iphone_links(
    runner: Callable[[Sequence[str], float], CommandResult] | None = None
) -> list[PhoneLink]:
    """Detect an Apple phone well enough to explain what it cannot do."""
    run = runner
    identifier = ""
    detected = False

    idevice = shutil.which("idevice_id")
    if idevice:
        if run is None:
            from .adb_calls import _subprocess_runner as run  # type: ignore[assignment]
        result = run([idevice, "-l"], ADB_COMMAND_TIMEOUT_SECONDS)
        if result.returncode == 0 and result.stdout.strip():
            identifier = result.stdout.strip().splitlines()[0].strip()
            detected = True

    if not detected:
        system = platform.system()
        if system == "Darwin":
            probe = shutil.which("system_profiler")
            needle = "iphone"
            args = [probe, "SPUSBDataType"] if probe else []
        elif system == "Linux":
            probe = shutil.which("lsusb")
            needle = "apple"
            args = [probe] if probe else []
        else:
            probe = shutil.which("pnputil")
            needle = "apple mobile device"
            args = [probe, "/enum-devices", "/connected"] if probe else []
        if probe and args:
            if run is None:
                from .adb_calls import _subprocess_runner as run  # type: ignore[assignment]
            result = run(args, ADB_COMMAND_TIMEOUT_SECONDS)
            if result.returncode == 0 and needle in (result.stdout or "").casefold():
                detected = True

    if not detected:
        return []
    return [
        PhoneLink(
            kind="iphone",
            name="iPhone",
            identifier=identifier,
            connected=True,
            usable=False,
            can_handle_sim_calls=False,
            reason=IPHONE_SIM_REASON,
            channels=("whatsapp",),
        )
    ]


def scan_links(
    adb: str | None = None,
    runner: Callable[[Sequence[str], float], CommandResult] | None = None,
) -> dict[str, object]:
    """One report of every phone on the cable and what Weronika can do with each.

    This is what the orb's CALL WATCH panel shows before any call rings, so the answer to
    "will this work on my phone?" does not have to wait for a missed call.
    """
    android = android_links(adb=adb, runner=runner)
    apple = iphone_links(runner=runner)
    links = [*android, *apple]
    sim_ready = [link for link in links if link.can_handle_sim_calls]
    summary = []
    if sim_ready:
        summary.append(
            f"{len(sim_ready)} Android phone(s) can have their SIM calls handled over the cable."
        )
    else:
        summary.append(
            "No phone on the cable can have its SIM calls handled right now. "
            "WhatsApp calls in the signed-in browser window are the other route."
        )
    if any(link.kind == "iphone" for link in apple):
        summary.append("An iPhone was detected; SIM calls cannot be handled on it.")
    return {
        "links": [link.to_dict() for link in links],
        "sim_ready": [link.to_dict() for link in sim_ready],
        "android": [link.to_dict() for link in android],
        "iphone": [link.to_dict() for link in apple],
        "summary": " ".join(summary),
        "adb": bool(adb if adb is not None else find_adb()),
    }
