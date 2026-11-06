import unittest

from weronika_agent.models import Platform, WorkflowStage
from weronika_agent.reply_watch import (
    ChatReading,
    ChatSnapshot,
    IncomingMessage,
    ReplyWatchError,
    ReplyWatchService,
    find_chat,
    looks_like_question,
)
from weronika_agent.watch_intents import parse_watch_request


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeActivity:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.chats = [
            ChatSnapshot(Platform.WHATSAPP, "Boss"),
            ChatSnapshot(Platform.WHATSAPP, "Priya", is_group=True),
        ]
        self.readings: dict[str, ChatReading] = {}
        self.read_count = 0

    def list_chats(self, platform):
        return list(self.chats)

    def read_latest(self, platform, chat_name):
        self.read_count += 1
        reading = self.readings.get(chat_name, ChatReading(chat_name=chat_name))
        is_group = any(chat.chat_name == chat_name and chat.is_group for chat in self.chats)
        return ChatReading(
            chat_name=chat_name,
            is_group=is_group,
            messages=reading.messages,
            last_is_incoming=reading.last_is_incoming,
        )

    def deliver(self, chat_name, text, sender="", *, incoming=True):
        existing = list(self.readings.get(chat_name, ChatReading(chat_name)).messages)
        message = IncomingMessage(
            platform=Platform.WHATSAPP,
            chat_name=chat_name,
            message_id=f"m{len(existing) + 1}",
            text=text,
            sender=sender,
            seen_at=self.clock(),
        )
        self.readings[chat_name] = ChatReading(
            chat_name=chat_name,
            messages=tuple(existing + [message]),
            last_is_incoming=incoming,
        )

    def reply_self(self, chat_name):
        reading = self.readings[chat_name]
        self.readings[chat_name] = ChatReading(
            chat_name=chat_name, messages=reading.messages, last_is_incoming=False
        )


class FakeDraft:
    def __init__(self, draft_id: str) -> None:
        self.id = draft_id
        self.stage = WorkflowStage.AWAITING_CONFIRMATION
        self.selected_recipient = "Boss"
        self.message = ""
        self.result = "Message sent and verified."


class FakeResult:
    def __init__(self, draft, prompt):
        self.draft = draft
        self.prompt = prompt


class FakeMessaging:
    def __init__(self) -> None:
        self.busy = False
        self.prepared = []
        self.confirmed = []
        self.selected = None
        self.ambiguous_chat = False

    def has_unsettled_draft(self) -> bool:
        return self.busy

    def prepare(self, platform, recipient, message, progress=None):
        self.prepared.append((platform.value, recipient, message))
        draft = FakeDraft("draft1")
        draft.message = message
        if recipient == "Boss" and self.ambiguous_chat:
            from weronika_agent.models import RecipientCandidate

            draft.stage = WorkflowStage.AWAITING_RECIPIENT_CHOICE
            draft.candidates = [
                RecipientCandidate("1", "Boss", 0.9, exact=True, source_id="0:0"),
                RecipientCandidate("2", "Boss Office", 0.84, source_id="0:1"),
            ]
            return FakeResult(draft, "Several chats match “Boss”. Choose one by number.")
        return FakeResult(
            draft,
            f"I opened {recipient} and prepared this reply:\n\n{message}\n\nIt has NOT been sent.",
        )

    def select_recipient(self, draft_id, candidate_id, progress=None):
        self.selected = (draft_id, candidate_id)
        draft = FakeDraft(draft_id)
        draft.selected_recipient = "Boss"
        draft.message = "I won’t be able to come today"
        return FakeResult(draft, "prepared after choosing the chat")

    def confirm_send(self, draft_id, phrase, progress=None):
        if phrase.strip().casefold() not in {"confirm send", "send it"}:
            raise ReplyWatchError("To send, reply exactly ‘confirm send’ or ‘send it’.")
        self.confirmed.append((draft_id, phrase))
        draft = FakeDraft(draft_id)
        draft.stage = WorkflowStage.SENT
        return FakeResult(draft, "sent")


class ReplyWatchServiceTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.activity = FakeActivity(self.clock)
        self.messaging = FakeMessaging()
        self.service = ReplyWatchService(
            lambda platform: self.activity, self.messaging, clock=self.clock
        )

    def add_boss_watch(self, **overrides):
        payload = {"platform": "whatsapp", "chat": "Boss", "mode": "ask", "rule": "unanswered"}
        payload.update(overrides)
        return self.service.add_watch(payload)

    def test_existing_history_is_not_reported_as_a_new_request(self):
        self.activity.deliver("Boss", "Old question from before the watch?")
        watching = self.add_boss_watch()
        self.assertIn("Watching", watching.prompt)
        self.assertEqual(self.service.scan()["detected"], [])

    def test_new_unanswered_message_is_raised_once(self):
        self.add_boss_watch(unanswered_after_seconds=0)
        self.activity.deliver("Boss", "Are you coming today?", sender="Boss")
        first = self.service.scan()
        self.assertEqual(len(first["detected"]), 1)
        item = first["detected"][0]
        self.assertEqual(item["state"], "awaiting_user")
        self.assertIn("Are you coming today?", item["message"]["text"])
        self.assertEqual(self.service.scan()["detected"], [])

    def test_a_chat_where_the_user_replied_last_is_left_alone(self):
        self.add_boss_watch(unanswered_after_seconds=0)
        self.activity.deliver("Boss", "Are you coming?", sender="Boss")
        self.activity.reply_self("Boss")
        self.assertEqual(self.service.scan()["detected"], [])

    def test_waiting_time_must_pass_before_reporting(self):
        self.add_boss_watch(unanswered_after_seconds=600)
        self.activity.deliver("Boss", "Kaam ho gaya?", sender="Boss")
        self.assertEqual(self.service.scan()["detected"], [])
        self.clock.advance(601)
        self.assertEqual(len(self.service.scan()["detected"]), 1)

    def test_urgent_rule_ignores_small_talk(self):
        self.add_boss_watch(rule="urgent", unanswered_after_seconds=0)
        self.activity.deliver("Boss", "ok", sender="Boss")
        self.activity.deliver("Boss", "haha", sender="Boss")
        self.assertEqual(self.service.scan()["detected"], [])
        self.activity.deliver("Boss", "Please call me now, urgent!", sender="Boss")
        self.assertEqual(len(self.service.scan()["detected"]), 1)

    def test_group_watch_needs_a_question_that_names_the_user(self):
        self.service.add_watch(
            {
                "platform": "whatsapp",
                "chat": "Priya",
                "mode": "ask",
                "rule": "unanswered",
                "unanswered_after_seconds": 0,
            }
        )
        self.activity.deliver("Priya", "bring snacks", sender="Rahul")
        self.assertEqual(self.service.scan()["detected"], [])
        self.activity.deliver("Priya", "@kethan are you coming today?", sender="Rahul")
        self.assertEqual(len(self.service.scan()["detected"]), 1)

    def test_propose_mode_suggests_wording_before_anything_is_typed(self):
        service = ReplyWatchService(
            lambda platform: self.activity,
            self.messaging,
            clock=self.clock,
            suggester=lambda chat, text: "I won’t be able to come today.",
        )
        service.add_watch(
            {
                "platform": "whatsapp",
                "chat": "Boss",
                "mode": "propose",
                "rule": "unanswered",
                "unanswered_after_seconds": 0,
            }
        )
        self.activity.deliver("Boss", "Are you coming to office today?", sender="Boss")
        item = service.scan()["detected"][0]
        self.assertEqual(item["suggestion"], "I won’t be able to come today.")
        self.assertEqual(self.messaging.prepared, [])

        staged = service.propose(item["item_id"], "I won’t be able to come today, sorry.")
        self.assertIn("NOT been sent", staged.prompt)
        self.assertEqual(self.messaging.prepared[0][2], "I won’t be able to come today, sorry.")
        self.assertEqual(self.messaging.confirmed, [])

        sent = service.confirm(item["item_id"], "send it")
        self.assertEqual(sent.item.state.value, "sent")
        self.assertEqual(self.messaging.confirmed[0][1], "send it")

    def test_ambiguous_chat_names_need_a_numbered_choice(self):
        self.messaging.ambiguous_chat = True
        service = ReplyWatchService(
            lambda platform: self.activity,
            self.messaging,
            clock=self.clock,
            suggester=lambda chat, text: "Sorry, I can’t come today.",
        )
        service.add_watch(
            {
                "platform": "whatsapp",
                "chat": "Boss",
                "mode": "propose",
                "rule": "unanswered",
                "unanswered_after_seconds": 0,
            }
        )
        self.activity.deliver("Boss", "Are you coming?", sender="Boss")
        item_id = service.scan()["detected"][0]["item_id"]
        staged = service.propose(item_id, "I won’t be able to come today")
        self.assertEqual(staged.item.state.value, "awaiting_user")
        self.assertIn("Several chats match", staged.prompt)
        self.assertEqual(self.messaging.confirmed, [])

        chosen = service.choose(item_id, "1")
        self.assertEqual(chosen.item.state.value, "awaiting_review")
        self.assertEqual(self.messaging.selected[1], "1")

    def test_a_refused_confirmation_does_not_mark_the_item_sent(self):
        self.add_boss_watch(unanswered_after_seconds=0)
        self.activity.deliver("Boss", "Hello?", sender="Boss")
        item_id = self.service.scan()["detected"][0]["item_id"]
        self.service.propose(item_id, "Hello")
        with self.assertRaises(ReplyWatchError):
            self.service.confirm(item_id, "yes")
        self.assertEqual(self.messaging.confirmed, [])

    def test_leave_it_closes_the_item_and_keeps_watching(self):
        self.add_boss_watch(unanswered_after_seconds=0)
        self.activity.deliver("Boss", "Hello?", sender="Boss")
        item_id = self.service.scan()["detected"][0]["item_id"]
        result = self.service.leave_it if hasattr(self.service, "leave_it") else self.service.decline
        outcome = result(item_id)
        self.assertEqual(outcome.item.state.value, "declined")
        self.assertEqual(self.messaging.prepared, [])
        state = self.service.list_state()
        self.assertEqual(len(state["watches"]), 1)
        self.assertEqual(state["watches"][0]["state"], "new")

    def test_scan_pauses_while_a_draft_is_open(self):
        self.add_boss_watch(unanswered_after_seconds=0)
        self.messaging.busy = True
        self.clock.advance(30)
        self.activity.deliver("Boss", "Hello?", sender="Boss")
        self.assertEqual(self.service.scan()["detected"], [])
        self.messaging.busy = False
        self.assertEqual(len(self.service.scan()["detected"]), 1)

    def test_unknown_chat_is_refused_with_the_visible_list(self):
        with self.assertRaises(ReplyWatchError) as raised:
            self.add_boss_watch(chat="Nobody")
        self.assertIn("Visible chats: Boss", str(raised.exception))

    def test_reminder_fires_once(self):
        self.add_boss_watch(unanswered_after_seconds=0, reminder_seconds=60)
        self.activity.deliver("Boss", "Hello?", sender="Boss")
        self.assertEqual(self.service.scan()["reminders"], [])
        self.clock.advance(61)
        first = self.service.scan()["reminders"]
        self.assertEqual(len(first), 1)
        self.assertEqual(self.service.scan()["reminders"], [])


