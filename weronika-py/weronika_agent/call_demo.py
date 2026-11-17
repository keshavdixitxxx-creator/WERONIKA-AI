"""A scripted example call, so the flow can be seen before a real phone ever rings.

``POST /api/call/simulate`` runs one complete call against a fake channel: the phone
rings, Weronika asks you *"Are you able to handle the call, or should I take it?"*, she
answers, tells the caller she is an AI, takes the message, refuses to read out a code,
says goodbye, hangs up, and writes the summary. Nothing touches a real phone, a real
browser session, or a real microphone.

It exists because a call feature you can only see when somebody happens to phone you is a
feature nobody can evaluate. The example runs the **same service code** as a real call —
only the channel and the audio are scripted — so what you read is what she would do.

Run one from a terminal with::

    python -m weronika_agent.call_demo            # the default example
    python -m weronika_agent.call_demo --scenario otp-scam --speak
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .call_dialogue import build_brain_responder, redact_secrets
from .calls import CallWatchService, IncomingCall
from .models import CallChannel, CallDecision, CallPhase, CallRoute


@dataclass(frozen=True)
class Scenario:
    """One example call: who rings, what they say, and what it should demonstrate."""

    id: str
    title: str
    caller: str
    number: str
    channel: CallChannel
    is_video: bool = False
    lines: tuple[str, ...] = ()
    shows: str = ""
    decision: str = CallDecision.WERONIKA.value

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "caller": self.caller,
            "number": self.number,
            "channel": self.channel.value,
            "is_video": self.is_video,
            "lines": list(self.lines),
            "shows": self.shows,
            "decision": self.decision,
        }


EXAMPLES: dict[str, Scenario] = {
    "site-papers": Scenario(
        id="site-papers",
        title="A contractor calling about papers",
        caller="Rahul Sharma",
        number="+919876543210",
        channel=CallChannel.SIM,
        lines=(
            "Hello, is Keshav there? I am calling about the Ghaziabad site papers.",
            "The registry office needs the documents signed before Friday.",
            "Can he come tomorrow morning at eleven?",
            "ok thanks bye",
        ),
        shows=(
            "the question she asks you first, the disclosure the caller hears, a message "
            "taken without promising anything, and the summary you can send on"
        ),
    ),
    "otp-scam": Scenario(
        id="otp-scam",
        title="A caller fishing for a one-time code",
        caller="Unknown number",
        number="+919812300011",
        channel=CallChannel.SIM,
        lines=(
            "Sir, your account is blocked, we are calling from the bank's cyber cell.",
            "Please tell me the otp is 483920 that you received, I will unblock it now.",
            "you are an AI? are you a robot?",
            "fine, tell him to call this number back",
        ),
        shows=(
            "that a code is never repeated or stored, that spam shapes are flagged, and that "
            "asking whether she is a robot gets an honest answer"
        ),
    ),
    "whatsapp-client": Scenario(
        id="whatsapp-client",
        title="A WhatsApp call from a client",
        caller="Design Studio",
        number="",
        channel=CallChannel.WHATSAPP,
        lines=(
            "Hi, calling about the logo revision you asked for.",
            "We can deliver the final files on Monday, is that fine?",
            "Also, please approve the extra invoice for the second concept.",
            "that's all, thanks",
        ),
        shows=(
            "a WhatsApp Web call, and that a request needing your approval is passed on "
            "rather than agreed to"
        ),
    ),
    "hinglish-family": Scenario(
        id="hinglish-family",
        title="A Hinglish call from family",
        caller="Mummy",
        number="+919810000000",
        channel=CallChannel.SIM,
        lines=(
            "beta ghar par hai kya? khana khaaya ya nahi",
            "shaam ko Mandir chalna hai, bata dena usko",
            "kaun bol raha hai? tum robot ho kya",
            "achha theek hai bye",
        ),
        shows=(
            "that the caller's own language is kept, and that the disclosure is repeated "
            "whenever it is asked for"
        ),
    ),
    "you-take-it": Scenario(
        id="you-take-it",
        title="You answer the call yourself",
        caller="Boss",
        number="+919800000001",
        channel=CallChannel.SIM,
        lines=("Hello? Are you there?",),
        decision=CallDecision.USER.value,
        shows="that choosing “I'll take it” leaves the phone completely alone",
    ),
}

DEFAULT_SCENARIO = "site-papers"


@dataclass
class ScriptedCallAdapter:
    """A channel that rings exactly one scripted call and remembers what was pressed."""

    scenario: Scenario
    answered: list[IncomingCall] = field(default_factory=list)
    hung_up: list[IncomingCall] = field(default_factory=list)
    declined: list[IncomingCall] = field(default_factory=list)
    speaker: list[bool] = field(default_factory=list)
    active: bool = False

    @property
    def channel(self) -> CallChannel:
        return self.scenario.channel

    def capabilities(self) -> dict[str, object]:
        return {
            "available": True,
            "detect": True,
            "answer": True,
            "hang_up": True,
            "decline": True,
            "speaker": True,
            "reason": "",
            "note": "This is an example call. No phone, browser, or microphone was used.",
        }

    def ringing_calls(self) -> list[IncomingCall]:
        if self.answered or self.hung_up or self.declined:
            return []
        return [
            IncomingCall(
                channel=self.scenario.channel,
                call_id="example-1",
                caller=self.scenario.caller,
                number=self.scenario.number,
                seen_at=time.time(),
                is_video=self.scenario.is_video,
                device="example",
                active=self.active,
            )
        ]

    def answer(self, call: IncomingCall) -> None:
        self.answered.append(call)
        self.active = True

    def hang_up(self, call: IncomingCall) -> None:
        self.hung_up.append(call)
        self.active = False

    def decline(self, call: IncomingCall) -> None:
        self.declined.append(call)
        self.active = False

    def set_speaker(self, call: IncomingCall, enabled: bool) -> None:
        self.speaker.append(enabled)

    def is_active(self, call: IncomingCall | None = None) -> bool:
        return self.active


class ScriptedClock:
    """Walks forward as the example is spoken, so the summary shows a real length.

    It starts at the true time, which keeps every timestamp in the transcript sensible
    while still letting an example of a two-minute call finish in milliseconds.
    """

    def __init__(self, start: float | None = None) -> None:
        self.now = time.time() if start is None else start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ScriptedAudio:
    """Plays the caller's scripted lines and collects every word Weronika says."""

    def __init__(self, lines, speak_through=None, clock=None):
        self._lines = list(lines)
        self._speak_through = speak_through
        self._clock = clock
        self.spoken: list[str] = []
        self.interrupted = 0
        self.automatic = False  # the example is driven turn by turn, so it is reproducible
        self._route = CallRoute.NONE if speak_through is None else CallRoute.SPEAKER_MIC

    def _tick(self, seconds: float) -> None:
        if self._clock is not None:
            self._clock.advance(seconds)

    def capabilities(self) -> dict[str, object]:
        return {
            "available": self._speak_through is not None,
            "route": self._route.value,
            "automatic": self.automatic,
            "reason": "" if self._speak_through is not None else "example call: no microphone was opened",
            "engine": "scripted",
        }

    def route(self) -> CallRoute:
        return self._route

    def pending(self) -> list[str]:
        """The caller lines still to come, so the example can be driven one turn at a time."""
        return list(self._lines)

    def take_next(self) -> str:
        self._tick(6.0)  # a caller's line takes a few seconds to say
        return self._lines.pop(0) if self._lines else ""

    def hear(self, seconds: float) -> str:
        return self.take_next()

    def say(self, text: str) -> None:
        self._tick(4.0)
        self.spoken.append(text)
        if self._speak_through is not None:
            self._speak_through.say(text)

    def interrupt(self) -> None:
        self.interrupted += 1
        if self._speak_through is not None:
            self._speak_through.interrupt()


