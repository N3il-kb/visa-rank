<script lang="ts">
  import { onMount } from "svelte";
  import type { PipelineEntry } from "../../lib/types";
  import { getPipeline, updateStatus } from "../../lib/pipeline";

  let entries: PipelineEntry[] = [];

  onMount(async () => {
    entries = await getPipeline();
  });

  const handleStatusChange = async (id: string, status: PipelineEntry["status"]) => {
    await updateStatus(id, status);
    entries = entries.map((e) => (e.id === id ? { ...e, status } : e));
  };

  const STATUS_OPTIONS: PipelineEntry["status"][] = [
    "applied", "screening", "interviewing", "offer", "rejected", "ghosted",
  ];

  const verdictDot = (verdict: string) =>
    verdict === "sponsor" ? "bg-emerald-400" : verdict === "unlikely" ? "bg-red-400" : "bg-slate-500";

  const statusColor = (status: PipelineEntry["status"]) => {
    if (status === "offer") return "text-emerald-400";
    if (status === "rejected" || status === "ghosted") return "text-red-400";
    if (status === "interviewing") return "text-[#5865f2]";
    return "text-slate-400";
  };

  const onStatusChange = (id: string, e: Event) => {
    const value = (e.target as HTMLSelectElement).value as PipelineEntry["status"];
    handleStatusChange(id, value);
  };
</script>

<div class="px-4 py-3 flex flex-col gap-2.5">
  {#if entries.length === 0}
    <div class="py-8 text-center">
      <p class="text-slate-500 text-xs">No applications tracked yet.</p>
      <p class="text-slate-600 text-[10px] mt-1">Check a job and click "Track this application".</p>
    </div>
  {:else}
    {#each entries as entry}
      <div class="bg-[#1e2038] border border-[#2a2d4a] rounded-xl p-3">
        <div class="flex justify-between items-start mb-2">
          <div class="flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full shrink-0 {verdictDot(entry.analysis.verdict)}"></span>
            <div>
              <p class="font-medium text-xs text-slate-100 leading-tight">{entry.jobInfo.company}</p>
              <p class="text-slate-500 text-[10px]">{entry.jobInfo.title}</p>
            </div>
          </div>
          <span class="text-[10px] font-semibold text-slate-500 shrink-0">
            {entry.analysis.sponsorScore}/100
          </span>
        </div>
        <select
          class="w-full text-[10px] border border-[#2a2d4a] rounded-lg px-2 py-1 bg-[#13141f] {statusColor(entry.status)} focus:outline-none focus:border-[#5865f2]"
          value={entry.status}
          on:change={(e) => onStatusChange(entry.id, e)}
        >
          {#each STATUS_OPTIONS as s}
            <option value={s} class="text-slate-100 bg-[#1e2038]">{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          {/each}
        </select>
      </div>
    {/each}
  {/if}
</div>
