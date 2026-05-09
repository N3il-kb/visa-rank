<script lang="ts">
  import { onMount } from "svelte";
  import type { JobInfo, AnalysisResponse } from "../lib/types";
  import { analyzeJob } from "../lib/api";
  import { addEntry, isTracked } from "../lib/pipeline";
  import Header from "./components/Header.svelte";
  import SponsorBadge from "./components/SponsorBadge.svelte";
  import H1BChart from "./components/H1BChart.svelte";
  import Pipeline from "./components/Pipeline.svelte";

  type View = "job" | "pipeline";

  const isWindow = new URLSearchParams(window.location.search).get("mode") === "window";

  let view: View = "job";
  let jobInfo: JobInfo | null = null;
  let result: AnalysisResponse | null = null;
  let loading = false;
  let checked = false;
  let tracked = false;
  let fetchError: string | null = null;

  const getActiveTabId = (): Promise<number | null> =>
    new Promise((resolve) => {
      chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
        resolve(tab?.id ?? null);
      });
    });

  const getJobFromTab = async (): Promise<JobInfo | null> => {
    const tabId = await getActiveTabId();
    if (!tabId) return null;
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { type: "GET_JOB_INFO" }, (resp) => {
        if (chrome.runtime.lastError) return resolve(null);
        resolve(resp?.payload ?? null);
      });
    });
  };

  const redetectFromTab = async (): Promise<JobInfo | null> => {
    const tabId = await getActiveTabId();
    if (!tabId) return null;
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { type: "REDETECT" }, (resp) => {
        if (chrome.runtime.lastError) return resolve(null);
        resolve(resp?.payload ?? null);
      });
    });
  };

  const autofill = (fieldType: "authorized" | "sponsorship" | "visa_type") => {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (!tab?.id) return;
      chrome.tabs.sendMessage(tab.id, { type: "AUTOFILL_REQUESTED", payload: { fieldType } });
    });
  };

  const track = async () => {
    if (!result || tracked) return;
    await addEntry({
      id: crypto.randomUUID(),
      jobInfo: result.jobInfo,
      analysis: result.analysis,
      appliedAt: new Date().toISOString(),
      status: "applied",
    });
    tracked = true;
  };

  const quickTrack = async () => {
    if (!jobInfo || tracked) return;
    await addEntry({
      id: crypto.randomUUID(),
      jobInfo,
      analysis: { company: jobInfo.company, sponsorScore: 0, verdict: "unknown", h1bHistory: [], notes: "" },
      appliedAt: new Date().toISOString(),
      status: "applied",
    });
    tracked = true;
  };

  const checkVisaFit = async () => {
    if (!jobInfo) return;
    checked = true;
    loading = true;
    fetchError = null;
    try {
      result = await analyzeJob(jobInfo);
    } catch (e) {
      fetchError = e instanceof Error ? e.message : "Failed to reach backend";
      checked = false;
    } finally {
      loading = false;
    }
  };

  const refresh = async () => {
    const tabId = await getActiveTabId();
    if (tabId) chrome.tabs.reload(tabId);
  };

  let retrying = false;

  onMount(async () => {
    // Show cached result immediately (may be stale/partial).
    jobInfo = await getJobFromTab();
    if (jobInfo) tracked = await isTracked(jobInfo.url);

    // Always redetect in the background — content script scores completeness
    // and only updates if the fresh read has more data than the cached one.
    // Poll up to 8 times so we also cover the "opened too early" case.
    retrying = !jobInfo;
    for (let i = 0; i < 8; i++) {
      await new Promise((r) => setTimeout(r, 750));
      const fresh = await redetectFromTab();
      if (fresh) {
        jobInfo = fresh;
        if (!tracked) tracked = await isTracked(fresh.url);
        retrying = false;
        break;
      }
    }
    retrying = false;
  });
</script>

