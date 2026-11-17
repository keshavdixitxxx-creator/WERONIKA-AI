"""Checks for the phone-over-cable (adb) call adapter.

The fixtures below are the shapes real ``dumpsys`` output takes on different Android
versions, including the ones that are hardest to tell apart: a ringing call, an idle
phone, and a legend line that merely mentions call states.
"""

import unittest

from weronika_agent.adb_calls import (
    AdbError,
    CommandResult,
    PhoneCallAdapter,
    PhoneDevice,
    list_phones,
    parse_audio_route,
    parse_call_state,
    parse_contact_name,
    parse_uiautomator_buttons,
)
from weronika_agent.models import CallChannel, CallRoute

ADB = "/usr/bin/adb"
SERIAL = "RZ8M12ABC"

GROUPED_RINGING = """
TELECOM DUMP
Telecom version: 1.0
mCallsManager:
  mCallIdToCall:
Call #0:
state: RINGING
isExternal: true
handle: tel:+919876543210
callerDisplayName: Rahul Sharma
connectTimeMillis: 0
mConnectionService: com.android.phone
"""

GROUPED_ACTIVE = """
TELECOM DUMP
Call #0:
state: ACTIVE
handle: tel:+919876543210
callerDisplayName: Rahul Sharma
"""

GROUPED_IDLE = """
TELECOM DUMP
mCallsManager:
  mCallIdToCall:
Call #0:
state: DISCONNECTED
handle: tel:+919876543210
"""

INLINE_RINGING = """
mCalls:
  Call@f2a1b: state=RINGING handle=tel:+919812345678 callerDisplayName=Priya video=false
"""

LEGEND_ONLY = """
CallState notes:
  A call state can be RINGING or ACTIVE depending on the modem.
  Nothing is happening on this phone right now.
mCallState=0
"""

REGISTRY_RINGING = """
TelephonyRegistry:
mCallState=1
mCallIncomingNumber=+919876543210
mServiceState=0
"""

REGISTRY_OFFHOOK = """
mCallState=2
mCallIncomingNumber=+919876543210
"""

AUDIO_SPEAKER = """
Audio Service dump
  mode: MODE_IN_COMMUNICATION
  communication device: DEVICE_OUT_SPEAKER
  devices: speaker
"""

AUDIO_BLUETOOTH = """
Audio Service dump
  mode: MODE_IN_COMMUNICATION
  setCommunicationDevice(bt_sco_headset)
  current communication device: bluetooth_sco
"""

AUDIO_WIRED = """
Audio Service dump
  mode: MODE_IN_COMMUNICATION
  communication device: DEVICE_OUT_WIRED_HEADSET
"""

UI_DUMP_RINGING = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy rotation="0">
  <node index="0" text="Rahul Sharma" resource-id="com.android.incallui:id/name" class="android.widget.TextView" clickable="false" bounds="[120,300][960,380]" />
  <node index="1" text="" content-desc="Decline" resource-id="com.android.incallui:id/declineButton" class="android.widget.ImageButton" clickable="true" bounds="[120,1500][420,1700]" />
  <node index="2" text="Accept" content-desc="Answer the call" resource-id="com.android.incallui:id/answerButton" class="android.widget.ImageButton" clickable="true" bounds="[660,1500][960,1700]" />
</hierarchy>
"""

UI_DUMP_IN_CALL = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy rotation="0">
  <node index="0" text="Mute" content-desc="Mute" class="android.widget.TextView" clickable="true" bounds="[60,1400][300,1560]" />
  <node index="1" text="Speaker" content-desc="Turn on speakerphone" class="android.widget.TextView" clickable="true" bounds="[380,1400][620,1560]" />
  <node index="2" text="End" content-desc="End call" class="android.widget.TextView" clickable="true" bounds="[700,1400][940,1560]" />
</hierarchy>
"""


