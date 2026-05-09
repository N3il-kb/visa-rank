import type { JobInfo, MessageType } from "../lib/types";

// Cache the last-detected job per tab so the popup can request it.
const tabJobCache = new Map<number, JobInfo>();
// Track tabs where the popup has already been auto-opened this session.
const autoOpenedTabs = new Set<number>();

chrome.runtime.onMessage.addListener((msg: MessageType, sender) => {
  if (msg.type === "JOB_DETECTED" && sender.tab?.id != null) {
    const tabId = sender.tab.id;
    tabJobCache.set(tabId, msg.payload);
    chrome.action.setBadgeText({ text: "✓", tabId });
    chrome.action.setBadgeBackgroundColor({ color: "#16a34a", tabId });

    if (!autoOpenedTabs.has(tabId)) {
      autoOpenedTabs.add(tabId);
      chrome.action.openPopup({ tabId }).catch(() => {
        // openPopup requires the tab to be active; silently ignore if it isn't.
      });
    }
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  tabJobCache.delete(tabId);
  autoOpenedTabs.delete(tabId);
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
