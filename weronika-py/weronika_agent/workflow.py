"""Two-step messaging workflow with recipient disambiguation and explicit send approval."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

from .contacts import rank_candidates, unique_exact_match
from .models import MessageDraft, Platform, RecipientCandidate, VisibleContact, WorkflowStage


class MessagingError(RuntimeError):
    """An expected, user-actionable messaging error."""


class LoginRequired(MessagingError):
    pass


class UnsupportedAppUi(MessagingError):
    pass


class MessagingAdapter(Protocol):
    def find_recipients(self, query: str) -> list[VisibleContact]: ...

    def open_chat_and_draft(self, candidate: RecipientCandidate, message: str) -> None: ...

    def send_and_verify(self, message: str) -> bool: ...

    def clear_draft_if_unchanged(self, message: str) -> bool: ...


@dataclass(frozen=True)
class WorkflowResult:
    draft: MessageDraft
    prompt: str

    def to_dict(self) -> dict[str, object]:
        result = self.draft.to_dict()
        result["prompt"] = self.prompt
        return result


class MessagingService:
    """Manage in-memory drafts; outgoing messages are never sent during prepare()."""

    DRAFT_TTL_SECONDS = 600
    SEND_CONFIRMATIONS = {"confirm send", "send it", "send the message"}

    def __init__(self, adapter_for: Callable[[Platform], MessagingAdapter]) -> None:
        self._adapter_for = adapter_for
        self._drafts: dict[str, MessageDraft] = {}
        self._lock = threading.RLock()

    def prepare(self, platform: Platform, recipient: str, message: str) -> WorkflowResult:
        recipient = " ".join(recipient.split())
        message = message.strip()
        if not recipient or not message:
            raise MessagingError("Both a recipient and a message are required.")
        if len(recipient) > 120 or len(message) > 2000:
            raise MessagingError("Recipient or message exceeds the supported length.")

        adapter = self._adapter_for(platform)
        names = adapter.find_recipients(recipient)
        candidates = rank_candidates(recipient, names)
        now = time.time()
        draft = MessageDraft(
            id=uuid.uuid4().hex,
            platform=platform,
            requested_recipient=recipient,
            message=message,
            candidates=candidates,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._expire_old_drafts(now)
            self._drafts[draft.id] = draft

        # Even a unique exact spelling requires a choice when similar results are
        # also visible. This avoids treating a short name (for example, “Boss”)
        # as sufficient when “Boss Work” and “Boss Home” are both in the list.
        exact = unique_exact_match(candidates)
        if exact is None or len(candidates) != 1:
            if candidates:
                draft.stage = WorkflowStage.AWAITING_RECIPIENT_CHOICE
                draft.result = "Several or similar contacts were found. Choose one before Weronika opens the chat."
                return WorkflowResult(draft, self._choice_prompt(draft))
            draft.stage = WorkflowStage.FAILED
            draft.result = "No matching chat was found. Nothing was typed or sent."
            return WorkflowResult(draft, draft.result)

        self._stage_message(draft, exact)
        return WorkflowResult(draft, self._confirmation_prompt(draft))

    def select_recipient(self, draft_id: str, candidate_id: str) -> WorkflowResult:
        with self._lock:
            draft = self._get_draft(draft_id)
            if draft.stage != WorkflowStage.AWAITING_RECIPIENT_CHOICE:
                raise MessagingError("This draft is not waiting for a contact choice.")
            candidate = next((item for item in draft.candidates if item.id == str(candidate_id)), None)
            if candidate is None:
                raise MessagingError("That contact choice is not in the current results.")
            draft.stage = WorkflowStage.PREPARING
        self._stage_message(draft, candidate)
        return WorkflowResult(draft, self._confirmation_prompt(draft))

    def _stage_message(self, draft: MessageDraft, candidate: RecipientCandidate) -> None:
        try:
            adapter = self._adapter_for(draft.platform)
            adapter.open_chat_and_draft(candidate, draft.message)
        except Exception as exc:
            draft.stage = WorkflowStage.FAILED
            draft.result = str(exc) or "Weronika could not safely prepare this message."
            raise MessagingError(draft.result) from exc
        draft.selected_recipient = candidate.display_name
        draft.stage = WorkflowStage.AWAITING_CONFIRMATION
        draft.updated_at = time.time()
        draft.result = "Message is drafted but has not been sent."

    def confirm_send(self, draft_id: str, confirmation_phrase: str) -> WorkflowResult:
        phrase = " ".join(confirmation_phrase.casefold().split()).strip(".! ")
        if phrase not in self.SEND_CONFIRMATIONS:
            raise MessagingError("To send, reply exactly ‘confirm send’ or ‘send it’. Otherwise nothing will be sent.")
        with self._lock:
            draft = self._get_draft(draft_id)
            if draft.stage != WorkflowStage.AWAITING_CONFIRMATION:
                raise MessagingError("This draft is not ready to send or has already been handled.")
            # The transition is atomic so simultaneous confirmations cannot both click Send.
            draft.stage = WorkflowStage.SENDING
            draft.updated_at = time.time()

        # Mark the draft before clicking. If the app times out after accepting the
        # click, a repeated confirmation must not send the same text a second time.
        try:
            adapter = self._adapter_for(draft.platform)
            verified = adapter.send_and_verify(draft.message)
        except Exception as exc:
            draft.stage = WorkflowStage.SENT_UNVERIFIED
            draft.result = (
                "The send action may have completed, but Weronika could not verify it. "
                "Check the chat before trying again."
            )
            raise MessagingError(draft.result) from exc

        draft.stage = WorkflowStage.SENT if verified else WorkflowStage.SENT_UNVERIFIED
        draft.updated_at = time.time()
        draft.result = (
            "Message sent and verified."
            if verified
            else "The send action was attempted, but delivery could not be verified. Check the chat before retrying."
        )
        return WorkflowResult(draft, draft.result)

    def cancel(self, draft_id: str) -> WorkflowResult:
        with self._lock:
            draft = self._get_draft(draft_id)
            if draft.stage in {WorkflowStage.SENT, WorkflowStage.SENT_UNVERIFIED, WorkflowStage.SENDING}:
                raise MessagingError("This message is already being sent or has been sent; check the chat first.")
            if draft.stage == WorkflowStage.PREPARING:
                raise MessagingError("Weronika is still preparing this draft. Try cancelling again in a moment.")
            should_clear = draft.stage == WorkflowStage.AWAITING_CONFIRMATION and bool(draft.selected_recipient)
            draft.stage = WorkflowStage.CANCELLED
            draft.updated_at = time.time()
            draft.result = "Cancelled. The unsent draft was cleared if it had not changed."
        if should_clear:
            try:
                self._adapter_for(draft.platform).clear_draft_if_unchanged(draft.message)
            except Exception:
                pass
        return WorkflowResult(draft, draft.result)

    def _get_draft(self, draft_id: str) -> MessageDraft:
        with self._lock:
            self._expire_old_drafts(time.time())
            draft = self._drafts.get(draft_id)
        if draft is None:
            raise MessagingError("That message draft expired or does not exist. Start again; nothing was sent.")
        return draft

    def _expire_old_drafts(self, now: float) -> None:
        terminal = {
            WorkflowStage.SENT,
            WorkflowStage.SENT_UNVERIFIED,
            WorkflowStage.CANCELLED,
            WorkflowStage.FAILED,
            WorkflowStage.EXPIRED,
        }
        for draft_id, draft in list(self._drafts.items()):
            if now - draft.updated_at <= self.DRAFT_TTL_SECONDS:
                continue
            if draft.stage in terminal:
                del self._drafts[draft_id]
            else:
                draft.stage = WorkflowStage.EXPIRED
                draft.result = "Draft expired. Nothing was sent."

    @staticmethod
    def _choice_prompt(draft: MessageDraft) -> str:
        options = "\n".join(
            f"{candidate.id}. {candidate.display_name}"
            + (f" ({candidate.context})" if candidate.context else "")
            + (" (exact name)" if candidate.exact else f" (similar, {candidate.confidence:.0%})")
            for candidate in draft.candidates
        )
        return (
            f"I found several or similar {draft.platform.value.title()} chats for “{draft.requested_recipient}”. "
            f"Choose the correct chat by number:\n{options}\nNo message has been typed or sent."
        )

    @staticmethod
    def _confirmation_prompt(draft: MessageDraft) -> str:
        return (
            f"I opened {draft.platform.value.title()} chat “{draft.selected_recipient}” and prepared this message:\n\n"
            f"{draft.message}\n\nIt has NOT been sent. Reply ‘confirm send’ or ‘send it’ to send, or ‘cancel’ to clear it."
        )
