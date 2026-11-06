import unittest

from weronika_agent.task_service import TaskService
from weronika_agent.tasks import PageReading, Step, TaskError, plan_from_payload, resolve_target
from weronika_agent.web_adapter import SubmitOutcome, find_browser, is_public_url
from weronika_agent.web_intents import plan_local, url_for_system_open, wants_system_browser


class FakeClock:
    def __init__(self, start: float = 2_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeBrowser:
    def __init__(self, fail_on: str = "") -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail_on = fail_on
        self.submitted: list[tuple[str, str]] = []
        self.prepared: list[tuple[str, str]] = []
        self.page = PageReading(
            url="https://www.youtube.com/watch?v=abc",
            title="Kesariya - Brahmastra",
            text="Kesariya song lyrics official video",
        )

    def _maybe_fail(self, action: str) -> None:
        if action == self.fail_on:
            raise TaskError(f"{action} blocked in the test")

    def search(self, query):
        self._maybe_fail("search")
        self.calls.append(("search", query))
        return f"https://duckduckgo.com/?q={query}"

    def open_url(self, value):
        self.calls.append(("open_url", value))
        return value

    def click_result(self, index=0):
        self.calls.append(("click_result", str(index)))
        return "Example result — https://example.com/"

    def read_page(self):
        self.calls.append(("read_page", ""))
        return self.page

    def play(self, query, *, context=""):
        self._maybe_fail("play_video")
        self.calls.append(("play_video", query))
        return f"Playing on YouTube: “{query}”", self.page.url

    def prepare_account_action(self, action, text, context):
        self.prepared.append((action, text))
        return f"{action} typed on “{self.page.title}” · not submitted"

    def submit_account_action(self, action, text):
        self.submitted.append((action, text))
        return SubmitOutcome(True, f"{action} submitted")

    def open_in_system_browser(self, url, preferred=""):
        self.calls.append(("system", f"{preferred}|{url}"))
        return f"Opened in Microsoft Edge: {url}"


class TaskPlanningTests(unittest.TestCase):
    def test_brain_plan_is_validated_and_follow_up_resolves_context(self):
        steps, context = plan_from_payload(
            {
                "steps": [
                    {"action": "play_video", "target": "Kesariya song"},
                    {"action": "comment", "target": "Beautiful track"},
                ]
            }
        )
        self.assertEqual([step.action for step in steps], ["play_video", "comment"])
        self.assertEqual(context, "Kesariya song")
        self.assertEqual(resolve_target(steps[1], context), "Beautiful track")

    def test_pronoun_target_falls_back_to_the_task_context(self):
        step = Step("play_video", "this video")
        self.assertEqual(resolve_target(step, "Kesariya song"), "Kesariya song")

    def test_unknown_actions_and_oversized_plans_are_refused(self):
        with self.assertRaises(TaskError):
            plan_from_payload({"steps": [{"action": "run_shell", "target": "rm -rf /"}]})
        with self.assertRaises(TaskError):
            plan_from_payload({"steps": [{"action": "search", "target": "x"}] * 9})
        with self.assertRaises(TaskError):
            Step("comment", "a" * 2500)


class TaskServiceTests(unittest.TestCase):
    def build(self, browser=None):
        clock = FakeClock()
        browser = browser or FakeBrowser()
        service = TaskService(lambda: browser, clock=clock)
        return service, browser, clock

    def test_search_and_play_run_without_any_approval(self):
        service, browser, _ = self.build()
        task = service.start(
            {
                "message": "open youtube and play kesariya song",
                "steps": [
                    {"action": "search", "target": "youtube"},
                    {"action": "play_video", "target": "kesariya song"},
                ],
            }
        )
        self.assertEqual(task.stage, "done")
        self.assertEqual([call[0] for call in browser.calls], ["search", "play_video"])
        self.assertTrue(all(outcome.status == "done" for outcome in task.outcomes))

    def test_comment_waits_for_approval_before_submitting(self):
        service, browser, _ = self.build()
        task = service.start(
            {
                "message": "make a comment of this: great explanation",
                "steps": [{"action": "comment", "target": "great explanation"}],
            }
        )
        self.assertEqual(task.stage, "awaiting_approval")
        self.assertEqual(task.pending_index, 0)
        self.assertEqual(browser.prepared, [("comment", "great explanation")])
        self.assertEqual(browser.submitted, [])
        self.assertIn("confirm", task.result)

        done = service.approve(task.id, "confirm")
        self.assertEqual(done.stage, "done")
        self.assertEqual(browser.submitted, [("comment", "great explanation")])

    def test_a_refused_phrase_never_submits(self):
        service, browser, _ = self.build()
        task = service.start(
            {"message": "comment", "steps": [{"action": "comment", "target": "hi"}]}
        )
        with self.assertRaises(TaskError):
            service.approve(task.id, "yes")
        self.assertEqual(browser.submitted, [])
        self.assertEqual(service.get(task.id).stage, "awaiting_approval")

    def test_cancel_drops_the_pending_action(self):
        service, browser, _ = self.build()
        task = service.start(
            {"message": "comment", "steps": [{"action": "comment", "target": "hi"}]}
        )
        cancelled = service.cancel(task.id)
        self.assertEqual(cancelled.stage, "cancelled")
        self.assertEqual(browser.submitted, [])

    def test_failed_step_stops_the_plan_and_reports_it(self):
        browser = FakeBrowser(fail_on="play_video")
        service, _, _ = self.build(browser)
        task = service.start(
            {
                "message": "play then comment",
                "steps": [
                    {"action": "play_video", "target": "kesariya"},
                    {"action": "comment", "target": "nice"},
                ],
            }
        )
        self.assertEqual(task.stage, "failed")
        self.assertIn("play_video blocked", task.result)
        self.assertEqual(browser.prepared, [])
        self.assertEqual(browser.submitted, [])

    def test_expired_task_cannot_be_approved(self):
        service, browser, clock = self.build()
        task = service.start(
            {"message": "comment", "steps": [{"action": "comment", "target": "hi"}]}
        )
        clock.advance(16 * 60)
        with self.assertRaises(TaskError):
            service.approve(task.id, "confirm")
        self.assertEqual(browser.submitted, [])

    def test_page_reading_is_carried_into_the_task(self):
        service, _, _ = self.build()
        task = service.start(
            {"message": "read this", "steps": [{"action": "read_page", "target": ""}]}
        )
        self.assertEqual(task.stage, "done")
        self.assertIsNotNone(task.page)
        self.assertEqual(task.outcomes[0].page.title, "Kesariya - Brahmastra")


class WebIntentTests(unittest.TestCase):
    def test_local_plans_cover_the_plain_phrasings(self):
        cases = {
            "open youtube and play kesariya song": ("play_video", "kesariya"),
            "search for best laptop under 50000": ("search", "best laptop under 50000"),
            "open youtube": ("open_url", "https://www.youtube.com/"),
            "comment: nice video": ("comment", "nice video"),
            "like this video": ("like", ""),
            "what is the capital of australia": ("search", "what is the capital of australia"),
        }
        for text, expected in cases.items():
            plan = plan_local(text)
            self.assertIsNotNone(plan, text)
            self.assertEqual((plan.steps[0].action, plan.steps[0].target), expected, text)

    def test_local_planner_leaves_other_requests_alone(self):
        for text in ("send a WhatsApp message to Boss saying hi", "watch my telegram chat with Rahul"):
            self.assertIsNone(plan_local(text), text)

    def test_system_browser_preference_is_detected(self):
        self.assertEqual(wants_system_browser("open github in chrome"), "chrome")
        self.assertEqual(wants_system_browser("open edge and go to github.com"), "edge")
        self.assertEqual(wants_system_browser("open github"), "")
        self.assertTrue(url_for_system_open("open github in chrome").startswith("https://github.com"))


class WebAdapterTests(unittest.TestCase):
    def test_only_public_http_addresses_are_opened(self):
        self.assertTrue(is_public_url("https://www.youtube.com/results?search_query=x"))
        for blocked in (
            "http://127.0.0.1:8080/",
            "http://localhost/admin",
            "http://169.254.169.254/latest/meta-data/",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ):
            self.assertFalse(is_public_url(blocked), blocked)

    def test_browser_lookup_can_be_limited_to_a_preference(self):
        self.assertIn(find_browser("edge"), {None, ("Microsoft Edge", "msedge")})


if __name__ == "__main__":
    unittest.main()