class FakeRunner:
    """Answers adb commands from a table, and remembers everything that was run."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def add(self, args, stdout="", returncode=0, stderr=""):
        self.responses[tuple(args)] = [CommandResult(returncode, stdout, stderr)]
        return self

    def queue(self, args, *results):
        self.responses[tuple(args)] = list(results)
        return self

    def __call__(self, args, timeout):
        args = tuple(args)
        self.calls.append(args)
        queued = self.responses.get(args)
        if not queued:
            return CommandResult(0, "", "")
        if len(queued) == 1:
            return queued[0]
        return queued.pop(0)

    def ran(self, *fragment):
        return any(all(part in list(args) for part in fragment) for args in self.calls)

    def shell_args(self):
        """The shell command tails, for readable assertions."""
        tails = []
        for args in self.calls:
            if "shell" in args:
                tails.append(tuple(args[args.index("shell") + 1 :]))
        return tails


def device(authorized=True):
    return PhoneDevice(serial=SERIAL, model="SM-A53", android_version="13", authorized=authorized)


def adapter(runner, dev=None, adb=ADB):
    return PhoneCallAdapter(dev if dev is not None else device(), adb=adb, runner=runner)


class ParseCallStateTests(unittest.TestCase):
    def test_a_grouped_dump_reports_the_ringing_call_and_its_number(self):
        calls = parse_call_state(GROUPED_RINGING)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].state, "ringing")
        self.assertTrue(calls[0].ringing)
        self.assertEqual(calls[0].number, "+919876543210")
        self.assertEqual(calls[0].name, "Rahul Sharma")

    def test_an_active_call_is_reported_as_connected_not_ringing(self):
        calls = parse_call_state(GROUPED_ACTIVE)
        self.assertEqual(calls[0].state, "active")
        self.assertTrue(calls[0].active)
        self.assertFalse(calls[0].ringing)

    def test_a_disconnected_call_is_not_a_call_to_answer(self):
        self.assertEqual(parse_call_state(GROUPED_IDLE), [])

    def test_a_one_line_dump_is_understood(self):
        calls = parse_call_state(INLINE_RINGING)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].number, "+919812345678")
        self.assertEqual(calls[0].name, "Priya")

    def test_a_legend_mentioning_states_is_not_a_call(self):
        self.assertEqual(parse_call_state(LEGEND_ONLY), [])

    def test_the_registry_is_the_fallback_when_telecom_says_nothing(self):
        calls = parse_call_state("", REGISTRY_RINGING)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].ringing)
        self.assertEqual(calls[0].number, "+919876543210")

    def test_an_offhook_registry_line_means_the_call_is_connected(self):
        calls = parse_call_state("", REGISTRY_OFFHOOK)
        self.assertTrue(calls[0].active)

    def test_an_idle_registry_reports_no_call(self):
        self.assertEqual(parse_call_state("", "mCallState=0\nmCallIncomingNumber="), [])

    def test_garbage_is_reported_as_no_call_instead_of_raising(self):
        self.assertEqual(parse_call_state("", ""), [])
        self.assertEqual(parse_call_state("permission denied", "error: device offline"), [])


class ParseAudioRouteTests(unittest.TestCase):
    def test_speaker_bluetooth_and_wired_are_told_apart(self):
        self.assertEqual(parse_audio_route(AUDIO_SPEAKER), CallRoute.SPEAKER_MIC)
        self.assertEqual(parse_audio_route(AUDIO_BLUETOOTH), CallRoute.BLUETOOTH)
        self.assertEqual(parse_audio_route(AUDIO_WIRED), CallRoute.AUX)

    def test_nothing_recognisable_means_no_route(self):
        self.assertEqual(parse_audio_route(""), CallRoute.NONE)


class ParseUiButtonsTests(unittest.TestCase):
    def test_the_answer_and_decline_buttons_are_found_with_their_centres(self):
        accept = parse_uiautomator_buttons(UI_DUMP_RINGING, ("accept", "answer"))
        self.assertEqual(accept, [(810, 1600, "Accept")])
        decline = parse_uiautomator_buttons(UI_DUMP_RINGING, ("decline", "reject"))
        self.assertEqual(decline, [(270, 1600, "Decline")])

    def test_a_label_on_a_non_clickable_node_is_not_tappable(self):
        # "Rahul Sharma" is text, not a button, and must never be tapped.
        self.assertEqual(parse_uiautomator_buttons(UI_DUMP_RINGING, ("rahul",)), [])

    def test_the_speaker_button_is_found_during_a_call(self):
        speaker = parse_uiautomator_buttons(UI_DUMP_IN_CALL, ("speaker",))
        self.assertEqual(speaker, [(500, 1480, "Speaker")])

    def test_an_empty_dump_yields_nothing(self):
        self.assertEqual(parse_uiautomator_buttons("", ("accept",)), [])


class ParseContactNameTests(unittest.TestCase):
    def test_a_content_query_row_gives_the_display_name(self):
        row = "Row: 0 display_name=Rahul Sharma, data1=+919876543210"
        self.assertEqual(parse_contact_name(row), "Rahul Sharma")

    def test_no_row_means_no_name(self):
        self.assertEqual(parse_contact_name("No result found."), "")


class CapabilitiesTests(unittest.TestCase):
    def test_without_adb_the_channel_reports_why_it_is_unavailable(self):
        report = adapter(FakeRunner(), adb="").capabilities()
        self.assertFalse(report["available"])
        self.assertFalse(report["answer"])
        self.assertIn("adb", str(report["reason"]).lower())

    def test_an_unauthorized_phone_is_reported_with_the_fix(self):
        report = adapter(FakeRunner(), dev=device(authorized=False)).capabilities()
        self.assertFalse(report["available"])
        self.assertIn("Allow", str(report["reason"]))

    def test_a_linked_phone_can_be_driven_but_carries_no_audio(self):
        runner = FakeRunner().add([ADB, "-s", SERIAL, "shell", "dumpsys", "audio"], AUDIO_SPEAKER)
        report = adapter(runner).capabilities()
        self.assertTrue(report["available"])
        self.assertTrue(report["detect"])
        self.assertTrue(report["answer"])
        self.assertFalse(report["audio_over_cable"])
        self.assertEqual(report["phone_audio_route"], "speaker_mic")
        self.assertEqual(report["device"]["model"], "SM-A53")

    def test_the_honest_note_says_audio_cannot_come_through_the_cable(self):
        runner = FakeRunner().add([ADB, "-s", SERIAL, "shell", "dumpsys", "audio"], AUDIO_SPEAKER)
        note = str(adapter(runner).capabilities()["note"])
        self.assertIn("audio cannot", note)


class DetectionTests(unittest.TestCase):
    def test_a_ringing_call_becomes_an_incoming_call_on_the_sim_channel(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], GROUPED_RINGING)
        calls = adapter(runner).ringing_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].channel, CallChannel.SIM)
        self.assertEqual(calls[0].caller, "Rahul Sharma")
        self.assertEqual(calls[0].number, "+919876543210")
        self.assertEqual(calls[0].device, SERIAL)

    def test_a_number_with_no_name_is_looked_up_in_the_phones_contacts(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], "")
        runner.add([ADB, "-s", SERIAL, "shell", "dumpsys", "telephony.registry"], REGISTRY_RINGING)
        runner.add(
            [
                ADB, "-s", SERIAL, "shell", "content", "query",
                "--uri", "content://com.android.contacts/data/phones",
                "--projection", "display_name:data1",
                "--where", "data1='+919876543210'",
            ],
            "Row: 0 display_name=Rahul Sharma, data1=+919876543210",
        )
        calls = adapter(runner).ringing_calls()
        self.assertEqual(calls[0].caller, "Rahul Sharma")

    def test_an_idle_phone_reports_no_call(self):
        runner = FakeRunner().add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], GROUPED_IDLE)
        self.assertEqual(adapter(runner).ringing_calls(), [])

    def test_a_dump_the_phone_refuses_is_reported_not_guessed(self):
        runner = FakeRunner()
        runner.queue(
            [ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"],
            CommandResult(1, "", "error: device offline"),
        )
        runner.queue(
            [ADB, "-s", SERIAL, "shell", "dumpsys", "telephony.registry"],
            CommandResult(1, "", "error: device offline"),
        )
        with self.assertRaises(AdbError):
            adapter(runner).ringing_calls()


class NumberSafetyTests(unittest.TestCase):
    def test_a_number_that_is_not_digits_is_never_put_in_a_command(self):
        runner = FakeRunner()
        adapter(runner).lookup_name("+91 98; rm -rf /sdcard")
        self.assertEqual(runner.calls, [])

    def test_a_quoted_injection_attempt_is_never_put_in_a_command(self):
        runner = FakeRunner()
        adapter(runner).lookup_name("1' OR '1'='1")
        self.assertEqual(runner.calls, [])

    def test_a_valid_number_queries_the_phones_contacts(self):
        runner = FakeRunner().add(
            [
                ADB, "-s", SERIAL, "shell", "content", "query",
                "--uri", "content://com.android.contacts/data/phones",
                "--projection", "display_name:data1",
                "--where", "data1='+919876543210'",
            ],
            "Row: 0 display_name=Rahul Sharma, data1=+919876543210",
        )
        self.assertEqual(adapter(runner).lookup_name("+919876543210"), "Rahul Sharma")


class AnswerTests(unittest.TestCase):
    def test_answering_uses_a_key_event_and_is_verified_by_the_state(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "input", "keyevent", "KEYCODE_CALL"])
        runner.queue(
            [ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"],
            CommandResult(0, GROUPED_RINGING, ""),
            CommandResult(0, GROUPED_ACTIVE, ""),
        )
        adapter(runner).answer()
        self.assertTrue(runner.ran("input", "keyevent", "KEYCODE_CALL"))

    def test_when_the_key_event_does_not_work_the_answer_button_is_tapped(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "input", "keyevent", "KEYCODE_CALL"])
        runner.add([ADB, "-s", SERIAL, "shell", "input", "keyevent", "KEYCODE_HEADSETHOOK"])
        runner.add([ADB, "-s", SERIAL, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], "UI hierchary dumped to: /sdcard/window_dump.xml")
        runner.add([ADB, "-s", SERIAL, "shell", "cat", "/sdcard/window_dump.xml"], UI_DUMP_RINGING)
        runner.add([ADB, "-s", SERIAL, "shell", "input", "tap", "810", "1600"])
        runner.queue(
            [ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"],
            CommandResult(0, GROUPED_RINGING, ""),
            CommandResult(0, GROUPED_RINGING, ""),
            CommandResult(0, GROUPED_ACTIVE, ""),
        )
        adapter(runner).answer()
        self.assertTrue(runner.ran("input", "tap", "810", "1600"))

    def test_an_answer_the_phone_does_not_confirm_is_reported_as_a_failure(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], GROUPED_RINGING)
        with self.assertRaises(AdbError) as caught:
            adapter(runner).answer()
        self.assertIn("did not confirm", str(caught.exception))

    def test_hanging_up_stops_when_the_phone_confirms_the_call_ended(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "input", "keyevent", "KEYCODE_ENDCALL"])
        runner.add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], GROUPED_IDLE)
        adapter(runner).hang_up()
        self.assertTrue(runner.ran("input", "keyevent", "KEYCODE_ENDCALL"))
        self.assertFalse(runner.ran("uiautomator"))

    def test_the_end_button_is_tapped_when_the_key_event_does_not_drop_the_call(self):
        runner = FakeRunner()
        runner.add([ADB, "-s", SERIAL, "shell", "input", "keyevent", "KEYCODE_ENDCALL"])
        runner.add([ADB, "-s", SERIAL, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], "dumped")
        runner.add([ADB, "-s", SERIAL, "shell", "cat", "/sdcard/window_dump.xml"], UI_DUMP_IN_CALL)
        runner.add([ADB, "-s", SERIAL, "shell", "input", "tap", "820", "1480"])
        runner.queue(
            [ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"],
            CommandResult(0, GROUPED_ACTIVE, ""),
            CommandResult(0, GROUPED_IDLE, ""),
        )
        adapter(runner).hang_up()
        self.assertTrue(runner.ran("input", "tap", "820", "1480"))

    def test_a_call_that_stays_connected_after_hanging_up_is_an_error(self):
        runner = FakeRunner().add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], GROUPED_ACTIVE)
        with self.assertRaises(AdbError):
            adapter(runner).hang_up()

    def test_declining_a_call_that_already_stopped_does_nothing(self):
        runner = FakeRunner().add([ADB, "-s", SERIAL, "shell", "dumpsys", "telecom"], GROUPED_IDLE)
        adapter(runner).decline()
        self.assertEqual(runner.shell_args(), [("dumpsys", "telecom"), ("dumpsys", "telephony.registry")])


class SpeakerTests(unittest.TestCase):
    def test_a_phone_already_on_speaker_is_left_alone(self):
        runner = FakeRunner().add([ADB, "-s", SERIAL, "shell", "dumpsys", "audio"], AUDIO_SPEAKER)
        adapter(runner).set_speaker(enabled=True)
        self.assertFalse(runner.ran("uiautomator"))

    def test_the_speaker_button_is_tapped_when_the_phone_is_on_the_earpiece(self):
        runner = FakeRunner()
        runner.queue(
            [ADB, "-s", SERIAL, "shell", "dumpsys", "audio"],
            CommandResult(0, AUDIO_BLUETOOTH, ""),
            CommandResult(0, AUDIO_SPEAKER, ""),
        )
        runner.add([ADB, "-s", SERIAL, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], "dumped")
        runner.add([ADB, "-s", SERIAL, "shell", "cat", "/sdcard/window_dump.xml"], UI_DUMP_IN_CALL)
        runner.add([ADB, "-s", SERIAL, "shell", "input", "tap", "500", "1480"])
        adapter(runner).set_speaker(enabled=True)
        self.assertTrue(runner.ran("input", "tap", "500", "1480"))


class ListPhonesTests(unittest.TestCase):
    def test_devices_are_listed_with_their_authorization_state(self):
        runner = FakeRunner()
        runner.add(
            [ADB, "devices"],
            "List of devices attached\nRZ8M12ABC\tdevice\nEMULATOR5554\tunauthorized\n\n",
        )
        runner.add([ADB, "-s", "RZ8M12ABC", "shell", "getprop", "ro.product.model"], "SM-A53 5G")
        runner.add([ADB, "-s", "RZ8M12ABC", "shell", "getprop", "ro.build.version.release"], "13")
        phones = list_phones(adb=ADB, runner=runner)
        self.assertEqual([phone.serial for phone in phones], ["RZ8M12ABC", "EMULATOR5554"])
        self.assertEqual(phones[0].model, "SM-A53 5G")
        self.assertTrue(phones[0].authorized)
        self.assertFalse(phones[1].authorized)

    def test_without_adb_there_are_no_phones(self):
        self.assertEqual(list_phones(adb="", runner=FakeRunner()), [])

    def test_an_offline_device_is_not_treated_as_usable(self):
        runner = FakeRunner().add([ADB, "devices"], "List of devices attached\nRZ8M12ABC\toffline\n")
        phones = list_phones(adb=ADB, runner=runner)
        self.assertEqual(len(phones), 1)
        self.assertFalse(phones[0].authorized)


if __name__ == "__main__":
    unittest.main()
