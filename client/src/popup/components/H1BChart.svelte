<script lang="ts">
  import type { H1BRecord } from "../../lib/types";

  export let records: H1BRecord[];

  $: sorted = [...records].sort((a, b) => a.year - b.year).slice(-5);
  $: maxApproved = Math.max(...sorted.map((r) => r.approved), 1);
</script>

{#if sorted.length === 0}
  <p class="text-xs text-gray-400 py-1">No USCIS filing history found.</p>
{:else}
  <div>
    <p class="text-xs font-medium text-gray-500 mb-1">H1B approvals (USCIS)</p>
    <div class="flex items-end gap-1 h-12">
      {#each sorted as r}
        <div class="flex flex-col items-center flex-1 gap-0.5">
          <div
            class="w-full bg-green-500 rounded-sm"
            style="height: {Math.round((r.approved / maxApproved) * 40)}px"
            title="{r.year}: {r.approved} approved, {r.denied} denied"
          ></div>
          <span class="text-[9px] text-gray-400">{r.year}</span>
        </div>
      {/each}
    </div>
  </div>
{/if}
