import type { JobInfo, AnalysisResponse } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// TODO: point this at your real backend endpoint once it's ready.
// The body includes job.description (scraped job summary) + job.location so the
// backend can run LLM visa-fit analysis.
export async function analyzeJob(job: JobInfo): Promise<AnalysisResponse> {
  try {
    const res = await fetch(`${BASE_URL}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(job),
    });

    if (!res.ok) throw new Error(`API error ${res.status}`);

    return res.json() as Promise<AnalysisResponse>;
  } catch {
    // PLACEHOLDER: backend not running — return mock data so the UI works.
    // Remove this block once the backend is live.
    return {
      jobInfo: job,
      analysis: {
        company: job.company,
        sponsorScore: 0,
        verdict: "unknown",
        h1bHistory: [],
        notes: "Backend not connected — this is placeholder data.",
      },
    };
  }
}
