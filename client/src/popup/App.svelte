<script lang="ts">
  import { onMount } from "svelte";
  import type { JobInfo, AnalysisResponse } from "../lib/types";
  import { analyzeJob } from "../lib/api";
  import { addEntry } from "../lib/pipeline";
  import SponsorBadge from "./components/SponsorBadge.svelte";
  import H1BChart from "./components/H1BChart.svelte";
  import Pipeline from "./components/Pipeline.svelte";

  type View = "job" | "pipeline";

  let view: View = "job";
  let jobInfo: JobInfo | null = null;
  let result: AnalysisResponse | null = null;
  let loading = false;
  let error: string | null = null;

  const getJobFromTab = (): Promise<JobInfo | null> =>
    new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "GET_JOB_INFO" }, (resp) => {
        resolve(resp?.payload ?? null);
      });
    });

  const autofill = (fieldType: "authorized" | "sponsorship" | "visa_type") => {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (!tab?.id) return;
      chrome.tabs.sendMessage(tab.id, {
        type: "AUTOFILL_REQUESTED",
        payload: { fieldType },
      });
    });
  };

  const track = async () => {
    if (!result) return;
    await addEntry({
      id: crypto.randomUUID(),
      jobInfo: result.jobInfo,
      analysis: result.analysis,
      appliedAt: new Date().toISOString(),
      status: "applied",
    });
    alert("Tracked in pipeline!");
  };

  onMount(async () => {
    jobInfo = await getJobFromTab();
    if (!jobInfo) return;

    loading = true;
    try {
      result = await analyzeJob(jobInfo);
    } catch (e) {
      error = e instanceof Error ? e.message : "Unknown error";
    } finally {
      loading = false;
    }
  });
</script>

<div class="w-80 min-h-48 bg-white font-sans text-sm text-gray-800">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100">
    <span class="font-bold text-base tracking-tight">Visa Filter</span>
    <div class="flex gap-2 text-xs text-gray-500">
      <button
        class="hover:text-gray-900"
        class:font-semibold={view === "job"}
        on:click={() => (view = "job")}>Job</button
      >
      <span>·</span>
      <button
        class="hover:text-gray-900"
        class:font-semibold={view === "pipeline"}
        on:click={() => (view = "pipeline")}>Pipeline</button
      >
    </div>
  </div>

  {#if view === "pipeline"}
    <Pipeline />
  {:else if !jobInfo}
    <div class="px-4 py-6 text-center text-gray-400 text-xs">
      Open a job posting on Workday, Greenhouse, Lever, or LinkedIn.
    </div>
  {:else if loading}
    <div class="px-4 py-6 text-center text-gray-400 text-xs animate-pulse">
      Looking up {jobInfo.company}…
    </div>
  {:else if error}
    <div class="px-4 py-4 text-xs text-red-600">{error}</div>
  {:else if result}
    <!-- Company header -->
    <div class="px-4 pt-4 pb-2">
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="font-semibold text-base leading-tight">{result.jobInfo.company}</p>
          <p class="text-gray-500 text-xs mt-0.5">{result.jobInfo.title}</p>
          <p class="text-gray-400 text-xs mt-0.5">
            {result.jobInfo.isRemote ? "Remote" : result.jobInfo.location}
            · {result.jobInfo.platform}
          </p>
        </div>
        <SponsorBadge verdict={result.analysis.verdict} score={result.analysis.sponsorScore} />
      </div>
    </div>

    <!-- H1B history chart -->
    <div class="px-4 pb-2">
      <H1BChart records={result.analysis.h1bHistory} />
    </div>

    <!-- Notes -->
    {#if result.analysis.notes}
      <p class="px-4 pb-3 text-xs text-gray-500 leading-relaxed">{result.analysis.notes}</p>
    {/if}

    <!-- Autofill shortcuts -->
    <div class="px-4 pb-3 border-t border-gray-100 pt-3">
      <p class="text-xs font-medium text-gray-600 mb-2">Autofill work-auth questions</p>
      <div class="flex gap-2 flex-wrap">
        <button
          on:click={() => autofill("authorized")}
          class="px-2 py-1 rounded text-xs bg-gray-100 hover:bg-gray-200"
        >Work authorized?</button>
        <button
          on:click={() => autofill("sponsorship")}
          class="px-2 py-1 rounded text-xs bg-gray-100 hover:bg-gray-200"
        >Sponsorship needed?</button>
        <button
          on:click={() => autofill("visa_type")}
          class="px-2 py-1 rounded text-xs bg-gray-100 hover:bg-gray-200"
        >Visa type</button>
      </div>
    </div>

    <!-- Track button -->
    <div class="px-4 pb-4">
      <button
        on:click={track}
        class="w-full py-1.5 rounded-lg text-xs font-medium bg-gray-900 text-white hover:bg-gray-700 transition-colors"
      >Track this application</button>
    </div>
  {/if}
</div>
