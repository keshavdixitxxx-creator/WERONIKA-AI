"""Run a multi-step browser task, pausing for approval before account actions."""

from __future__ import annotations

import threading
import time
from typing import Callable, Protocol

from .tasks import (
    ACTIONS,
    AutomationTask,
    Step,
    StepOutcome,
    TaskError,
    new_task,
    plan_from_payload,
    resolve_target,
)
from .web_adapter import SubmitOutcome

TASK_TTL_SECONDS = 15 * 60
MAX_LIVE_TASKS = 12


class TaskBrowser(Protocol):
    def search(self, query: str) -> str: ...

    def open_url(self, value: str) -> str: ...

    def click_result(self, index: int = 0) -> str: ...

    def read_page(self): ...

    def play(self, query: str, *, context: str = "") -> tuple[str, str]: ...

    def prepare_account_action(self, action: str, text: str, context: str) -> str: ...

    def submit_account_action(self, action: str, text: str) -> SubmitOutcome: ...

    def open_in_system_browser(self, url: str, preferred: str = "") -> str: ...


APPROVALS = {"confirm", "confirm action", "post it", "do it", "go ahead", "approve"}
CANCELS = {"cancel task", "stop task", "cancel", "stop"}


class TaskService:
    """One live task at a time; every risky step waits for the user's word."""

    def __init__(
        self,
        adapter_for: Callable[[], TaskBrowser],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._adapter_for = adapter_for
        self._clock = clock
        self._tasks: dict[str, AutomationTask] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ plan

    def start(self, payload: dict[str, object], *, progress: Callable[[str], None] | None = None):
        message = str(payload.get("message") or "")
        steps, context = plan_from_payload(payload)
        now = self._clock()
        task = new_task(message, steps, context, now)
        with self._lock:
            self._expire(now)
            self._tasks[task.id] = task
            while len(self._tasks) > MAX_LIVE_TASKS:
                self._tasks.pop(next(iter(self._tasks)))
        self._notify(progress, self._plan_summary(task))
        return self.run(task.id, progress=progress)

    # ------------------------------------------------------------------- run

    def run(self, task_id: str, *, progress: Callable[[str], None] | None = None):
        task = self._task(task_id)
        with self._lock:
            if task.pending_index is not None:
                return task
            task.stage = "running"
        while task.cursor < len(task.steps):
            index = task.cursor
            step = task.steps[index]
            target = resolve_target(step, task.context)
            self._notify(progress, f"Step {index + 1} of {len(task.steps)} · {ACTIONS[step.action].label}")
            try:
                if step.needs_approval:
                    detail = self._prepare(task, step, target)
                    with self._lock:
                        task.stage = "awaiting_approval"
                        task.pending_index = index
                        task.result = (
                            f"Step {index + 1} is ready: {ACTIONS[step.action].label}. "
                            f"{detail} Reply ‘confirm’ to submit it, or ‘cancel task’ to stop."
                        )
                    self._notify(progress, task.result)
                    return task
                outcome, task.page = self._execute(task, step, target)
            except Exception as exc:  # noqa: BLE001 - surfaced to the orb verbatim
                detail = str(exc) or "Weronika stopped safely."
                with self._lock:
                    task.outcomes.append(StepOutcome(index, step.action, "failed", detail))
                    task.stage = "failed"
                    task.result = f"Step {index + 1} stopped: {detail}"
                    task.cursor = index + 1
                self._notify(progress, task.result)
                return task
            with self._lock:
                task.outcomes.append(outcome)
                task.cursor = index + 1
            self._notify(progress, f"Step {index + 1} done · {outcome.detail}")
            self._absorbs_side_effect(task, step)

        with self._lock:
            task.stage = "done"
            task.result = self._summary(task)
        self._notify(progress, task.result)
        return task

    # ------------------------------------------------------------- approvals

    def approve(self, task_id: str, phrase: str = "confirm", *, progress=None):
        cleaned = " ".join(str(phrase or "").casefold().split()).strip(".! ")
        if cleaned not in APPROVALS:
            raise TaskError("To submit that action, reply exactly ‘confirm’. Otherwise nothing is submitted.")
        task = self._task(task_id)
        with self._lock:
            if task.pending_index is None:
                raise TaskError("This task has no action waiting for approval.")
            index = task.pending_index
            step = task.steps[index]
            target = resolve_target(step, task.context)
            task.stage = "running"
            task.pending_index = None
        try:
            outcome = self._adapter_for().submit_account_action(step.action, target)
        except Exception as exc:  # noqa: BLE001
            detail = str(exc) or "The action could not be submitted."
            with self._lock:
                task.outcomes.append(StepOutcome(index, step.action, "failed", detail))
                task.stage = "failed"
                task.result = detail
            raise TaskError(detail) from exc
        with self._lock:
            task.outcomes.append(
                StepOutcome(index, step.action, "done", outcome.detail, url=getattr(task.page, "url", "") if task.page else "")
            )
            task.cursor = max(task.cursor, index + 1)
        self._notify(progress, outcome.detail)
        return self.run(task_id, progress=progress)

    def cancel(self, task_id: str) -> AutomationTask:
        task = self._task(task_id)
        with self._lock:
            task.stage = "cancelled"
            task.pending_index = None
            task.result = "Cancelled. Nothing further was typed or submitted."
        return task

    # ------------------------------------------------------------------ query

    def get(self, task_id: str) -> AutomationTask:
        return self._task(task_id)

    def open_in_own_browser(self, url: str, preferred: str = "") -> str:
        """Open a public address in the user's Edge/Chrome/Firefox, outside the worker."""
        opener = getattr(self._adapter_for(), "open_in_system_browser", None)
        if not callable(opener):
            raise TaskError("This worker cannot open your own browser.")
        try:
            return opener(url, preferred)
        except Exception as exc:  # noqa: BLE001
            raise TaskError(str(exc) or "Weronika could not open that address.") from exc

    def live(self) -> AutomationTask | None:
        with self._lock:
            self._expire(self._clock())
            live = [task for task in self._tasks.values() if task.stage in {"running", "awaiting_approval"}]
            return live[-1] if live else None

    # ---------------------------------------------------------------- helpers

    def _prepare(self, task: AutomationTask, step: Step, target: str) -> str:
        if step.action in {"comment", "reply"} and not target.strip():
            raise TaskError("What exactly should the comment say?")
        adapter = self._adapter_for()
        return adapter.prepare_account_action(step.action, target, task.context)

    def _execute(self, task: AutomationTask, step: Step, target: str):
        adapter = self._adapter_for()
        page = task.page
        if step.action == "search":
            url = adapter.search(target)
            return StepOutcome(task.cursor, step.action, "done", f"Searched: {target}", url=url), None
        if step.action == "open_url":
            url = adapter.open_url(target)
            return StepOutcome(task.cursor, step.action, "done", f"Opened {url}", url=url), None
        if step.action == "open_result":
            detail = adapter.click_result(0)
            return StepOutcome(task.cursor, step.action, "done", f"Opened {detail}"), None
        if step.action == "read_page":
            reading = adapter.read_page()
            detail = f"Read “{reading.title or reading.url}” ({len(reading.text)} characters)."
            return StepOutcome(task.cursor, step.action, "done", detail, url=reading.url, page=reading), reading
        if step.action == "play_video":
            detail, url = adapter.play(target, context=task.context)
            return StepOutcome(task.cursor, step.action, "done", detail, url=url), page
        raise TaskError(f"“{step.action}” cannot run without your approval.")

    @staticmethod
    def _absorbs_side_effect(task: AutomationTask, step: Step) -> None:
        """A step that consumed “it” should not let a later step reuse the same text."""
        if step.action in {"comment", "reply"}:
            task.context = ""

    def _plan_summary(self, task: AutomationTask) -> str:
        lines = [f"I broke this into {len(task.steps)} step(s):"]
        for index, step in enumerate(task.steps, start=1):
            approval = " · needs your approval" if step.needs_approval else ""
            lines.append(f"{index}. {ACTIONS[step.action].label}{f': {resolve_target(step, task.context)}' if resolve_target(step, task.context) else ''}{approval}")
        return "\n".join(lines)

    def _summary(self, task: AutomationTask) -> str:
        done = [outcome for outcome in task.outcomes if outcome.status == "done"]
        if task.steps and len(done) == len(task.steps):
            tail = ""
            if task.page is not None:
                tail = f" Open page: “{task.page.title or task.page.url}”."
            return f"All {len(task.steps)} step(s) finished.{tail}"
        return f"{len(done)} of {len(task.steps)} step(s) finished."

    def _task(self, task_id: str) -> AutomationTask:
        with self._lock:
            self._expire(self._clock())
            task = self._tasks.get(str(task_id or ""))
        if task is None:
            raise TaskError("That automation expired or does not exist. Ask again; nothing is left running.")
        return task

    def _expire(self, now: float) -> None:
        for task_id, task in list(self._tasks.items()):
            if now - task.created_at <= TASK_TTL_SECONDS:
                continue
            if task.stage in {"awaiting_approval", "running"}:
                task.stage = "expired"
                task.pending_index = None
                task.result = "Expired without submitting the pending action."
            else:
                del self._tasks[task_id]

    def _notify(self, progress: Callable[[str], None] | None, message: str) -> None:
        if progress is None or not message:
            return
        try:
            progress(message)
        except Exception:
            pass

