"""WhatsApp Web calls, in the browser window you already signed in to.

This is the same visible-automation approach reply watch uses, applied to calling:

* The signed-in WhatsApp Web page shows an incoming call with answer and decline
  controls. This adapter reads what the page is actually showing and presses those
  controls. It never opens the browser window itself — scanning for a ringing call every
  couple of seconds must not launch a window as a side effect — and it refuses to guess
  when the page does not look like a call it recognises.
* **Audio.** WhatsApp Web plays the caller's voice through this computer's speakers and
  sends this computer's microphone into the call, so the plain route works exactly as it
  does for a phone on speaker. On top of that, when the page exposes the caller's audio as
  a ``MediaStream`` on an ``<audio>`` element, a small in-page tap can hear it directly —
  no room noise, no echo — and hand 16-bit samples to the local speech engine. The tap is
  optional: if it cannot attach, the microphone route is used and the orb says which one
  is live.
* **Telegram has no calls.** Telegram Web cannot call and Telegram's Bot API cannot make or
  receive calls, so there is no adapter for it anywhere in this worker.

Selectors on a site change, so the JavaScript below collects *candidates* with their
labels and lets Python decide what they mean. A call that cannot be recognised with
confidence is reported as "not a call I can read", never answered blindly.
"""

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from .call_audio import SAMPLE_RATE, resample_pcm
from .calls import IncomingCall
from .models import CallChannel, CallRoute, Platform

# Marks the elements this worker found, so a later click can address exactly the node that
# was described. Nothing else on the page is touched.
TAG_ATTRIBUTE = "data-weronika-call"

CALL_SCAN_JS = """
(marker) => {
  const WORDS = /(answer|accept|decline|reject|end\\s*call|hang\\s*up|incoming\\s*call|ringing|on a call|call ended|voice call|video call|caller|mute|speakerphone|\\u0938\\u094D\\u0935\\u0940\\u0915\\u093E\\u0930|\\u091C\\u0935\\u093E\\u092C|\\u0915\\u093E\\u091F)/i;
  const nodes = Array.from(document.querySelectorAll(
    'button,[role="button"],[aria-label],[data-icon],[title],div[class*="call" i],span[class*="call" i]'
  ));
  const candidates = [];
  for (const node of nodes) {
    const label = (node.getAttribute('aria-label') || node.getAttribute('title') || '').trim();
    const icon = (node.getAttribute('data-icon') || '').trim();
    const text = (node.textContent || '').trim().slice(0, 120);
    if (!WORDS.test(label) && !WORDS.test(icon) && !WORDS.test(text)) continue;
    const rect = node.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) continue;
    const panel = node.closest('[role="dialog"]') || node.parentElement && node.parentElement.parentElement;
    candidates.push({
      index: candidates.length,
      label, icon, text,
      tag: node.tagName,
      clickable: node.tagName === 'BUTTON' || node.getAttribute('role') === 'button' || !!label || !!icon,
      panel_text: ((panel && panel.innerText) || '').trim().slice(0, 240),
    });
    node.setAttribute(marker, String(candidates.length - 1));
  }
  const signedIn = !!(document.querySelector('#pane-side, [data-testid="chat-list"], [aria-label*="Chat list" i]'));
  const body = (document.body && document.body.innerText || '').slice(0, 600);
  return {
    url: location.href,
    signed_in: signedIn,
    needs_login: /scan (?:the )?qr|link a device|log ?in|whatsapp web/i.test(body) && !signedIn,
    candidates,
  };
}
"""

CLICK_JS = """
(marker, index) => {
  const node = document.querySelector(`${marker}="${index}"`);
  if (!node) return { clicked: false, reason: 'that control is no longer on the page' };
  const rect = node.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return { clicked: false, reason: 'that control is not visible' };
  node.scrollIntoView({ block: 'center' });
  node.click();
  return { clicked: true, label: node.getAttribute('aria-label') || node.textContent || '' };
}
"""

CLEAR_JS = """
(marker) => {
  document.querySelectorAll(`[${marker}]`).forEach((node) => node.removeAttribute(marker));
  return true;
}
"""