<div class="w-[480px] min-h-[440px] h-full bg-[#0f1021] font-sans text-sm text-slate-100 flex flex-col">
  <Header {view} {isWindow} on:change={(e) => (view = e.detail)} />

  {#if view === "pipeline"}
    <Pipeline />

  {:else if retrying}
    <div class="px-4 py-8 text-center flex flex-col items-center gap-3">
      <div class="flex justify-center gap-1">
        {#each [0, 1, 2] as i}
          <span class="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style="animation-delay: {i * 0.15}s"></span>
        {/each}
      </div>
      <p class="text-slate-500 text-xs">Waiting for page to load…</p>
    </div>

  {:else if !jobInfo}
    <div class="px-4 py-8 text-center flex flex-col items-center gap-3">
      <div class="text-2xl">🔍</div>
      <p class="text-slate-400 text-xs leading-relaxed">
        Open a job posting on Workday, Greenhouse,<br/>Lever, LinkedIn, or Indeed.
      </p>
      <button
        on:click={refresh}
        class="text-[11px] text-slate-600 hover:text-slate-400 underline underline-offset-2 transition-colors"
      >Not showing up? Click to refresh</button>
    </div>

  {:else if !checked}
    <div class="px-4 py-5 flex flex-col gap-3">
      {#if fetchError}
        <div class="bg-red-950/40 border border-red-800/50 rounded-xl px-3 py-2 text-xs text-red-400">
          {fetchError}
        </div>
      {/if}
      <!-- Detected job card -->
      <div class="bg-[#1e2038] border border-[#2a2d4a] rounded-xl p-3.5">
        <p class="text-sm leading-tight">
          <span class="font-semibold text-slate-100">{jobInfo.company}</span>
          <span class="text-slate-600 mx-1.5">|</span>
          <span class="text-slate-400">{jobInfo.title}</span>
        </p>
        <p class="text-slate-500 text-xs mt-1">
          {jobInfo.isRemote ? "Remote" : jobInfo.location}
          {#if jobInfo.platform !== "unknown"}
            · <span class="capitalize">{jobInfo.platform}</span>
          {/if}
        </p>
      </div>
      <button
        on:click={checkVisaFit}
        class="w-full py-2.5 rounded-xl text-xs font-semibold bg-[#5865f2] hover:bg-[#4752c4] text-white transition-colors duration-150"
      >
        Check Visa Fit
      </button>
      <button
        on:click={quickTrack}
        disabled={tracked}
        class="w-full py-2 rounded-xl text-xs font-medium transition-colors duration-150 {tracked ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800 cursor-default' : 'bg-[#1e2038] border border-[#2a2d4a] text-slate-400 hover:border-[#5865f2] hover:text-slate-200'}"
      >
        {tracked ? "✓ Already tracked" : "Quick track (no analysis)"}
      </button>
    </div>

  {:else if loading}
    <div class="px-4 py-8 text-center">
      <div class="flex justify-center gap-1 mb-3">
        {#each [0, 1, 2] as i}
          <span
            class="w-1.5 h-1.5 rounded-full bg-[#5865f2] animate-bounce"
            style="animation-delay: {i * 0.15}s"
          ></span>
        {/each}
      </div>
      <p class="text-slate-400 text-xs">Checking {jobInfo.company}…</p>
    </div>

  {:else if result}
    <!-- Company + badge -->
    <div class="px-4 pt-4 pb-3">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="text-sm leading-tight">
            <span class="font-semibold text-slate-100">{result.jobInfo.company}</span>
            <span class="text-slate-600 mx-1.5">|</span>
            <span class="text-slate-400">{result.jobInfo.title}</span>
          </p>
          <p class="text-slate-500 text-xs mt-0.5">
            {result.jobInfo.isRemote ? "Remote" : result.jobInfo.location}
            · <span class="capitalize">{result.jobInfo.platform}</span>
          </p>
        </div>
        <SponsorBadge verdict={result.analysis.verdict} score={result.analysis.sponsorScore} />
      </div>
    </div>

    <!-- H1B chart -->
    <div class="px-4 pb-3">
      <H1BChart records={result.analysis.h1bHistory} />
    </div>

    <!-- Notes -->
    {#if result.analysis.notes}
      <p class="px-4 pb-3 text-xs text-slate-500 leading-relaxed">{result.analysis.notes}</p>
    {/if}

    <!-- Autofill -->
    <div class="px-4 pb-3 border-t border-[#2a2d4a] pt-3">
      <p class="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-2">Autofill work-auth</p>
      <div class="flex gap-1.5 flex-wrap">
        <button
          on:click={() => autofill("authorized")}
          class="px-2 py-1 rounded-lg text-xs bg-[#1e2038] border border-[#2a2d4a] text-slate-300 hover:border-[#5865f2] hover:text-white transition-colors"
        >Authorized?</button>
        <button
          on:click={() => autofill("sponsorship")}
          class="px-2 py-1 rounded-lg text-xs bg-[#1e2038] border border-[#2a2d4a] text-slate-300 hover:border-[#5865f2] hover:text-white transition-colors"
        >Need sponsorship?</button>
        <button
          on:click={() => autofill("visa_type")}
          class="px-2 py-1 rounded-lg text-xs bg-[#1e2038] border border-[#2a2d4a] text-slate-300 hover:border-[#5865f2] hover:text-white transition-colors"
        >Visa type</button>
      </div>
    </div>

    <!-- Track button -->
    <div class="px-4 pb-4">
      <button
        on:click={track}
        disabled={tracked}
        class="w-full py-2 rounded-xl text-xs font-semibold transition-colors duration-150 {tracked ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800 cursor-default' : 'bg-[#5865f2] hover:bg-[#4752c4] text-white'}"
      >
        {tracked ? "✓ Added to pipeline" : "Track this application"}
      </button>
    </div>
  {/if}
</div>
