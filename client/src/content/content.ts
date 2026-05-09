import { detectJob } from "./detectors";
import { autofillField } from "./autofill";
import type { MessageType } from "../lib/types";

let currentJob = detectJob();

// Re-detect on SPA navigation (Workday, LinkedIn use pushState)
const observer = new MutationObserver(() => {
  const detected = detectJob();
  if (detected && detected.url !== currentJob?.url) {
    currentJob = detected;
    chrome.runtime.sendMessage<MessageType>({ type: "JOB_DETECTED", payload: currentJob });
  }
});

observer.observe(document.body, { childList: true, subtree: true });

if (currentJob) {
  chrome.runtime.sendMessage<MessageType>({ type: "JOB_DETECTED", payload: currentJob });
}

chrome.runtime.onMessage.addListener((msg: MessageType, _sender, sendResponse) => {
  if (msg.type === "GET_JOB_INFO") {
    sendResponse({ type: "JOB_INFO_RESPONSE", payload: currentJob });
  }

  if (msg.type === "AUTOFILL_REQUESTED") {
    const success = autofillField(msg.payload.fieldType);
    sendResponse({ success });
  }

  return true;
});
