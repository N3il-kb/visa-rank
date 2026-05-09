<script lang="ts">
  import type { CompanyAnalysis } from "../../lib/types";

  export let verdict: CompanyAnalysis["verdict"];
  export let score: number;

  const config = {
    sponsor: { label: "Sponsors", bg: "bg-green-100", text: "text-green-700", dot: "bg-green-500" },
    unlikely: { label: "Unlikely", bg: "bg-red-100", text: "text-red-700", dot: "bg-red-500" },
    unknown: { label: "Unknown", bg: "bg-gray-100", text: "text-gray-600", dot: "bg-gray-400" },
  } as const;

  $: c = config[verdict];
</script>

<div class="flex flex-col items-end gap-1 shrink-0">
  <span class="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium {c.bg} {c.text}">
    <span class="w-1.5 h-1.5 rounded-full {c.dot}"></span>
    {c.label}
  </span>
  <span class="text-xs text-gray-400">{score}/100</span>
</div>
