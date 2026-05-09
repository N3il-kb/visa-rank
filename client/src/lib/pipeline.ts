import type { PipelineEntry } from "./types";

const STORAGE_KEY = "vf_pipeline";

export async function getPipeline(): Promise<PipelineEntry[]> {
  return new Promise((resolve) => {
    chrome.storage.local.get(STORAGE_KEY, (result) => {
      resolve((result[STORAGE_KEY] as PipelineEntry[]) ?? []);
    });
  });
}

export async function addEntry(entry: PipelineEntry): Promise<void> {
  const existing = await getPipeline();
  const deduped = existing.filter((e) => e.id !== entry.id);
  return new Promise((resolve) => {
    chrome.storage.local.set({ [STORAGE_KEY]: [entry, ...deduped] }, resolve);
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
