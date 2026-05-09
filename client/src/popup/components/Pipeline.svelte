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

  const verdictColor = (verdict: string) =>
    verdict === "sponsor" ? "text-green-600" : verdict === "unlikely" ? "text-red-500" : "text-gray-400";
</script>

<div class="px-4 py-3">
  {#if entries.length === 0}
    <p class="text-xs text-gray-400 text-center py-4">No applications tracked yet.</p>
  {:else}
    <div class="flex flex-col gap-3">
      {#each entries as entry}
        <div class="border border-gray-100 rounded-lg p-3">
          <div class="flex justify-between items-start mb-1">
            <div>
              <p class="font-medium text-xs leading-tight">{entry.jobInfo.company}</p>
              <p class="text-gray-400 text-[10px]">{entry.jobInfo.title}</p>
            </div>
            <span class="text-[10px] font-medium {verdictColor(entry.analysis.verdict)}">
              {entry.analysis.sponsorScore}/100
            </span>
          </div>
          <select
            class="w-full text-[10px] border border-gray-200 rounded px-1 py-0.5 mt-1 bg-white"
            value={entry.status}
            on:change={(e) =>
              handleStatusChange(entry.id, (e.target as HTMLSelectElement).value as PipelineEntry["status"])}
          >
            {#each STATUS_OPTIONS as s}
              <option value={s}>{s}</option>
            {/each}
          </select>
        </div>
      {/each}
    </div>
  {/if}
</div>
