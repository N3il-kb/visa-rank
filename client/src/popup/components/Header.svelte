<script lang="ts">
  import { createEventDispatcher } from "svelte";

  export let view: "job" | "pipeline";
  export let isWindow = false;

  const dispatch = createEventDispatcher<{ change: "job" | "pipeline" }>();

  const popOut = () => {
    const base = window.location.href.split("?")[0];
    chrome.windows.create({
      url: base + "?mode=window",
      type: "popup",
      width: 520,
      height: 640,
      focused: true,
    });
    window.close();
  };
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

  <div class="flex items-center gap-2">
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

    <!-- Pop-out / back-to-extension -->
    {#if isWindow}
      <button
        on:click={() => window.close()}
        title="Close window"
        class="text-slate-500 hover:text-slate-300 transition-colors p-1 rounded"
      >
        <!-- X icon -->
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
    {:else}
      <button
        on:click={popOut}
        title="Open in floating window"
        class="text-slate-500 hover:text-slate-300 transition-colors p-1 rounded"
      >
        <!-- Pop-out icon -->
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M6 2H2.5A1.5 1.5 0 0 0 1 3.5v8A1.5 1.5 0 0 0 2.5 13h8A1.5 1.5 0 0 0 12 11.5V8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M8 1h5v5M13 1L7 7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    {/if}
  </div>
</header>
