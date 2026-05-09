<script lang="ts">
  import { onMount } from "svelte";
  import type { PipelineEntry, AnalysisResponse } from "../../lib/types";
  import { getPipeline, updateStatus, removeEntry } from "../../lib/pipeline";
  import { analyzeJob } from "../../lib/api";
  import SponsorBadge from "./SponsorBadge.svelte";

  let entries: PipelineEntry[] = [];
  let selected: PipelineEntry | null = null;
  let analysisResult: AnalysisResponse | null = null;
  let analyzing = false;

  onMount(async () => {
    entries = await getPipeline();
  });

  const STATUS_OPTIONS: PipelineEntry["status"][] = [
    "applied", "screening", "interviewing", "offer", "rejected", "ghosted",
  ];

  const verdictDot = (v: string) =>
    v === "sponsor" ? "bg-emerald-400" : v === "unlikely" ? "bg-red-400" : "bg-slate-500";

  const statusColor = (s: PipelineEntry["status"]) => {
    if (s === "offer") return "text-emerald-400";
    if (s === "rejected" || s === "ghosted") return "text-red-400";
    if (s === "interviewing") return "text-[#5865f2]";
    return "text-slate-400";
  };

  const onStatusChange = (id: string, e: Event) => {
    const value = (e.target as HTMLSelectElement).value as PipelineEntry["status"];
    updateStatus(id, value);
    entries = entries.map((en) => (en.id === id ? { ...en, status: value } : en));
    if (selected?.id === id) selected = { ...selected, status: value };
  };

  const checkVisaFit = async () => {
    if (!selected) return;
    analyzing = true;
    analysisResult = await analyzeJob(selected.jobInfo);
    analyzing = false;
  };

  const fmt = (iso: string) =>
    new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

  const openDetail = (entry: PipelineEntry) => {
    selected = entry;
    analysisResult = null;
  };

  const back = () => {
    selected = null;
    analysisResult = null;
  };

  const deleteEntry = async () => {
    if (!selected) return;
    await removeEntry(selected.id);
    entries = entries.filter((e) => e.id !== selected!.id);
    back();
  };

  const quickDelete = async (id: string) => {
    await removeEntry(id);
    entries = entries.filter((e) => e.id !== id);
  };
</script>

