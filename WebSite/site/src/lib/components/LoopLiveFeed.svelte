<script lang="ts">
  import { onMount } from 'svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import {
    fetchPatchLoopFeed,
    type LoopPatchEvent,
    type LoopPatchRun,
    type LoopStageId,
    type PatchLoopFeed,
    type PatchLoopFeedSource
  } from '$lib/mcp/live';
  import { relativeStamp } from '$lib/live/project';

  type Stage = {
    id: LoopStageId;
    label: string;
  };

  let {
    stages,
    selectedStageId = 'intake',
    onSelectStage = () => {}
  }: {
    stages: Stage[];
    selectedStageId?: LoopStageId;
    onSelectStage?: (stage: LoopStageId) => void;
  } = $props();

  let feed = $state<PatchLoopFeed | null>(null);
  let activeSource = $state<PatchLoopFeedSource>('mcp');
  let loadingSource = $state<PatchLoopFeedSource | null>(null);
  let latestError = $state('');

  const activeRun = $derived.by((): LoopPatchRun | null => {
    if (!feed?.runs.length) return null;
    return feed.runs.find((run) => run.run_id === feed?.activeRunId) ?? feed.runs[0];
  });

  const headline = $derived.by(() => {
    if (activeRun) return activeRun.name || activeRun.run_id;
    if (feed?.events.length) return `Community loop watch: ${(feed.overall ?? 'unknown').toUpperCase()}`;
    return 'Waiting for change_loop_v1';
  });

  const subhead = $derived.by(() => {
    if (activeRun) return `${activeRun.status} · ${relativeStamp(activeRun.started_at)}`;
    if (feed?.events.length) return `${feed.events.length} live stage signal${feed.events.length === 1 ? '' : 's'} · ${relativeStamp(feed.fetchedAt)}`;
    return feed?.live ? 'no visible run yet' : 'feed not visible yet';
  });

  const recentEvents = $derived.by((): LoopPatchEvent[] => {
    return [...(feed?.events ?? [])].slice(-8).reverse();
  });

  async function refresh(source: PatchLoopFeedSource = activeSource) {
    activeSource = source;
    loadingSource = source;
    latestError = '';
    try {
      feed = await fetchPatchLoopFeed(12, source);
      if (!feed.live && feed.warnings.length) {
        latestError = feed.warnings[feed.warnings.length - 1];
      }
    } catch (error) {
      latestError = error instanceof Error ? error.message : 'Loop feed unavailable';
    } finally {
      loadingSource = null;
    }
  }

  onMount(() => {
    void refresh('mcp');
    const timer = window.setInterval(() => void refresh(activeSource), 30000);
    return () => window.clearInterval(timer);
  });

  function eventsFor(stage: LoopStageId): LoopPatchEvent[] {
    return (feed?.events ?? []).filter((event) => event.stage === stage);
  }

  function latestFor(stage: LoopStageId): LoopPatchEvent | null {
    const matches = eventsFor(stage);
    return matches[matches.length - 1] ?? null;
  }

  function stageStatus(stage: LoopStageId): 'waiting' | 'running' | 'done' | 'failed' {
    const latest = latestFor(stage);
    if (!latest) return activeRun?.current_stage === stage ? 'running' : 'waiting';
    const status = latest.status.toLowerCase();
    if (status.includes('fail') || status.includes('error') || status.includes('revert')) return 'failed';
    if (status.includes('complete') || status.includes('success') || status.includes('done') || status.includes('accept')) return 'done';
    return 'running';
  }

  function statusLabel(stage: LoopStageId): string {
    const count = eventsFor(stage).length;
    if (count) return `${count} event${count === 1 ? '' : 's'}`;
    if (activeRun?.current_stage === stage) return 'active run';
    return 'waiting';
  }
</script>