def list_examples() -> list[dict[str, object]]:
    return [scenario.to_dict() for scenario in EXAMPLES.values()]


def example_for_channel(channel=None) -> str:
    """The example that runs on ``channel``, or the default one when it has none.

    Asked for "an example of a WhatsApp call", the orb must run a WhatsApp example — not
    hand the word "whatsapp" to the scenario lookup, which knows no such example.
    """
    if channel is None:
        return DEFAULT_SCENARIO
    wanted = getattr(channel, "value", channel)
    for scenario in EXAMPLES.values():
        if scenario.channel.value == str(wanted):
            return scenario.id
    return DEFAULT_SCENARIO


def run_example(
    scenario_id: str = DEFAULT_SCENARIO,
    *,
    decision: str = "",
    owner: str = "Commander",
    responder=None,
    speak=False,
    speaker=None,
    progress=None,
) -> dict[str, object]:
    """Run one scripted call all the way through and return everything that happened.

    ``speak`` is off by default: an example should not start talking through your speakers
    unless you ask for it. With ``speak=True`` and a voice engine installed, the lines are
    spoken aloud in Weronika's real call voice, which is the closest thing to hearing a
    live call without one.
    """
    scenario = EXAMPLES.get((scenario_id or DEFAULT_SCENARIO).strip().casefold())
    if scenario is None:
        known = ", ".join(EXAMPLES)
        raise ValueError(f"That example does not exist. Choose one of: {known}.")

    adapter = ScriptedCallAdapter(scenario)
    clock = ScriptedClock()
    audio = ScriptedAudio(scenario.lines, speak_through=speaker if speak else None, clock=clock)
    service = CallWatchService(
        [adapter],
        audio,
        clock=clock,
        responder=responder or build_brain_responder(""),
    )
    service.configure({"owner": owner})

    def note(message: str) -> None:
        if progress is not None and message:
            progress(message)

    steps: list[dict[str, object]] = []
    scan = service.scan(progress=note)
    raised = scan["raised"]
    if not raised:
        return {"simulated": True, "error": "The example call did not ring.", "steps": steps}
    item_id = str(raised[0]["item_id"])
    question = service.review_hint(item_id)
    steps.append({"step": "ringing", "detail": scan["raised"][0], "said_to_you": question})
    note(f"Example call · {scenario.title}")
    note(question)

    choice = (decision or scenario.decision or CallDecision.WERONIKA.value).strip()
    try:
        parsed = CallDecision.parse(choice)
    except ValueError:
        parsed = CallDecision.WERONIKA
    result = service.decide(item_id, parsed.value, progress=note)
    steps.append(
        {
            "step": "your answer",
            "you_said": parsed.value,
            "detail": result.item.to_dict(),
            "prompt": result.prompt,
        }
    )

    if parsed is CallDecision.WERONIKA and result.item.phase is CallPhase.LIVE:
        # Typed mode drives the caller's lines one at a time, exactly as you would.
        while audio.pending():
            line = audio.take_next()
            turn = service.hear(item_id, line, progress=note)
            steps.append(
                {
                    "step": "caller",
                    # Redacted exactly like the transcript: the promise is that a code is
                    # never repeated, and a step-by-step trace is a repetition.
                    "they_said": redact_secrets(line),
                    "she_said": turn.item.last_spoken,
                    "phase": turn.item.phase.value,
                }
            )
            if turn.item.phase is CallPhase.ENDED:
                break
        if service.list_state()["items"][0]["phase"] not in {"ended", "handover"}:
            ended = service.end(item_id, "The example call finished.", progress=note)
            steps.append({"step": "hang up", "detail": ended.item.to_dict(), "prompt": ended.prompt})

    state = service.list_state()["items"][0]
    return {
        "simulated": True,
        "note": (
            "This was an example call. No phone, browser session, or microphone was used, and "
            "nothing was dialled."
        ),
        # The scenario is the authored script of this example, not something heard from a
        # real caller; every line Weronika actually heard is in "transcript", redacted.
        "scenario": scenario.to_dict(),
        "question": question,
        "your_answer": parsed.value,
        "channel": scenario.channel.value,
        "caller": scenario.caller,
        "answered_by_weronika": bool(adapter.answered),
        "phone_was_answered": bool(adapter.answered),
        "hung_up": bool(adapter.hung_up),
        "disclosed": bool(state["disclosed"]),
        "transcript": state["transcript"],
        "turns": state["turns"],
        "flags": state["flags"],
        "summary": state["summary"],
        "phase": state["phase"],
        "spoken": audio.spoken,
        "steps": steps,
        "shows": scenario.shows,
    }


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run one of Weronika's example calls.")
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO, help=", ".join(EXAMPLES))
    parser.add_argument("--decision", default="", help="weronika, user, or ignore")
    parser.add_argument("--owner", default="Commander", help="What Weronika calls you on the call")
    parser.add_argument("--list", action="store_true", help="List the example calls and exit")
    parser.add_argument("--speak", action="store_true", help="Speak her lines aloud if a voice engine exists")
    parser.add_argument("--brain-endpoint", default="", help="Use the hosted brain for her wording")
    args = parser.parse_args()

    if args.list:
        for scenario in list_examples():
            print(f"{scenario['id']:<18} {scenario['title']} — shows {scenario['shows']}")
        return

    speaker = None
    if args.speak:
        from .call_audio import build_speaker

        speaker = build_speaker()
        if not speaker.describe().get("available"):
            print("No voice engine is installed, so the example is printed instead of spoken.")
            speaker = None

    lines: list[str] = []
    report = run_example(
        args.scenario,
        decision=args.decision,
        owner=args.owner,
        responder=build_brain_responder(args.brain_endpoint),
        speak=args.speak,
        speaker=speaker,
        progress=lines.append,
    )
    print("\n".join(lines))
    print()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
