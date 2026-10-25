const requestField = document.querySelector("#request");
const prepareButton = document.querySelector("#prepare");
const responsePanel = document.querySelector("#response");
const responseTitle = document.querySelector("#response-title");
const responseContent = document.querySelector("#response-content");
const responseActions = document.querySelector("#response-actions");
let activeDraftId = null;
let busy = false;

function showMessage(title, message, kind = "") {
  responsePanel.hidden = false;
  responsePanel.dataset.kind = kind;
  responseTitle.textContent = title;
  responseContent.replaceChildren();
  responseActions.replaceChildren();
  const paragraph = document.createElement("p");
  paragraph.className = "response-copy";
  paragraph.textContent = message;
  responseContent.append(paragraph);
}

function button(label, onClick, className = "secondary") {
  const element = document.createElement("button");
  element.type = "button";
  element.className = className;
  element.textContent = label;
  element.addEventListener("click", onClick);
  responseActions.append(element);
  return element;
}

async function post(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  let result;
  try { result = await response.json(); } catch { throw new Error("The local service returned an unreadable response."); }
  if (!response.ok) throw new Error(result.error || "The request could not be completed.");
  return result;
}

function renderWorkflow(result) {
  const stage = result.stage;
  activeDraftId = result.draft_id || activeDraftId;

  if (stage === "awaiting_recipient_choice") {
    showMessage("Choose the right chat", result.prompt || result.result);
    for (const candidate of result.candidates || []) {
      const context = candidate.context ? ` · ${candidate.context}` : "";
      const detail = candidate.exact ? " · exact name" : ` · similar · ${Math.round(candidate.confidence * 100)}%`;
      button(`${candidate.display_name}${context}${detail}`, async () => {
        setBusy(true);
        try {
          const next = await post("/api/recipient", { draft_id: activeDraftId, candidate_id: candidate.id });
          renderWorkflow(next);
        } catch (error) {
          showMessage("Couldn’t select that chat", error.message, "error");
        } finally { setBusy(false); }
      }, "choice");
    }
    return;
  }

  if (stage === "awaiting_confirmation") {
    showMessage("Review before sending", result.prompt || result.result, "approval");
    button("Confirm & send", () => confirmSend("confirm send"), "primary");
    button("Cancel", cancelDraft, "secondary");
    return;
  }

  const sent = stage === "sent";
  const uncertain = stage === "sent_unverified";
  const title = sent ? "Message sent" : uncertain ? "Check the chat" : stage === "cancelled" ? "Cancelled" : stage === "failed" ? "Couldn’t prepare the message" : "Weronika";
  showMessage(title, result.prompt || result.result || "No message was sent.", sent ? "success" : uncertain ? "warning" : "");
  if (stage === "sent" || stage === "sent_unverified" || stage === "cancelled" || stage === "failed") activeDraftId = null;
}

async function confirmSend(confirmation) {
  if (!activeDraftId) return;
  setBusy(true);
  try {
    const result = await post("/api/confirm", { draft_id: activeDraftId, confirmation });
    renderWorkflow(result);
  } catch (error) {
    showMessage("Not sent", error.message, "error");
  } finally { setBusy(false); }
}

async function cancelDraft() {
  if (!activeDraftId) return;
  setBusy(true);
  try {
    const result = await post("/api/cancel", { draft_id: activeDraftId });
    renderWorkflow(result);
  } catch (error) {
    showMessage("Couldn’t cancel", error.message, "error");
  } finally { setBusy(false); }
}

function setBusy(value) {
  busy = value;
  prepareButton.disabled = value;
  prepareButton.textContent = value ? "Working…" : "Prepare message ↗";
  responseActions.querySelectorAll("button").forEach((item) => { item.disabled = value; });
}

async function prepareRequest() {
  if (busy) return;
  const text = requestField.value.trim();
  if (!text) {
    requestField.focus();
    return;
  }
  if (activeDraftId && /^(?:confirm send|send it|send the message)[.! ]*$/i.test(text)) {
    requestField.value = "";
    await confirmSend(text);
    return;
  }
  if (activeDraftId && /^cancel[.! ]*$/i.test(text)) {
    requestField.value = "";
    await cancelDraft();
    return;
  }

  setBusy(true);
  showMessage("Preparing safely", "Looking for the intended chat. Nothing will be sent without your approval.");
  try {
    const result = await post("/api/message", { text });
    requestField.value = "";
    if (result.handled === false) {
      activeDraftId = null;
      showMessage("Try a messaging request", result.prompt);
    } else if (result.draft_id) {
      renderWorkflow(result);
    } else {
      showMessage("One more detail", result.prompt || "Please provide a recipient and the exact message.");
    }
  } catch (error) {
    showMessage("Couldn’t prepare that message", error.message, "error");
  } finally { setBusy(false); }
}

prepareButton.addEventListener("click", prepareRequest);
requestField.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) prepareRequest();
});
