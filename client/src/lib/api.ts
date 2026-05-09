import type { JobInfo, AnalysisResponse } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const analyzeJob = async (job: JobInfo): Promise<AnalysisResponse> => {
  const res = await fetch(`${BASE_URL}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(job),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }

  return res.json() as Promise<AnalysisResponse>;
};

export interface HealthStatus {
  ok: boolean;
  db_rows: number | null;
  model_loaded: boolean;
  schema_version: number;
}

export const checkHealth = async (): Promise<HealthStatus> => {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json() as Promise<HealthStatus>;
};
