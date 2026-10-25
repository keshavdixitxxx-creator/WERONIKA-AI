import threading
import unittest

from weronika_agent.models import Platform, VisibleContact, WorkflowStage
from weronika_agent.workflow import MessagingError, MessagingService


class FakeAdapter:
    def __init__(self, results, verified=True):
        self.results = results
        self.verified = verified
        self.opened = []
        self.sent = []
        self.cleared = []

    def find_recipients(self, query):
        return self.results

    def open_chat_and_draft(self, candidate, message):
        self.opened.append((candidate, message))

    def send_and_verify(self, message):
        self.sent.append(message)
        return self.verified

    def clear_draft_if_unchanged(self, message):
        self.cleared.append(message)
        return True


class WorkflowTests(unittest.TestCase):
    def test_exact_single_result_is_prepared_but_never_sent_automatically(self):
        adapter = FakeAdapter([VisibleContact("0:0", "Boss")])
        service = MessagingService(lambda _: adapter)
        result = service.prepare(Platform.WHATSAPP, "Boss", "I will be on leave")
        self.assertEqual(result.draft.stage, WorkflowStage.AWAITING_CONFIRMATION)
        self.assertEqual(adapter.opened[0][1], "I will be on leave")
        self.assertEqual(adapter.sent, [])
        self.assertIn("NOT been sent", result.prompt)

    def test_similar_or_duplicate_results_require_choice(self):
        adapter = FakeAdapter([
            VisibleContact("0:0", "Boss"),
            VisibleContact("0:1", "Boss Work"),
        ])
        service = MessagingService(lambda _: adapter)
        result = service.prepare(Platform.WHATSAPP, "Boss", "I will be on leave")
        self.assertEqual(result.draft.stage, WorkflowStage.AWAITING_RECIPIENT_CHOICE)
        self.assertEqual(adapter.opened, [])
        self.assertEqual(adapter.sent, [])
        staged = service.select_recipient(result.draft.id, result.draft.candidates[0].id)
        self.assertEqual(staged.draft.stage, WorkflowStage.AWAITING_CONFIRMATION)
        self.assertEqual(len(adapter.opened), 1)
        self.assertEqual(adapter.sent, [])

    def test_confirmation_is_required_and_duplicate_send_is_rejected(self):
        adapter = FakeAdapter([VisibleContact("0:0", "Boss")])
        service = MessagingService(lambda _: adapter)
        draft = service.prepare(Platform.TELEGRAM, "Boss", "On my way").draft
        with self.assertRaises(MessagingError):
            service.confirm_send(draft.id, "yes")
        self.assertEqual(adapter.sent, [])
        sent = service.confirm_send(draft.id, "confirm send")
        self.assertEqual(sent.draft.stage, WorkflowStage.SENT)
        self.assertEqual(adapter.sent, ["On my way"])
        with self.assertRaises(MessagingError):
            service.confirm_send(draft.id, "send it")
        self.assertEqual(adapter.sent, ["On my way"])

    def test_unverified_send_is_not_automatically_retried(self):
        adapter = FakeAdapter([VisibleContact("0:0", "Boss")], verified=False)
        service = MessagingService(lambda _: adapter)
        draft = service.prepare(Platform.X, "Boss", "Hello").draft
        result = service.confirm_send(draft.id, "send it")
        self.assertEqual(result.draft.stage, WorkflowStage.SENT_UNVERIFIED)
        self.assertIn("Check the chat", result.prompt)
        self.assertEqual(adapter.sent, ["Hello"])

    def test_cancel_clears_unchanged_draft(self):
        adapter = FakeAdapter([VisibleContact("0:0", "Boss")])
        service = MessagingService(lambda _: adapter)
        draft = service.prepare(Platform.WHATSAPP, "Boss", "Draft only").draft
        result = service.cancel(draft.id)
        self.assertEqual(result.draft.stage, WorkflowStage.CANCELLED)
        self.assertEqual(adapter.cleared, ["Draft only"])

    def test_no_match_stops_safely(self):
        adapter = FakeAdapter([])
        service = MessagingService(lambda _: adapter)
        result = service.prepare(Platform.WHATSAPP, "Boss", "Hello")
        self.assertEqual(result.draft.stage, WorkflowStage.FAILED)
        self.assertEqual(adapter.opened, [])
        self.assertEqual(adapter.sent, [])

    def test_concurrent_confirmations_cannot_double_send(self):
        entered_send = threading.Event()
        release_send = threading.Event()

        class SlowAdapter(FakeAdapter):
            def send_and_verify(self, message):
                self.sent.append(message)
                entered_send.set()
                release_send.wait(timeout=2)
                return True

        adapter = SlowAdapter([VisibleContact("0:0", "Boss")])
        service = MessagingService(lambda _: adapter)
        draft = service.prepare(Platform.WHATSAPP, "Boss", "Only once").draft
        first = threading.Thread(target=lambda: service.confirm_send(draft.id, "confirm send"))
        first.start()
        self.assertTrue(entered_send.wait(timeout=1))
        with self.assertRaises(MessagingError):
            service.confirm_send(draft.id, "send it")
        release_send.set()
        first.join(timeout=2)
        self.assertFalse(first.is_alive())
        self.assertEqual(adapter.sent, ["Only once"])


if __name__ == "__main__":
    unittest.main()