{#if selected}
  <!-- Detail view -->
  <div class="flex flex-col">
    <!-- Back bar -->
    <div class="flex items-center justify-between px-4 py-2.5 border-b border-[#2a2d4a]">
      <button
        on:click={back}
        class="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M9 11L5 7l4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        All tracked jobs
      </button>
      <button
        on:click={deleteEntry}
        title="Remove from tracking"
        class="text-slate-600 hover:text-red-400 transition-colors p-1 rounded"
      >
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <path d="M5.5 1.5h4M2 3.5h11M3.5 3.5l.9 9a1 1 0 0 0 1 .9h4.2a1 1 0 0 0 1-.9l.9-9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M6 6.5v4M9 6.5v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
      </button>
    </div>

    <div class="px-4 py-4 flex flex-col gap-3">
      <!-- Header -->
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="text-sm leading-tight">
            <span class="font-semibold text-slate-100">{selected.jobInfo.company}</span>
            <span class="text-slate-600 mx-1.5">|</span>
            <span class="text-slate-400">{selected.jobInfo.title}</span>
          </p>
          <p class="text-slate-500 text-[10px] mt-1">Tracking since {fmt(selected.appliedAt)}</p>
        </div>
        <SponsorBadge verdict={selected.analysis.verdict} score={selected.analysis.sponsorScore} />
      </div>

      <!-- Meta -->
      <div class="bg-[#1e2038] border border-[#2a2d4a] rounded-xl p-3 flex flex-col gap-2 text-xs">
        <div class="flex items-center gap-2 text-slate-400">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1C3.79 1 2 2.79 2 5c0 2.76 4 6.5 4 6.5S10 7.76 10 5c0-2.21-1.79-4-4-4zm0 5.5A1.5 1.5 0 1 1 6 3.5a1.5 1.5 0 0 1 0 3z" fill="currentColor"/></svg>
          <span>{selected.jobInfo.isRemote ? "Remote" : selected.jobInfo.location}</span>
        </div>
        <div class="flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1a5 5 0 1 0 0 10A5 5 0 0 0 6 1zm.5 7.5h-1v-4h1v4zm0-5h-1v-1h1v1z" fill="#5865f2"/></svg>
          <a
            href={selected.jobInfo.url}
            target="_blank"
            rel="noopener noreferrer"
            class="text-[#5865f2] hover:text-indigo-300 truncate transition-colors"
          >Open application →</a>
        </div>
      </div>

      <!-- Status -->
      <div>
        <p class="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-1.5">Status</p>
        <select
          class="w-full text-xs border border-[#2a2d4a] rounded-lg px-2 py-1.5 bg-[#13141f] {statusColor(selected.status)} focus:outline-none focus:border-[#5865f2]"
          value={selected.status}
          on:change={(e) => onStatusChange(selected.id, e)}
        >
          {#each STATUS_OPTIONS as s}
            <option value={s} class="text-slate-100 bg-[#1e2038]">
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          {/each}
        </select>
      </div>

      <!-- Description -->
      {#if selected.jobInfo.description}
        <div>
          <p class="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-1.5">Job Description</p>
          <div class="bg-[#1e2038] border border-[#2a2d4a] rounded-xl p-3 text-xs text-slate-400 leading-relaxed max-h-40 overflow-y-auto">
            {selected.jobInfo.description}
          </div>
        </div>
      {/if}

      <!-- Visa Fit -->
      {#if analyzing}
        <div class="flex justify-center gap-1 py-2">
          {#each [0, 1, 2] as i}
            <span class="w-1.5 h-1.5 rounded-full bg-[#5865f2] animate-bounce" style="animation-delay:{i*0.15}s"></span>
          {/each}
        </div>
      {:else if analysisResult}
        <div class="bg-[#1e2038] border border-[#2a2d4a] rounded-xl p-3">
          <p class="text-[10px] font-medium text-slate-500 uppercase tracking-wide mb-2">Visa Fit Result</p>
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-slate-300">{analysisResult.analysis.verdict === "sponsor" ? "Likely sponsors" : analysisResult.analysis.verdict === "unlikely" ? "Unlikely to sponsor" : "Unknown history"}</span>
            <SponsorBadge verdict={analysisResult.analysis.verdict} score={analysisResult.analysis.sponsorScore} />
          </div>
          {#if analysisResult.analysis.notes}
            <p class="text-xs text-slate-500 leading-relaxed">{analysisResult.analysis.notes}</p>
          {/if}
        </div>
      {:else}
        <button
          on:click={checkVisaFit}
          class="w-full py-2 rounded-xl text-xs font-semibold bg-[#5865f2] hover:bg-[#4752c4] text-white transition-colors"
        >Check Visa Fit</button>
      {/if}
    </div>
  </div>

{:else}
  <!-- List view -->
  <div class="px-4 py-3 flex flex-col gap-2">
    {#if entries.length === 0}
      <div class="py-8 text-center">
        <p class="text-slate-500 text-xs">No jobs tracked yet.</p>
        <p class="text-slate-600 text-[10px] mt-1">Open a job, check visa fit, then track it.</p>
      </div>
    {:else}
      {#each entries as entry}
        <div class="relative bg-[#1e2038] border border-[#2a2d4a] rounded-xl p-3 hover:border-[#5865f2]/50 transition-colors group">
          <!-- clickable body -->
          <button
            on:click={() => openDetail(entry)}
            class="w-full text-left"
          >
            <div class="flex items-center gap-1.5 min-w-0 pr-6 mb-1.5">
              <span class="w-1.5 h-1.5 rounded-full shrink-0 {verdictDot(entry.analysis.verdict)}"></span>
              <p class="text-xs leading-tight truncate whitespace-nowrap">
                <span class="font-medium text-slate-100">{entry.jobInfo.company}</span>
                <span class="text-slate-600 mx-1">|</span>
                <span class="text-slate-400">{entry.jobInfo.title}</span>
              </p>
            </div>
            <div class="flex items-center justify-between pl-3">
              <span class="text-[10px] {statusColor(entry.status)} capitalize">{entry.status}</span>
              <span class="text-[10px] text-slate-600">
                {#if entry.analysis.sponsorScore > 0}H1B {entry.analysis.sponsorScore} · {/if}{fmt(entry.appliedAt)}
              </span>
            </div>
          </button>
          <!-- trash -->
          <button
            on:click|stopPropagation={() => quickDelete(entry.id)}
            title="Remove"
            class="absolute top-2.5 right-2.5 text-slate-700 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
          >
            <svg width="13" height="13" viewBox="0 0 15 15" fill="none">
              <path d="M5.5 1.5h4M2 3.5h11M3.5 3.5l.9 9a1 1 0 0 0 1 .9h4.2a1 1 0 0 0 1-.9l.9-9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M6 6.5v4M9 6.5v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      {/each}
    {/if}
  </div>
{/if}