<section class="live-loop" aria-labelledby="live-loop-title">
  <div class="live-loop__head">
    <div>
      <RitualLabel color="var(--signal-live)">· Live patch traffic ·</RitualLabel>
      <h2 id="live-loop-title">Watch patches move through the route.</h2>
      <p>When the operational loop emits run state, this rail lights up from MCP and the community-loop GitHub monitor: intake, queued requests, writer blockage, release workflows, and observation incidents.</p>
    </div>
    <div class="live-loop__actions">
      <button
        class="refresh"
        type="button"
        disabled={loadingSource !== null}
        aria-pressed={activeSource === 'mcp'}
        aria-busy={loadingSource === 'mcp'}
        onclick={() => refresh('mcp')}
      >
        Refresh MCP
      </button>
      <button
        class="refresh"
        type="button"
        disabled={loadingSource !== null}
        aria-pressed={activeSource === 'github'}
        aria-busy={loadingSource === 'github'}
        onclick={() => refresh('github')}
      >
        Refresh GitHub
      </button>
      <span>{loadingSource ? `Refreshing ${loadingSource === 'mcp' ? 'MCP' : 'GitHub'} feed` : feed?.source ?? 'MCP loop feed'}</span>
    </div>
  </div>

  <div class="live-loop__body">
    <div class="run-card">
      <span>Current patch run</span>
      {#if activeRun}
        <strong>{headline}</strong>
        <p><code>{activeRun.run_id}</code> · {subhead}</p>
      {:else if feed?.events.length}
        <strong>{headline}</strong>
        <p><code>{feed.source}</code> · {subhead}</p>
      {:else}
        <strong>{headline}</strong>
        <p><code>{feed?.branchDefId ?? 'fd5c66b1d87d'}</code> · {subhead}</p>
      {/if}
      {#if latestError}
        <p class="feed-error">{latestError}</p>
      {/if}
    </div>

    <div class="live-rail" aria-label="Live loop stages">
      {#each stages as stage, index}
        {@const latest = latestFor(stage.id)}
        <button
          type="button"
          class={`live-stage live-stage--${stageStatus(stage.id)}`}
          class:selected={selectedStageId === stage.id}
          aria-pressed={selectedStageId === stage.id}
          onclick={() => onSelectStage(stage.id)}
        >
          <span>{index + 1}. {stage.label}</span>
          <strong>{latest?.title ?? 'Waiting for live event'}</strong>
          <small>{latest?.detail ?? statusLabel(stage.id)}</small>
        </button>
      {/each}
    </div>

    <div class="event-stream">
      <div class="event-stream__head">
        <span>Recent loop events</span>
        <strong>{feed?.events.length ?? 0}</strong>
      </div>
      {#if recentEvents.length}
        <ol>
          {#each recentEvents as event}
            <li>
              <span>{event.stage}</span>
              <div>
                <strong>{event.title}</strong>
                <p>{event.detail}</p>
                <small>{event.status} · {relativeStamp(event.at)}</small>
              </div>
            </li>
          {/each}
        </ol>
      {:else}
        <p class="empty">Waiting for the first patch event from the operational loop feed.</p>
      {/if}
    </div>
  </div>

  {#if feed?.warnings.length}
    <details class="source-trail">
      <summary>Source trail</summary>
      <ul>
        {#each feed.warnings as warning}
          <li>{warning}</li>
        {/each}
      </ul>
    </details>
  {/if}
</section>

<style>
  .live-loop {
    padding: 22px;
    border: 1px solid rgba(109, 211, 166, 0.22);
    border-radius: 8px;
    background:
      linear-gradient(135deg, rgba(109, 211, 166, 0.055), rgba(138, 99, 206, 0.045)),
      var(--bg-inset);
  }

  .live-loop__head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 18px;
    align-items: start;
    margin-bottom: 18px;
  }

  .live-loop h2 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(28px, 4vw, 42px);
    font-weight: 500;
    line-height: 1.04;
    letter-spacing: 0;
    margin: 8px 0 10px;
  }

  .live-loop p {
    color: var(--fg-2);
    font-size: 14.5px;
    line-height: 1.6;
    margin: 0;
    max-width: 72ch;
  }

  .live-loop__actions {
    display: grid;
    grid-template-columns: repeat(2, max-content);
    gap: 8px;
    justify-items: end;
  }

  .live-loop__actions span {
    grid-column: 1 / -1;
    text-align: right;
  }

  .live-loop__actions span,
  .run-card span,
  .event-stream__head span,
  .event-stream__head strong {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .refresh {
    min-height: 36px;
    padding: 0 13px;
    border: 1px solid rgba(109, 211, 166, 0.34);
    border-radius: 6px;
    background: rgba(109, 211, 166, 0.08);
    color: var(--signal-live);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    text-transform: uppercase;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon);
  }

  .refresh:hover:not(:disabled) {
    border-color: rgba(109, 211, 166, 0.62);
    background: rgba(109, 211, 166, 0.12);
  }

  .refresh[aria-pressed="true"] {
    border-color: rgba(109, 211, 166, 0.72);
    background: rgba(109, 211, 166, 0.14);
  }

  .refresh:disabled {
    cursor: wait;
    opacity: 0.55;
  }

  .live-loop__body {
    display: grid;
    grid-template-columns: minmax(210px, 0.45fr) minmax(0, 1fr) minmax(250px, 0.55fr);
    gap: 12px;
    min-width: 0;
  }

  .run-card,
  .event-stream {
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.16);
    min-width: 0;
  }

  .run-card {
    display: grid;
    align-content: start;
    gap: 9px;
    padding: 15px;
  }

  .run-card strong {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: 24px;
    font-weight: 500;
    line-height: 1.06;
    overflow-wrap: anywhere;
  }

  .run-card code {
    color: var(--violet-200);
    font-family: var(--font-mono);
    font-size: 12px;
    overflow-wrap: anywhere;
  }

  .feed-error {
    color: var(--ember-300) !important;
    font-family: var(--font-mono);
    font-size: 11px !important;
    overflow-wrap: anywhere;
  }

  .live-rail {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 8px;
    min-width: 0;
  }

  .live-stage {
    position: relative;
    display: grid;
    grid-template-rows: auto auto 1fr;
    gap: 6px;
    min-height: 154px;
    min-width: 0;
    padding: 12px;
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: var(--bg-inset);
    color: var(--fg-2);
    cursor: pointer;
    text-align: left;
    transition: transform var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), background var(--dur-fast) var(--ease-standard);
  }

  .live-stage::before {
    content: "";
    width: 9px;
    height: 9px;
    border-radius: 999px;
    background: var(--fg-3);
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.03);
  }

  .live-stage:hover,
  .live-stage.selected {
    transform: translateY(-1px);
    border-color: rgba(204, 120, 92, 0.55);
    background: rgba(204, 120, 92, 0.065);
  }

  .live-stage--running::before {
    background: var(--violet-400);
    box-shadow: 0 0 12px rgba(138, 99, 206, 0.9);
    animation: live-pulse 1.6s ease-in-out infinite;
  }

  .live-stage--done::before {
    background: var(--signal-live);
    box-shadow: 0 0 10px rgba(109, 211, 166, 0.75);
  }

  .live-stage--failed::before {
    background: var(--ember-600);
    box-shadow: 0 0 10px rgba(233, 69, 96, 0.75);
  }

  .live-stage span {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
  }

  .live-stage strong {
    color: var(--fg-1);
    font-size: 13.5px;
    line-height: 1.2;
    overflow-wrap: anywhere;
  }

  .live-stage small {
    color: var(--fg-3);
    font-size: 12px;
    line-height: 1.35;
    overflow-wrap: anywhere;
  }

  .event-stream {
    overflow: hidden;
  }

  .event-stream__head {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 14px;
    border-bottom: 1px solid var(--border-1);
  }

  .event-stream ol {
    display: grid;
    gap: 0;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .event-stream li {
    display: grid;
    grid-template-columns: 72px minmax(0, 1fr);
    gap: 10px;
    padding: 12px 14px;
    border-top: 1px solid var(--border-1);
  }

  .event-stream li:first-child {
    border-top: 0;
  }

  .event-stream li > span,
  .event-stream small {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
  }

  .event-stream strong {
    display: block;
    color: var(--fg-1);
    font-size: 13px;
    line-height: 1.3;
    margin-bottom: 3px;
    overflow-wrap: anywhere;
  }

  .event-stream p {
    color: var(--fg-2);
    font-size: 12.5px;
    line-height: 1.45;
    margin-bottom: 5px;
  }

  .empty {
    color: var(--fg-3) !important;
    padding: 14px;
  }

  .source-trail {
    margin-top: 12px;
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 11px;
  }

  .source-trail summary {
    cursor: pointer;
    width: fit-content;
  }

  .source-trail ul {
    display: grid;
    gap: 4px;
    margin: 8px 0 0;
    padding-left: 18px;
  }

  @keyframes live-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  @media (max-width: 1180px) {
    .live-loop__body {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 860px) {
    .live-loop__head {
      grid-template-columns: 1fr;
    }
    .live-loop__actions {
      justify-items: start;
    }
    .live-loop__actions span {
      text-align: left;
    }
    .live-rail {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 520px) {
    .live-loop {
      padding: 16px;
    }
    .live-loop__actions {
      grid-template-columns: 1fr 1fr;
    }
    .refresh {
      width: 100%;
    }
    .live-rail {
      grid-template-columns: 1fr;
    }
    .live-stage {
      min-height: 118px;
    }
    .event-stream li {
      grid-template-columns: 1fr;
    }
  }
</style>
