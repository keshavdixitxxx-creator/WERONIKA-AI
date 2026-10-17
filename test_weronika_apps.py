"""Offline safety and routing tests for local signed-in app automation."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from weronika_apps import (
    LocalAppBrowser,
    _format_google_dates,
    _line_delta,
    _safe_datetime,
    normalize_app,
)


class AppHelperTests(unittest.TestCase):
    def test_only_allowlisted_apps_are_supported(self):
        self.assertEqual(normalize_app("Gmail"), "gmail")
        self.assertEqual(normalize_app("Google Calendar"), "google_calendar")
        self.assertEqual(normalize_app("Outlook Calendar"), "microsoft_calendar")
        with self.assertRaisesRegex(ValueError, "supported apps"):
            normalize_app("https://attacker.example")

    def test_calendar_dates_are_validated_and_converted_to_utc(self):
        start = _safe_datetime("2026-10-17T15:00", "Asia/Kolkata")
        end = _safe_datetime("2026-10-17T16:00", "Asia/Kolkata")
        self.assertEqual(_format_google_dates(start, end), "20261017T093000Z/20261017T103000Z")
        with self.assertRaisesRegex(ValueError, "ISO date/time"):
            _safe_datetime("tomorrow evening", "Asia/Kolkata")

    def test_family_monitor_delta_returns_only_new_visible_lines(self):
        self.assertEqual(
            _line_delta("Mom\nOld note\n", "Mom\nOld note\nNew message from Mom"),
            "New message from Mom",
        )


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="weronika-app-browser-")
        self.browser = LocalAppBrowser(profile_dir=self.tmp.name)

    def tearDown(self):
        self.browser.shutdown()
        self.tmp.cleanup()

    def test_invalid_action_and_unknown_app_do_not_start_browser(self):
        bad_action = self.browser.perform("run_shell", {"command": "echo nope"})
        bad_app = self.browser.perform("open", {"app": "https://attacker.example"})
        self.assertFalse(bad_action["ok"])
        self.assertFalse(bad_app["ok"])
        self.assertIsNone(self.browser._context)

    def test_send_requires_live_one_time_confirmation(self):
        token = "send-once"
        self.browser._pending[token] = {
            "kind": "send", "app": "whatsapp", "created": __import__("time").time(), "target": "Mom",
        }
        click = Mock()
        button = SimpleNamespace(click=click)
        fake_page = SimpleNamespace(
            get_by_role=Mock(return_value=object()),
            locator=Mock(return_value=object()),
            wait_for_timeout=Mock(),
        )
        self.browser._app_page = Mock(return_value=fake_page)
        self.browser._first_visible = Mock(return_value=button)

        cancelled = self.browser.perform("confirm", {"confirmation_token": token, "confirm": False})
        self.assertTrue(cancelled["ok"])
        self.assertFalse(cancelled["confirmed"])
        self.assertEqual(click.call_count, 0)
        self.assertNotIn(token, self.browser._pending)

    def test_confirmed_send_clicks_only_after_confirmation(self):
        token = "confirm-before-send"
        self.browser._pending[token] = {
            "kind": "send", "app": "whatsapp", "created": __import__("time").time(), "target": "Mom",
        }
        click = Mock()
        button = SimpleNamespace(click=click)
        fake_page = SimpleNamespace(
            get_by_role=Mock(return_value=object()),
            locator=Mock(return_value=object()),
            wait_for_timeout=Mock(),
        )
        self.browser._app_page = Mock(return_value=fake_page)
        self.browser._first_visible = Mock(return_value=button)

        result = self.browser.perform("confirm", {"confirmation_token": token, "confirm": True})
        self.assertTrue(result["ok"])
        self.assertTrue(result["send_clicked"])
        click.assert_called_once_with(timeout=5_000)
        self.assertNotIn(token, self.browser._pending)

    def test_chat_prepare_selects_the_named_recipient_before_drafting(self):
        page = SimpleNamespace()
        self.browser._app_page = Mock(return_value=page)
        self.browser._body_text = Mock(return_value="signed-in chat page")
        self.browser._requires_sign_in = Mock(return_value=False)
        self.browser._active_chat_target = Mock(return_value="Another chat")
        self.browser._select_chat_target = Mock()
        self.browser._chat_compose = Mock(return_value=("Mom", "chat"))

        result = self.browser._prepare_send("whatsapp", {
            "mode": "reply", "recipient": "Mom", "body": "I will call at six",
        })

        self.browser._select_chat_target.assert_called_once_with("whatsapp", page, "Mom")
        self.browser._chat_compose.assert_called_once_with("whatsapp", page, "I will call at six", "Mom")
        self.assertTrue(result["requires_confirmation"])

    def test_calendar_save_requires_confirmation(self):
        token = "confirm-calendar-save"
        self.browser._pending[token] = {
            "kind": "calendar_save", "app": "google_calendar", "created": __import__("time").time(),
        }
        click = Mock()
        button = SimpleNamespace(click=click)
        fake_page = SimpleNamespace(
            get_by_role=Mock(return_value=object()),
            locator=Mock(return_value=object()),
            wait_for_timeout=Mock(),
        )
        self.browser._app_page = Mock(return_value=fake_page)
        self.browser._first_visible = Mock(return_value=button)

        cancelled = self.browser.perform("confirm", {"confirmation_token": token, "confirm": False})
        self.assertFalse(cancelled["confirmed"])
        self.assertEqual(click.call_count, 0)
        self.browser._pending[token] = {
            "kind": "calendar_save", "app": "google_calendar", "created": __import__("time").time(),
        }
        saved = self.browser.perform("confirm", {"confirmation_token": token, "confirm": True})
        self.assertTrue(saved["saved"])
        click.assert_called_once_with(timeout=5_000)

    def test_answering_call_requires_confirmation(self):
        token = "confirm-call"
        self.browser._pending[token] = {
            "kind": "answer_call", "app": "telegram", "created": __import__("time").time(),
        }
        click = Mock()
        button = SimpleNamespace(click=click)
        fake_page = SimpleNamespace(
            get_by_role=Mock(return_value=object()),
            locator=Mock(return_value=object()),
        )
        self.browser._app_page = Mock(return_value=fake_page)
        self.browser._body_text = Mock(return_value="Incoming voice call from a contact")
        self.browser._first_visible = Mock(return_value=button)

        cancelled = self.browser.perform("confirm", {"confirmation_token": token, "confirm": False})
        self.assertFalse(cancelled["confirmed"])
        self.assertEqual(click.call_count, 0)
        self.browser._pending[token] = {
            "kind": "answer_call", "app": "telegram", "created": __import__("time").time(),
        }
        answered = self.browser.perform("confirm", {"confirmation_token": token, "confirm": True})
        self.assertTrue(answered["answered_click"])
        click.assert_called_once_with(timeout=5_000)


if __name__ == "__main__":
    unittest.main()