# The optional in-page tap: hears the caller's own audio stream instead of the room.
# The processor is connected through a zero-gain node because a ScriptProcessor only runs
# while it reaches the destination, and reaching it audibly would echo the caller twice.
AUDIO_TAP_JS = """
() => {
  const existing = window.__weronikaCall;
  if (existing && existing.installed) return existing.status();
  const state = { installed: true, attached: false, error: '', chunks: [], ctx: null, sampleRate: 0 };
  const api = {
    installed: true,
    status() {
      return {
        attached: state.attached, error: state.error,
        queued: state.chunks.reduce((total, item) => total + item.byteLength, 0),
        sampleRate: state.sampleRate,
      };
    },
    attach() {
      try {
        const elements = Array.from(document.querySelectorAll('audio, video'));
        const withAudio = elements.filter(
          (el) => el.srcObject && typeof el.srcObject.getAudioTracks === 'function'
            && el.srcObject.getAudioTracks().length > 0
        );
        if (!withAudio.length) { state.error = 'the page is not playing a call stream'; state.attached = false; return false; }
        // Our own microphone feed is muted in the page; the caller's is not.
        const target = withAudio.find((el) => !el.muted) || withAudio[0];
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) { state.error = 'this browser exposes no AudioContext'; return false; }
        state.ctx = state.ctx || new Ctx();
        state.sampleRate = state.ctx.sampleRate || 48000;
        const source = state.ctx.createMediaStreamSource(target.srcObject);
        const processor = state.ctx.createScriptProcessor(4096, 1, 1);
        const mute = state.ctx.createGain();
        mute.gain.value = 0;
        processor.onaudioprocess = (event) => {
          const input = event.inputBuffer.getChannelData(0);
          const out = new Int16Array(input.length);
          for (let i = 0; i < input.length; i += 1) {
            const sample = Math.max(-1, Math.min(1, input[i]));
            out[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
          }
          state.chunks.push(out.buffer);
          // About thirty seconds of unheard audio is the most the page will hold.
          let total = state.chunks.reduce((sum, item) => sum + item.byteLength, 0);
          while (total > 960000 && state.chunks.length > 1) {
            total -= state.chunks.shift().byteLength;
          }
        };
        source.connect(processor);
        processor.connect(mute);
        mute.connect(state.ctx.destination);
        state.attached = true;
        state.error = '';
        return true;
      } catch (error) {
        state.error = String(error && error.message ? error.message : error);
        state.attached = false;
        return false;
      }
    },
    detach() {
      state.attached = false;
      state.chunks = [];
      return true;
    },
    drain() {
      const chunks = state.chunks.splice(0, state.chunks.length);
      const total = chunks.reduce((sum, item) => sum + item.byteLength, 0);
      const joined = new Uint8Array(total);
      let offset = 0;
      for (const chunk of chunks) {
        joined.set(new Uint8Array(chunk), offset);
        offset += chunk.byteLength;
      }
      let binary = '';
      for (let i = 0; i < joined.length; i += 1) binary += String.fromCharCode(joined[i]);
      return { sampleRate: state.sampleRate, attached: state.attached, error: state.error,
               pcm: joined.length ? btoa(binary) : '' };
    },
  };
  window.__weronikaCall = api;
  return api.status();
}
"""

_ACCEPT_WORDS = ("answer", "accept", "स्वीकार", "जवाब")
_DECLINE_WORDS = ("decline", "reject", "काट", "इनकार")
_END_WORDS = ("end call", "end the call", "hang up", "hangup", "end_call", "call-end")
_RINGING_WORDS = ("incoming call", "ringing", "is calling", "call from")
_ACTIVE_WORDS = ("on a call", "call ended", "mute", "speakerphone")
_CALL_ICON_RE = re.compile(r"(?:call|answer|decline|hangup|hang-up|end|accept|reject)", re.IGNORECASE)


class WhatsappCallError(RuntimeError):
    """An expected, user-actionable problem with the WhatsApp call channel."""


@dataclass(frozen=True)
class Candidate:
    """One call-ish control the page is showing."""

    index: int
    label: str = ""
    icon: str = ""
    text: str = ""
    clickable: bool = True
    panel_text: str = ""

    @property
    def words(self) -> str:
        return " ".join(part for part in (self.label, self.icon, self.text) if part).casefold()


@dataclass(frozen=True)
class CallReading:
    """What the page means, decided in Python rather than in the browser."""

    state: str  # "ringing", "active", "idle", or "unknown"
    caller: str = ""
    candidates: tuple[Candidate, ...] = ()
    reason: str = ""

    def pick(self, kind: str) -> Candidate | None:
        return pick_button(self.candidates, kind)


# A "page" here is anything with an ``evaluate(script, *args)`` method, which Playwright's
# own page satisfies. Keeping it that loose is what makes the adapter testable without a
# browser installed.


