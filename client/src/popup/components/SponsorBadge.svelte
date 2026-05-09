<script lang="ts">
  import type { CompanyAnalysis } from "../../lib/types";

  export let verdict: CompanyAnalysis["verdict"];
  export let score: number;

  const config = {
    sponsor:  { label: "Sponsors",  bg: "bg-emerald-900/40", text: "text-emerald-400", dot: "bg-emerald-400", border: "border-emerald-800" },
    unlikely: { label: "Unlikely",  bg: "bg-red-900/40",     text: "text-red-400",     dot: "bg-red-400",     border: "border-red-900"   },
    unknown:  { label: "Unknown",   bg: "bg-slate-800/60",   text: "text-slate-400",   dot: "bg-slate-500",   border: "border-slate-700" },
  } as const;

  $: c = config[verdict];
</script>

<div class="flex flex-col items-end gap-1 shrink-0">
  <span class="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-semibold border {c.bg} {c.text} {c.border}">
    <span class="w-1.5 h-1.5 rounded-full {c.dot}"></span>
    {c.label}
  </span>
  <span class="text-[10px] text-slate-500">{score}/100</span>
</div>
