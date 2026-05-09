import { detectJob } from "./detectors";
import { autofillField } from "./autofill";
import type { MessageType } from "../lib/types";

let currentJob = null as ReturnType<typeof detectJob>;

// Workday job ID is the _R123456 suffix in the URL path — present on both
// the listing page and the /apply/applyManually page.
const getWorkdayJobId = (): string | null => {
  if (!location.hostname.endsWith(".myworkdayjobs.com")) return null;
  return location.pathname.match(/_([A-Z]\d+)/)?.[1] ?? null;
};

const loadAndBroadcast = async () => {
  const detected = detectJob();
  if (!detected) return;

  const jobId = getWorkdayJobId();

  if (jobId) {
    if (detected.description) {
      // On job listing page — cache the description for later
      chrome.storage.local.set({ [`wd_desc_${jobId}`]: detected.description });
    } else {
      // On apply page — pull cached description from the listing page visit
      const data = await chrome.storage.local.get(`wd_desc_${jobId}`);
      if (data[`wd_desc_${jobId}`]) {
        detected.description = data[`wd_desc_${jobId}`];
      }
    }
  }

  currentJob = detected;
  console.log("[visa-rank] location:", currentJob.location);
  console.log("[visa-rank] description:", currentJob.description);
  chrome.runtime.sendMessage<MessageType>({ type: "JOB_DETECTED", payload: currentJob });
};

// Re-detect on SPA navigation (Workday/LinkedIn use pushState)
let lastUrl = location.href;
const observer = new MutationObserver(() => {
  if (location.href === lastUrl) return;
  const detected = detectJob();
  if (detected) {
    lastUrl = location.href;
    loadAndBroadcast();
  }
});

observer.observe(document.body, { childList: true, subtree: true });

loadAndBroadcast();

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
