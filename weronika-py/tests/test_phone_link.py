"""Checks for the cable phone scan that answers "will this work on my phone?" before a call.

The important assertions are the honest negative ones: an iPhone is reported as connected
but unable to have its SIM calls handled, and an Android phone that has not allowed USB
debugging is reported as connected but unusable — never as "no phone", which would invite
the owner to think nothing is plugged in.
"""

import unittest
from unittest import mock

from weronika_agent.adb_calls import CommandResult
from weronika_agent.phone_link import (
    ANDROID_UNAUTHORIZED_REASON,
    IPHONE_SIM_REASON,
    android_links,
    iphone_links,
    scan_links,
)

ADB = "/usr/bin/adb"
DEVICES = (ADB, "devices")


class FakeRunner:
    """Answers adb and platform probes from a table."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def add(self, args, stdout="", returncode=0, stderr=""):
        self.responses[tuple(args)] = CommandResult(returncode, stdout, stderr)
        return self

    def __call__(self, args, timeout):
        args = tuple(args)
        self.calls.append(args)
        return self.responses.get(args, CommandResult(0, "", ""))


def android_runner(*devices):
    """A runner whose `adb devices` lists ``devices`` as (serial, state) pairs."""
    runner = FakeRunner()
    listing = "List of devices attached\n" + "".join(
        f"{serial}\t{state}\n" for serial, state in devices
    )
    runner.add(DEVICES, listing)
    for serial, state in devices:
        if state == "device":
            runner.add((ADB, "-s", serial, "shell", "getprop", "ro.product.model"), "SM-A53 5G")
            runner.add((ADB, "-s", serial, "shell", "getprop", "ro.build.version.release"), "13")
    return runner


class AndroidScanTests(unittest.TestCase):
    def test_no_adb_says_so_and_still_offers_whatsapp(self):
        links = android_links(adb="", runner=FakeRunner())
        self.assertEqual(len(links), 1)
        link = links[0]
        self.assertFalse(link.connected)
        self.assertFalse(link.usable)
        self.assertFalse(link.can_handle_sim_calls)
        self.assertIn("adb was not found", link.reason)
        self.assertIn("platform-tools", link.reason)
        self.assertEqual(link.channels, ("whatsapp",))

    def test_adb_with_no_phone_says_the_phone_is_not_linked(self):
        runner = FakeRunner().add(DEVICES, "List of devices attached\n")
        link = android_links(adb=ADB, runner=runner)[0]
        self.assertFalse(link.connected)
        self.assertIn("No Android phone is linked", link.reason)
        self.assertIn("USB debugging", link.reason)
        self.assertEqual(link.channels, ("whatsapp",))

    def test_an_authorized_phone_can_have_its_sim_calls_handled(self):
        link = android_links(adb=ADB, runner=android_runner(("RZ8M12ABC", "device")))[0]
        self.assertEqual(link.kind, "android")
        self.assertEqual(link.identifier, "RZ8M12ABC")
        self.assertTrue(link.connected)
        self.assertTrue(link.usable)
        self.assertTrue(link.can_handle_sim_calls)
        self.assertIn("SM-A53 5G", link.name)
        self.assertIn("13", link.name)
        self.assertEqual(link.channels, ("sim", "whatsapp"))

    def test_a_ready_phone_still_says_its_audio_cannot_cross_the_cable(self):
        link = android_links(adb=ADB, runner=android_runner(("RZ8M12ABC", "device")))[0]
        self.assertIn("audio cannot", link.reason)
        for route in ("speaker", "Bluetooth", "line-in"):
            self.assertIn(route, link.reason)

    def test_a_phone_that_has_not_allowed_debugging_is_not_pretended_away(self):
        link = android_links(adb=ADB, runner=android_runner(("RZ8M12ABC", "unauthorized")))[0]
        self.assertTrue(link.connected, "the phone IS plugged in; only debugging is refused")
        self.assertFalse(link.usable)
        self.assertFalse(link.can_handle_sim_calls)
        self.assertEqual(link.reason, ANDROID_UNAUTHORIZED_REASON)
        self.assertIn("Allow USB debugging", link.reason)

    def test_an_offline_phone_is_reported_as_unusable_rather_than_ready(self):
        link = android_links(adb=ADB, runner=android_runner(("RZ8M12ABC", "offline")))[0]
        self.assertTrue(link.connected)
        self.assertFalse(link.can_handle_sim_calls)

    def test_a_phone_in_some_other_state_is_ignored_entirely(self):
        runner = FakeRunner().add(DEVICES, "List of devices attached\nemulator-5554\trecovery\n")
        links = android_links(adb=ADB, runner=runner)
        self.assertEqual(len(links), 1)
        self.assertFalse(links[0].connected)
        self.assertIn("No Android phone is linked", links[0].reason)

    def test_two_phones_give_two_verdicts(self):
        runner = android_runner(("RZ8M12ABC", "device"), ("SERIAL2", "unauthorized"))
        runner.add((ADB, "-s", "SERIAL2", "shell", "getprop", "ro.product.model"), "")
        links = android_links(adb=ADB, runner=runner)
        self.assertEqual([link.identifier for link in links], ["RZ8M12ABC", "SERIAL2"])
        self.assertEqual([link.can_handle_sim_calls for link in links], [True, False])

    def test_a_model_that_cannot_be_read_still_produces_a_named_link(self):
        runner = FakeRunner().add(DEVICES, "List of devices attached\nRZ8M12ABC\tdevice\n")
        runner.add((ADB, "-s", "RZ8M12ABC", "shell", "getprop", "ro.product.model"), "", returncode=1)
        runner.add((ADB, "-s", "RZ8M12ABC", "shell", "getprop", "ro.build.version.release"), "", returncode=1)
        link = android_links(adb=ADB, runner=runner)[0]
        self.assertTrue(link.can_handle_sim_calls)
        self.assertEqual(link.name, "Android phone")


class IPhoneScanTests(unittest.TestCase):
    def test_no_apple_device_means_no_iphone_link(self):
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value=None):
            self.assertEqual(iphone_links(runner=FakeRunner()), [])

    def test_an_iphone_is_detected_and_honestly_refused_for_sim_calls(self):
        runner = FakeRunner().add(("/usr/bin/idevice_id", "-l"), "00008101-000A1B2C3D4E5F60\n")
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value="/usr/bin/idevice_id"):
            links = iphone_links(runner=runner)
        self.assertEqual(len(links), 1)
        link = links[0]
        self.assertEqual(link.kind, "iphone")
        self.assertTrue(link.connected)
        self.assertFalse(link.usable)
        self.assertFalse(link.can_handle_sim_calls)
        self.assertEqual(link.identifier, "00008101-000A1B2C3D4E5F60")
        self.assertEqual(link.reason, IPHONE_SIM_REASON)
        self.assertEqual(link.channels, ("whatsapp",))

    def test_the_iphone_reason_offers_the_route_that_does_work(self):
        self.assertIn("WhatsApp", IPHONE_SIM_REASON)
        self.assertIn("messages", IPHONE_SIM_REASON)

    def test_a_linux_usb_probe_can_find_an_apple_phone(self):
        runner = FakeRunner().add(("/usr/bin/lsusb",), "Bus 001 Device 005: ID 05ac:12a8 Apple, Inc. iPhone\n")
        which = lambda name: {"idevice_id": None, "lsusb": "/usr/bin/lsusb"}.get(name)  # noqa: E731
        with mock.patch("weronika_agent.phone_link.shutil.which", side_effect=which), \
                mock.patch("weronika_agent.phone_link.platform.system", return_value="Linux"):
            links = iphone_links(runner=runner)
        self.assertEqual(len(links), 1)
        self.assertFalse(links[0].can_handle_sim_calls)

    def test_a_usb_probe_that_finds_nothing_reports_nothing(self):
        runner = FakeRunner().add(("/usr/bin/lsusb",), "Bus 001 Device 002: ID 0bda:8153 Realtek USB LAN\n")
        which = lambda name: {"idevice_id": None, "lsusb": "/usr/bin/lsusb"}.get(name)  # noqa: E731
        with mock.patch("weronika_agent.phone_link.shutil.which", side_effect=which), \
                mock.patch("weronika_agent.phone_link.platform.system", return_value="Linux"):
            self.assertEqual(iphone_links(runner=runner), [])

    def test_a_windows_probe_looks_for_the_apple_mobile_device_driver(self):
        runner = FakeRunner().add(
            ("C:/Windows/pnputil.exe", "/enum-devices", "/connected"),
            "Instance ID: USB\\VID_05AC&PID_12A8\\Apple Mobile Device USB\n",
        )
        which = lambda name: {"idevice_id": None, "pnputil": "C:/Windows/pnputil.exe"}.get(name)  # noqa: E731
        with mock.patch("weronika_agent.phone_link.shutil.which", side_effect=which), \
                mock.patch("weronika_agent.phone_link.platform.system", return_value="Windows"):
            links = iphone_links(runner=runner)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].kind, "iphone")

    def test_a_failing_probe_is_not_reported_as_a_phone(self):
        runner = FakeRunner().add(("/usr/bin/idevice_id", "-l"), "", returncode=1, stderr="no device")
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value=None):
            self.assertEqual(iphone_links(runner=runner), [])


class ScanReportTests(unittest.TestCase):
    def test_a_report_with_no_phone_points_at_whatsapp(self):
        runner = FakeRunner().add(DEVICES, "List of devices attached\n")
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value=None):
            report = scan_links(adb=ADB, runner=runner)
        self.assertEqual(report["sim_ready"], [])
        self.assertIn("No phone on the cable can have its SIM calls handled", report["summary"])
        self.assertIn("WhatsApp", report["summary"])
        self.assertTrue(report["adb"])

    def test_a_report_with_a_ready_phone_counts_it(self):
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value=None):
            report = scan_links(adb=ADB, runner=android_runner(("RZ8M12ABC", "device")))
        self.assertEqual(len(report["sim_ready"]), 1)
        self.assertIn("1 Android phone(s) can have their SIM calls handled", report["summary"])
        self.assertEqual(report["links"], report["sim_ready"])

    def test_a_report_with_both_phones_separates_them(self):
        runner = android_runner(("RZ8M12ABC", "device"))
        runner.add(("/usr/bin/idevice_id", "-l"), "00008101-ABC\n")
        with mock.patch("weronika_agent.phone_link.shutil.which", side_effect=(
            lambda name: "/usr/bin/idevice_id" if name == "idevice_id" else None)):
            report = scan_links(adb=ADB, runner=runner)
        self.assertEqual(len(report["links"]), 2)
        self.assertEqual([link["kind"] for link in report["links"]], ["android", "iphone"])
        self.assertEqual(len(report["sim_ready"]), 1)
        self.assertIn("An iPhone was detected; SIM calls cannot be handled on it.", report["summary"])

    def test_a_report_without_adb_says_adb_is_missing(self):
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value=None):
            report = scan_links(adb="", runner=FakeRunner())
        self.assertFalse(report["adb"])
        self.assertIn("adb was not found", report["android"][0]["reason"])

    def test_every_link_is_plain_data_for_the_orb(self):
        with mock.patch("weronika_agent.phone_link.shutil.which", return_value=None):
            report = scan_links(adb=ADB, runner=android_runner(("RZ8M12ABC", "device")))
        link = report["links"][0]
        self.assertEqual(
            sorted(link),
            ["can_handle_sim_calls", "channels", "connected", "identifier", "kind", "name", "reason", "usable"],
        )
        self.assertIsInstance(link["channels"], list)

    def test_a_link_with_no_name_still_reads_as_a_phone(self):
        from weronika_agent.phone_link import PhoneLink

        blank = PhoneLink(kind="android", name="", identifier="X", connected=True, usable=False,
                          can_handle_sim_calls=False)
        self.assertEqual(blank.to_dict()["name"], "Android phone")
        apple = PhoneLink(kind="iphone", name="", identifier="Y", connected=True, usable=False,
                          can_handle_sim_calls=False)
        self.assertEqual(apple.to_dict()["name"], "iPhone")


if __name__ == "__main__":
    unittest.main()
