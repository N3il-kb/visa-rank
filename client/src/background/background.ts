import type { JobInfo, MessageType } from "../lib/types";

// Cache the last-detected job per tab so the popup can request it.
const tabJobCache = new Map<number, JobInfo>();

chrome.runtime.onMessage.addListener((msg: MessageType, sender) => {
  if (msg.type === "JOB_DETECTED" && sender.tab?.id != null) {
    tabJobCache.set(sender.tab.id, msg.payload);
    chrome.action.setBadgeText({ text: "✓", tabId: sender.tab.id });
    chrome.action.setBadgeBackgroundColor({ color: "#16a34a", tabId: sender.tab.id });
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  tabJobCache.delete(tabId);
});

// Expose cache to popup via chrome.runtime.sendMessage from popup
chrome.runtime.onMessage.addListener((msg: MessageType, _sender, sendResponse) => {
  if (msg.type === "GET_JOB_INFO") {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      sendResponse({
        type: "JOB_INFO_RESPONSE",
        payload: tab?.id != null ? (tabJobCache.get(tab.id) ?? null) : null,
      });
    });
    return true;
  }
});
