<script lang="ts">
  import type { CompanyAnalysis } from "../../lib/types";

  export let verdict: CompanyAnalysis["verdict"];
  export let score: number;

  const config = {
    sponsor:  { label: "Sponsors",  bg: "bg-emerald-900/40", text: "text-emerald-400", dot: "bg-emerald-400", border: "border-emerald-800", bar: "bg-emerald-400" },
    unlikely: { label: "Unlikely",  bg: "bg-red-900/40",     text: "text-red-400",     dot: "bg-red-400",     border: "border-red-900",   bar: "bg-red-500"     },
    unknown:  { label: "Unknown",   bg: "bg-slate-800/60",   text: "text-slate-400",   dot: "bg-slate-500",   border: "border-slate-700", bar: "bg-slate-500"   },
  } as const;

  // score values: 5→tier1, 25→tier2, 50→tier3, 70→tier4, 90→tier5
  const TIER_LABEL: Record<number, string> = {
    90: "Strong sponsor history",
    70: "Good sponsor history",
    50: "Limited data",
    25: "Rarely sponsors",
    5:  "No recorded history",
  };

  $: c = config[verdict];
  $: filled = Math.ceil(score / 20); // 5→1, 25→2, 50→3, 70→4, 90→5
  $: label = TIER_LABEL[score] ?? `Score ${score}/100`;
</script>

<div class="flex flex-col items-end gap-1 shrink-0">
  <span class="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-semibold border {c.bg} {c.text} {c.border}">
    <span class="w-1.5 h-1.5 rounded-full {c.dot}"></span>
    {c.label}
  </span>
  <!-- 5-segment strength bar -->
  <div class="flex items-center gap-1">
    <div class="flex gap-0.5">
      {#each [1,2,3,4,5] as seg}
        <div class="w-3.5 h-1.5 rounded-sm {seg <= filled ? c.bar : 'bg-slate-700'}"></div>
      {/each}
    </div>
    <span class="text-[9px] text-slate-500">{score}/100</span>
  </div>
  <span class="text-[9px] text-slate-500 text-right leading-tight max-w-[110px]">{label}</span>
</div>