def parse_candidates(payload: Sequence[dict]) -> tuple[Candidate, ...]:
    candidates = []
    for entry in payload or ():
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        candidates.append(
            Candidate(
                index=index,
                label=str(entry.get("label") or "").strip(),
                icon=str(entry.get("icon") or "").strip(),
                text=str(entry.get("text") or "").strip(),
                clickable=bool(entry.get("clickable", True)),
                panel_text=str(entry.get("panel_text") or "").strip(),
            )
        )
    return tuple(candidates)


def pick_button(candidates: Sequence[Candidate], kind: str) -> Candidate | None:
    """Choose the control to press, by label first and by icon only when no label exists.

    Answering a call is irreversible, so a match has to be specific: "Decline" is never
    accepted as an answer button, and a generic "call" icon is not enough on its own.
    """
    wanted = {
        "accept": _ACCEPT_WORDS,
        "decline": _DECLINE_WORDS,
        "end": _END_WORDS,
    }.get(kind)
    if not wanted:
        return None
    clickable = [item for item in candidates if item.clickable]
    for item in clickable:
        label = item.label.casefold()
        if any(word in label for word in wanted):
            return item
    for item in clickable:
        text = item.text.casefold()
        if any(word in text for word in wanted) and len(text) < 40:
            return item
    for item in clickable:
        icon = item.icon.casefold()
        if any(word in icon for word in wanted) and _CALL_ICON_RE.search(icon):
            return item
    return None


def caller_from_panel(panel_text: str) -> str:
    """The first plausible name line in the call panel's own text."""
    for raw in (panel_text or "").splitlines():
        line = " ".join(raw.split())
        if not line or len(line) > 60:
            continue
        lowered = line.casefold()
        if any(word in lowered for word in _RINGING_WORDS + _ACTIVE_WORDS):
            continue
        if re.search(r"\b(?:whatsapp|call|audio|video|mute|speaker|end|decline|answer)\b", lowered):
            continue
        if re.fullmatch(r"[\d\s:+().-]{4,}", line):
            continue
        return line
    return ""


def interpret_call_dom(payload: dict) -> CallReading:
    """Decide whether the page shows a ringing call, a live call, or no call at all."""
    if not isinstance(payload, dict):
        return CallReading(state="unknown", reason="the page did not report its call controls")
    if payload.get("needs_login"):
        return CallReading(state="idle", reason="WhatsApp Web is not signed in in this window")
    candidates = parse_candidates(payload.get("candidates") or [])
    if not candidates:
        return CallReading(state="idle", candidates=candidates, reason="no call is showing on the page")

    accept = pick_button(candidates, "accept")
    end = pick_button(candidates, "end")
    ringing_text = any(
        any(word in item.words for word in _RINGING_WORDS) for item in candidates
    )
    panels = [item.panel_text for item in candidates if item.panel_text]
    caller = ""
    for panel in panels:
        caller = caller_from_panel(panel)
        if caller:
            break

    if accept is not None or ringing_text:
        if accept is None:
            return CallReading(
                state="unknown",
                caller=caller,
                candidates=candidates,
                reason=(
                    "the page looks like an incoming call but Weronika cannot find a control "
                    "she is sure answers it, so she will not press anything"
                ),
            )
        return CallReading(state="ringing", caller=caller, candidates=candidates)
    if end is not None:
        return CallReading(state="active", caller=caller, candidates=candidates)
    return CallReading(
        state="unknown",
        caller=caller,
        candidates=candidates,
        reason="the page shows call controls Weronika does not recognise",
    )


