<!-- /catalog — Phase 1.5+ stub. Real implementation lifts from design-source/ui_kits/workflow-web/Catalog.jsx. -->
<script lang="ts">
  import LiveSourceBar from '$lib/components/LiveSourceBar.svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import { initialMcpSnapshot } from '$lib/live/project';

  const goals = initialMcpSnapshot.goals;
</script>

<svelte:head>
  <title>Catalog — Workflow</title>
</svelte:head>

<section class="catalog-note">
  <div class="wrap">
    <div class="section-head">
      <div>
        <RitualLabel color="var(--violet-400)">· Catalog lens · live MCP goals ·</RitualLabel>
        <h1>Start from goals. Let branches compete underneath.</h1>
      </div>
      <p>Your chatbot can already browse this catalog directly via the <a href="/connect">MCP connector</a>. Say "browse goals" or "show me research-paper branches" once connected.</p>
    </div>

    <LiveSourceBar label="Goal source" detail={`${goals.length} public goals are visible from the current MCP snapshot; branch leaderboards stay explicit until that feed exists.`} tone="violet" />

    <div class="goal-board">
      {#each goals as goal, index}
        <a class="goal-card" href="/wiki" aria-label={`Inspect ${goal.name} in the live commons`}>
          <span class="goal-card__rank">G{index + 1}</span>
          <h3>{goal.name}</h3>
          <p>{goal.summary}</p>
          <div class="tags">
            {#if goal.tags.length}
              {#each goal.tags.slice(0, 5) as tag}
                <span>{tag}</span>
              {/each}
            {:else}
              <span>untagged</span>
            {/if}
          </div>
          <small>{goal.id} · {goal.visibility}</small>
        </a>
      {/each}
    </div>

    <div class="next-surface">
      <RitualLabel>Not faked yet</RitualLabel>
      <p>The missing layer is the branch leaderboard under each goal: canonical branch, forks, gates, runs, judge score, and remix path. Until that feed exists, the page keeps the gap visible instead of inventing rows.</p>
    </div>
  </div>
</section>

<style>
  .catalog-note { padding-block: 72px; }
  .wrap { max-width: 1120px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); color: var(--fg-2); }
  .section-head { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 0.55fr); gap: 30px; align-items: end; margin-bottom: 18px; }
  h1 { color: var(--fg-1); font-family: var(--font-display); font-size: clamp(42px, 7vw, 68px); font-weight: 400; letter-spacing: 0; line-height: 0.98; margin: 12px 0 0; text-wrap: balance; }
  p { line-height: 1.7; margin: 0 0 14px; font-size: 15px; }
  a { color: var(--ember-600); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .goal-board { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .goal-card { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 8px; color: inherit; display: block; padding: 20px; min-width: 0; text-decoration: none; transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon); }
  .goal-card:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .goal-card__rank { color: var(--ember-600); display: block; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.14em; margin-bottom: 10px; text-transform: uppercase; }
  h3 { color: var(--fg-1); font-family: var(--font-display); font-size: 24px; font-weight: 500; letter-spacing: 0; line-height: 1.12; margin: 0 0 10px; }
  .goal-card p { font-size: 13.5px; line-height: 1.6; margin-bottom: 14px; }
  .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  .tags span { border: 1px solid var(--border-1); border-radius: 4px; color: var(--fg-2); font-family: var(--font-mono); font-size: 10px; padding: 3px 7px; }
  small { color: var(--fg-3); font-family: var(--font-mono); font-size: 10.5px; overflow-wrap: anywhere; }
  .next-surface { background: var(--bg-inset); border: 1px dashed var(--border-2); border-radius: 8px; margin-top: 12px; padding: 18px 20px; }
  .next-surface p { margin: 10px 0 0; }
  @media (max-width: 800px) {
    .section-head,
    .goal-board { grid-template-columns: 1fr; }
  }
</style>
