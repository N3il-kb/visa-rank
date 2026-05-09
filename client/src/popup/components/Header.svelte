<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let view: "job" | "pipeline";

  const dispatch = createEventDispatcher<{ change: "job" | "pipeline" }>();
</script>

<header class="flex items-center justify-between px-4 py-3 bg-[#171829] border-b border-[#2a2d4a]">
  <!-- Logo + title -->
  <div class="flex items-center gap-2.5">
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M11 2L3 5.8V11C3 15.55 6.48 19.76 11 21C15.52 19.76 19 15.55 19 11V5.8L11 2Z" fill="#5865f2"/>
      <path d="M8 11L10 13L14.5 8.5" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div class="flex flex-col leading-none">
      <span class="font-bold text-sm text-slate-100 tracking-tight">Visa Rank</span>
      <span class="text-[9px] text-slate-500 tracking-wide uppercase mt-0.5">Sponsorship Intel</span>
    </div>
  </div>

  <!-- Tab switcher -->
  <nav class="flex items-center gap-0.5 bg-[#0f1021] rounded-lg p-0.5">
    <button
      class="px-3 py-1 rounded-md text-xs font-medium transition-all duration-150 {view === 'job' ? 'bg-[#5865f2] text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'}"
      on:click={() => dispatch("change", "job")}
    >Job</button>
    <button
      class="px-3 py-1 rounded-md text-xs font-medium transition-all duration-150 {view === 'pipeline' ? 'bg-[#5865f2] text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'}"
      on:click={() => dispatch("change", "pipeline")}
    >Tracking</button>
  </nav>
</header>