class WhatsappCallAdapter:
    """Drives WhatsApp Web calling in the window that is already signed in."""

    def __init__(self, browser=None, *, page_provider: Callable[[], object] | None = None) -> None:
        self._browser = browser
        self._page_provider = page_provider
        self.channel = CallChannel.WHATSAPP
        self._last_reading: CallReading | None = None
        self._call_seen_at = 0.0

    # ------------------------------------------------------------------ plumbing

    def _page(self):
        if self._page_provider is not None:
            return self._page_provider()
        if self._browser is None:
            return None
        getter = getattr(self._browser, "signed_in_page", None)
        if getter is None:
            return None
        return getter(Platform.WHATSAPP)

    def _scan(self) -> tuple[CallReading, dict]:
        page = self._page()
        if page is None:
            return (
                CallReading(
                    state="idle",
                    reason=(
                        "the WhatsApp window is not open. Say “open WhatsApp” and sign in, "
                        "then Weronika can watch it for calls."
                    ),
                ),
                {},
            )
        try:
            page.evaluate(CLEAR_JS, TAG_ATTRIBUTE)
            payload = page.evaluate(CALL_SCAN_JS, TAG_ATTRIBUTE)
        except Exception as exc:
            return CallReading(state="unknown", reason=f"the WhatsApp page could not be read ({exc})"), {}
        reading = interpret_call_dom(payload if isinstance(payload, dict) else {})
        return reading, payload if isinstance(payload, dict) else {}

    def _press(self, candidate: Candidate) -> None:
        page = self._page()
        if page is None:
            raise WhatsappCallError("The WhatsApp window closed, so the call cannot be controlled.")
        try:
            result = page.evaluate(CLICK_JS, TAG_ATTRIBUTE, candidate.index)
        except Exception as exc:
            raise WhatsappCallError(f"The WhatsApp page refused the click ({exc}).") from exc
        if not isinstance(result, dict) or not result.get("clicked"):
            reason = result.get("reason") if isinstance(result, dict) else "the control did not respond"
            raise WhatsappCallError(f"Weronika could not press that control: {reason}.")

    # -------------------------------------------------------------- capabilities

    def capabilities(self) -> dict[str, object]:
        reading, payload = self._scan()
        if reading.state == "idle" and "not open" in reading.reason:
            return {
                "available": False,
                "detect": False,
                "answer": False,
                "reason": reading.reason,
                "signed_in": False,
            }
        signed_in = bool(payload.get("signed_in")) if payload else False
        report: dict[str, object] = {
            "available": signed_in,
            "detect": signed_in,
            "answer": signed_in,
            "hang_up": signed_in,
            "decline": signed_in,
            "speaker": False,
            "signed_in": signed_in,
            "reason": "" if signed_in else (reading.reason or "sign in to WhatsApp Web in the Weronika window"),
            "note": (
                "WhatsApp Web calling works in the window you signed in to. Its audio uses this "
                "computer's microphone and speakers, or the in-page tap when the call stream is "
                "reachable. If WhatsApp changes this screen, Weronika stops instead of guessing."
            ),
        }
        return report

    # ------------------------------------------------------------------ detection

    def ringing_calls(self) -> list[IncomingCall]:
        reading, _payload = self._scan()
        self._last_reading = reading
        if reading.state not in {"ringing", "active"}:
            if reading.state == "unknown" and reading.reason:
                raise WhatsappCallError(reading.reason)
            return []
        now = time.time()
        if reading.state == "ringing" and not self._call_seen_at:
            self._call_seen_at = now
        return [
            IncomingCall(
                channel=CallChannel.WHATSAPP,
                call_id="whatsapp-call",
                caller=reading.caller,
                number="",
                seen_at=self._call_seen_at or now,
                is_video=any("video" in item.words for item in reading.candidates),
                device="whatsapp-web",
                active=reading.state == "active",
            )
        ]

    def answer(self, call: IncomingCall | None = None) -> None:
        reading = self._reading()
        accept = reading.pick("accept")
        if accept is None:
            raise WhatsappCallError(
                "Weronika cannot find an answer control she is sure of on the WhatsApp screen, "
                "so she is not pressing anything."
            )
        self._press(accept)
        if not self.is_active():
            raise WhatsappCallError(
                "WhatsApp did not show the call as connected after answering, so Weronika stopped."
            )

    def hang_up(self, call: IncomingCall | None = None) -> None:
        reading = self._reading()
        for kind in ("end", "decline"):
            button = reading.pick(kind)
            if button is not None:
                self._press(button)
                return
        raise WhatsappCallError("Weronika cannot find an end-call control on the WhatsApp screen.")

    def decline(self, call: IncomingCall | None = None) -> None:
        reading = self._reading()
        button = reading.pick("decline") or reading.pick("end")
        if button is None:
            raise WhatsappCallError("Weronika cannot find a decline control on the WhatsApp screen.")
        self._press(button)

    def set_speaker(self, call: IncomingCall | None = None, enabled: bool = True) -> None:
        # The browser already plays the call through this computer's speakers.
        return None

    def is_active(self, call: IncomingCall | None = None) -> bool:
        reading, _payload = self._scan()
        self._last_reading = reading
        if reading.state == "idle":
            self._call_seen_at = 0.0
        return reading.state == "active"

    def _reading(self) -> CallReading:
        reading, _payload = self._scan()
        self._last_reading = reading
        return reading