class WatchIntentTests(unittest.TestCase):
    def test_parses_a_named_chat_and_ask_mode(self):
        intent = parse_watch_request("Watch my WhatsApp chat with Boss")
        self.assertEqual(intent.action, "add_watch")
        self.assertEqual(intent.platform, Platform.WHATSAPP)
        self.assertEqual(intent.chat, "Boss")
        self.assertEqual(intent.mode, "ask")

    def test_parses_propose_mode_and_delay(self):
        intent = parse_watch_request(
            "Keep an eye on Telegram chat with Rahul and reply for me if I don’t reply in 10 minutes"
        )
        self.assertEqual(intent.mode, "propose")
        self.assertEqual(intent.chat, "Rahul")
        self.assertEqual(intent.delay_seconds, 600)

    def test_group_name_is_extracted(self):
        intent = parse_watch_request("watch the Family group on WhatsApp and you can reply for me")
        self.assertEqual(intent.chat, "Family")
        self.assertEqual(intent.mode, "propose")

    def test_all_chats_phrase(self):
        intent = parse_watch_request("Watch all my Telegram chats and reply if I can’t")
        self.assertTrue(intent.all_chats)

    def test_plain_chat_is_not_hijacked(self):
        for text in ("what is the weather today", "send a WhatsApp message to Boss saying hi"):
            self.assertEqual(parse_watch_request(text).action, "unhandled", text)

    def test_stop_and_status_phrases(self):
        self.assertEqual(parse_watch_request("stop watching").action, "stop_watch")
        self.assertEqual(parse_watch_request("who is waiting for a reply?").action, "status")
        self.assertEqual(parse_watch_request("leave it").action, "leave_it")


class ChatMatchingTests(unittest.TestCase):
    def test_single_best_chat_wins(self):
        chats = [ChatSnapshot(Platform.WHATSAPP, "Boss"), ChatSnapshot(Platform.WHATSAPP, "Rahul")]
        self.assertEqual(find_chat(chats, "boss").chat_name, "Boss")

    def test_two_equally_good_chats_are_not_guessed(self):
        chats = [ChatSnapshot(Platform.WHATSAPP, "Boss"), ChatSnapshot(Platform.WHATSAPP, "Boss")]
        self.assertIsNone(find_chat(chats, "Boss"))

    def test_question_detection_handles_hindi_and_romanscript(self):
        self.assertTrue(looks_like_question("kya aaj aaoge"))
        self.assertTrue(looks_like_question("Are you coming?"))
        self.assertFalse(looks_like_question("ok done"))


if __name__ == "__main__":
    unittest.main()
