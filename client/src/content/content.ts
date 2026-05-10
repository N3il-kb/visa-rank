import { detectJob } from "./detectors";
import { autofillField } from "./autofill";
import type { JobInfo, MessageType } from "../lib/types";

// iCIMS renders the real job DOM inside an iframe (?in_iframe=1). With
// all_frames: true, this script runs in BOTH the wrapper and the iframe —
// and chrome.tabs.sendMessage races their responses, so the wrapper's null
// reply can clobber the iframe's real one. Bail out of the wrapper.
const isIcimsWrapperFrame =
  location.hostname.endsWith(".icims.com") &&
  new URLSearchParams(location.search).get("in_iframe") !== "1";

let currentJob = null as JobInfo | null;

const getWorkdayJobId = (): string | null => {
  if (!location.hostname.endsWith(".myworkdayjobs.com")) return null;
  return location.pathname.match(/_([A-Z]\d+)/)?.[1] ?? null;
};

const isMoreComplete = (next: JobInfo, prev: JobInfo | null): boolean => {
  if (!prev) return true;
  // Prefer whichever result has more populated fields.
  const score = (j: JobInfo) =>
    (j.company ? 1 : 0) +
    (j.title ? 1 : 0) +
    (j.location ? 1 : 0) +
    (j.description ? 2 : 0); // weight description — it's the last to render
  return score(next) > score(prev);
};

const loadAndBroadcast = async () => {
  const detected = detectJob();
  if (!detected) return;

  const jobId = getWorkdayJobId();
  if (jobId) {
    if (detected.description) {
      chrome.storage.local.set({ [`wd_desc_${jobId}`]: detected.description });
    } else {
      const data = await chrome.storage.local.get(`wd_desc_${jobId}`);
      if (data[`wd_desc_${jobId}`]) detected.description = data[`wd_desc_${jobId}`];
    }
  }

  // Only update and broadcast if the new result is more complete than what
  // we already have — avoids overwriting good data with a partial early read.
  if (isMoreComplete(detected, currentJob)) {
    currentJob = detected;
    chrome.runtime.sendMessage<MessageType>({ type: "JOB_DETECTED", payload: currentJob });
  }
};

// Re-detect on URL change (SPA navigation) OR when content settles on
// the same URL — handles async-rendered job details (Workday, LinkedIn).
let lastUrl = location.href;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

if (!isIcimsWrapperFrame) {
  const observer = new MutationObserver(() => {
    const urlChanged = location.href !== lastUrl;
    if (urlChanged) lastUrl = location.href;

    // Debounce: wait 600ms after DOM settles before re-running detection.
    // This covers both SPA navigation and async content rendering on the same URL.
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      loadAndBroadcast();
    }, 600);
  });

  observer.observe(document.body, { childList: true, subtree: true });

  loadAndBroadcast();

  chrome.runtime.onMessage.addListener((msg: MessageType, _sender, sendResponse) => {
    if (msg.type === "GET_JOB_INFO") {
      sendResponse({ type: "JOB_INFO_RESPONSE", payload: currentJob });
    }

    if (msg.type === "REDETECT") {
      loadAndBroadcast().then(() => sendResponse({ payload: currentJob }));
      return true;
    }

    if (msg.type === "AUTOFILL_REQUESTED") {
      const success = autofillField(msg.payload.fieldType);
      sendResponse({ success });
    }

    return true;
  });
}
