import type { PipelineEntry } from "./types";

const STORAGE_KEY = "vf_pipeline";

export async function getPipeline(): Promise<PipelineEntry[]> {
  return new Promise((resolve) => {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      resolve((result[STORAGE_KEY] as PipelineEntry[]) ?? []);
    });
  });
}

export async function isTracked(url: string): Promise<boolean> {
  const entries = await getPipeline();
  return entries.some((e) => e.jobInfo.url === url);
}

// Returns false if the job URL is already tracked (dedup by URL).
export async function addEntry(entry: PipelineEntry): Promise<boolean> {
  const existing = await getPipeline();
  if (existing.some((e) => e.jobInfo.url === entry.jobInfo.url)) return false;
  return new Promise((resolve) => {
    chrome.storage.local.set({ [STORAGE_KEY]: [entry, ...existing] }, () => resolve(true));
  });
}

export async function removeEntry(id: string): Promise<void> {
  const entries = await getPipeline();
  return new Promise((resolve) => {
    chrome.storage.local.set({ [STORAGE_KEY]: entries.filter((e) => e.id !== id) }, resolve);
  });
}

export async function updateStatus(
  id: string,
  status: PipelineEntry["status"]
): Promise<void> {
  const entries = await getPipeline();
  const updated = entries.map((e) => (e.id === id ? { ...e, status } : e));
  return new Promise((resolve) => {
    chrome.storage.local.set({ [STORAGE_KEY]: updated }, resolve);
  });
}