class BrowserCallAudio:
    """Hears a WhatsApp call through the in-page tap, and speaks through this computer.

    ``hear`` polls the page for samples, resamples them to the rate the speech engines
    want, and stops at the same pause the microphone route uses. When the tap cannot
    attach — no call stream, a browser that blocks it, a page that changed — this falls
    back to the microphone route rather than reporting silence as "the caller said nothing".
    """

    def __init__(self, adapter: WhatsappCallAdapter, *, fallback=None, transcriber=None, speaker=None,
                 language: str = "", clock: Callable[[], float] = time.monotonic) -> None:
        self._adapter = adapter
        self._fallback = fallback
        self._transcriber = transcriber
        self._speaker = speaker
        self._language = language
        self._clock = clock
        self._attached = False
        self._error = ""
        # The page tap only proves itself available once attached, and that happens inside
        # the first listen. Until it fails, treat it as available, so a WhatsApp call is not
        # reported as unhearable before Weronika has even tried.
        self._tap_available = True

    @property
    def automatic(self) -> bool:
        """True only when a real engine can turn heard audio into words on this route."""
        if self._transcriber is None or not self._transcriber.automatic:
            return False
        return self.route() is not CallRoute.NONE or self._tap_available

    def route(self) -> CallRoute:
        return CallRoute.BROWSER if self._attached else (
            self._fallback.route() if self._fallback is not None else CallRoute.NONE
        )

    def capabilities(self) -> dict[str, object]:
        fallback = (
            self._fallback.capabilities()
            if self._fallback is not None and hasattr(self._fallback, "capabilities")
            else {"available": False, "reason": ""}
        )
        return {
            "available": self._attached or self._tap_available or bool(fallback.get("available")),
            "route": self.route().value,
            "automatic": self.automatic,
            "reason": self._error or str(fallback.get("reason") or ""),
            "engine": "whatsapp-page-tap" if self._attached else "microphone",
            "fallback": {"route": self.route().value, "automatic": bool(fallback.get("automatic"))},
        }

    def _page(self):
        return self._adapter._page()

    def _ensure_attached(self) -> bool:
        page = self._page()
        if page is None:
            self._error = "the WhatsApp window is not open"
            self._tap_available = False
            return False
        try:
            page.evaluate(AUDIO_TAP_JS)
            result = page.evaluate("() => window.__weronikaCall.attach()")
        except Exception as exc:
            self._error = f"the page tap could not be installed ({exc})"
            self._attached = False
            self._tap_available = False
            return False
        self._attached = bool(result)
        if not self._attached:
            self._error = "WhatsApp is not exposing the call audio to the page"
            self._tap_available = False
        return self._attached

    def hear(self, seconds: float) -> str:
        if not self.automatic:
            return ""
        if not self._attached and not self._ensure_attached():
            if self._fallback is not None:
                return self._fallback.hear(seconds)
            return ""
        page = self._page()
        collected = bytearray()
        rate = 0
        deadline = self._clock() + max(1.0, seconds)
        while self._clock() < deadline:
            try:
                payload = page.evaluate("() => window.__weronikaCall.drain()")
            except Exception as exc:
                self._attached = False
                self._tap_available = False
                self._error = f"the page tap stopped working ({exc})"
                if self._fallback is not None:
                    return self._fallback.hear(seconds)
                return ""
            if isinstance(payload, dict):
                rate = int(payload.get("sampleRate") or rate or 48000)
                encoded = str(payload.get("pcm") or "")
                if encoded:
                    collected.extend(base64.b64decode(encoded))
                if len(collected) and self._clock() > deadline - 0.6:
                    break
            time.sleep(0.1)
        if not collected:
            return ""
        pcm = resample_pcm(bytes(collected), rate or 48000, SAMPLE_RATE)
        return " ".join(self._transcriber.transcribe(pcm, self._language).split())

    def say(self, text: str) -> None:
        # Weronika's voice goes out through this computer's microphone, which WhatsApp
        # already sends into the call; no page patching is needed to be heard.
        if self._speaker is not None:
            self._speaker.say(text)
        elif self._fallback is not None:
            self._fallback.say(text)

    def interrupt(self) -> None:
        for target in (self._speaker, self._fallback):
            if target is not None and hasattr(target, "interrupt"):
                target.interrupt()
