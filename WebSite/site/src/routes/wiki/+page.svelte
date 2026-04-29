<!--
  /wiki — live readout from tinyassets.io/mcp.
  Renders the baked snapshot immediately, then re-renders with live data
  once the browser fetch lands. If the live fetch fails, the snapshot stays.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import baked from '$lib/content/mcp-snapshot.json';
  import { fetchLive, liveToSnapshotShape } from '$lib/mcp/live';
  import type { Snapshot } from '$lib/mcp/types';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import StatusPill from '$lib/components/Primitives/StatusPill.svelte';
  import LiveBadge from '$lib/components/LiveBadge.svelte';

  let snapshot: Snapshot = $state(baked as unknown as Snapshot);
  let loading = $state(false);
  let liveError = $state<string | null>(null);

  onMount(async () => {
    loading = true;
    try {
      const live = await fetchLive();
      snapshot = liveToSnapshotShape(live, baked as unknown as Snapshot);
      liveError = null;
    } catch (e: any) {
      liveError = e?.message ?? String(e);
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Live wiki — Workflow</title>
  <meta name="description" content="Live readout of the community wiki at tinyassets.io/mcp." />
</svelte:head>

<section class="hero">
  <div class="container">
    <div class="head__row">
      <RitualLabel color="var(--ember-500)">· {snapshot.source} ·</RitualLabel>
      <LiveBadge fetchedAt={snapshot.fetched_at} source={snapshot.source} {loading} />
    </div>
    <h1>The wiki is the loop.</h1>
    <p class="lead">
      Real users (and their chatbots) file patches, draft concepts, and write builder notes. The community accumulates here. This page reads live from <code>tinyassets.io/mcp</code> on every load.
    </p>
    {#if liveError}
      <p class="error">Live fetch failed: <code>{liveError}</code> — showing baked snapshot.</p>
    {/if}
    <div class="stats">
      <div class="stat"><span class="stat__num">{snapshot.stats.wiki_promoted}</span><span class="stat__label">Promoted pages</span></div>
      <div class="stat"><span class="stat__num">{snapshot.stats.wiki_drafts}</span><span class="stat__label">Drafts</span></div>
      <div class="stat"><span class="stat__num">{snapshot.stats.goals}</span><span class="stat__label">Goals</span></div>
      <div class="stat"><span class="stat__num">{snapshot.stats.universes}</span><span class="stat__label">Universes</span></div>
    </div>
  </div>
</section>

<section class="goals">
  <div class="container">
    <RitualLabel color="var(--violet-400)">· Goals · what the community is pursuing ·</RitualLabel>
    <h2>{snapshot.goals.length} active goals.</h2>
    <div class="goals__grid">
      {#each snapshot.goals as g (g.id)}
        <article class="goal">
          <header class="goal__head">
            <code class="goal__id">{g.id}</code>
            <h3 class="goal__name">{g.name}</h3>
          </header>
          <p class="goal__summary">{g.summary}</p>
          {#if g.tags.length}
            <div class="goal__tags">{#each g.tags as t}<span class="tag">{t}</span>{/each}</div>
          {/if}
        </article>
      {/each}
    </div>
  </div>
</section>

<section class="universes">
  <div class="container">
    <RitualLabel>· Universes · live daemon work ·</RitualLabel>
    <h2>{snapshot.universes.length} universes.</h2>
    <div class="uni__list">
      {#each snapshot.universes as u (u.id)}
        <article class="uni">
          <div class="uni__name"><code>{u.id}</code></div>
          <div class="uni__phase">
            <StatusPill kind={u.phase === 'paused' ? 'idle' : u.phase === 'idle-no-premise' ? 'self' : 'live'}>
              {u.phase}
            </StatusPill>
          </div>
          <div class="uni__words">{u.word_count.toLocaleString()} words</div>
          <div class="uni__when">{u.last_activity_at ? `last ${u.last_activity_at}` : 'no activity yet'}</div>
        </article>
      {/each}
    </div>
  </div>
</section>

<section class="bugs">
  <div class="container">
    <RitualLabel color="var(--ember-500)">· Bugs · {snapshot.wiki.bugs.length} filed · this is what users said wasn't working ·</RitualLabel>
    <h2>Filed by chatbot-users via the wiki.</h2>
    <p class="bugs__lead">Each bug is a <code>patch_request</code> waiting for a daemon to claim it. Iteration is constant.</p>
    <ol class="bugs__list">
      {#each snapshot.wiki.bugs as b (b.id)}
        <li class="bug"><code class="bug__id">{b.id}</code><span class="bug__title">{b.title}</span></li>
      {/each}
    </ol>
  </div>
</section>

<section class="docs">
  <div class="container docs__grid">
    <div class="col">
      <RitualLabel color="var(--violet-400)">· Concepts ·</RitualLabel>
      <ul class="doclist">
        {#each snapshot.wiki.concepts as p (p.slug)}<li><span class="doc__type">concept</span><span>{p.title}</span></li>{/each}
      </ul>
    </div>
    <div class="col">
      <RitualLabel>· Builder notes ·</RitualLabel>
      <ul class="doclist">
        {#each snapshot.wiki.notes as p (p.slug)}<li><span class="doc__type">note</span><span>{p.title}</span></li>{/each}
      </ul>
    </div>
  </div>
</section>

<section class="docs">
  <div class="container">
    <RitualLabel color="var(--ember-500)">· Plans · {snapshot.wiki.plans.length} active ·</RitualLabel>
    <ul class="doclist doclist--plans">
      {#each snapshot.wiki.plans as p (p.slug)}<li><span class="doc__type">plan</span><span>{p.title}</span></li>{/each}
    </ul>
  </div>
</section>

<section class="docs">
  <div class="container">
    <RitualLabel>· Drafts · {snapshot.wiki.drafts.length} in progress ·</RitualLabel>
    <ul class="doclist doclist--drafts">
      {#each snapshot.wiki.drafts as p (p.slug)}<li><span class="doc__type">draft</span><span>{p.title}</span></li>{/each}
    </ul>
  </div>
</section>

<style>
  .hero, .goals, .universes, .bugs, .docs { padding-block: 56px; border-top: 1px solid var(--border-1); }
  .hero { padding-top: 80px; border-top: none; }
  .head__row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
  h1 { font-family: var(--font-display); font-size: clamp(48px, 8vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.95; margin: 14px 0 18px; }
  h2 { font-family: var(--font-display); font-size: clamp(24px, 4vw, 32px); font-weight: 500; letter-spacing: -0.02em; margin: 14px 0 18px; }
  .lead { font-size: 16px; color: var(--fg-2); line-height: 1.6; margin: 0 0 16px; max-width: 64ch; }
  .lead code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 13px; color: var(--violet-200); }
  .error { font-size: 13px; color: var(--signal-error); margin: 0 0 16px; font-family: var(--font-mono); }
  .error code { color: var(--signal-error); }
  .stats { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 12px; }
  .stat { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 10px; padding: 14px 20px; min-width: 110px; }
  .stat__num { display: block; font-family: var(--font-display); font-size: 36px; font-weight: 500; color: var(--ember-600); line-height: 1; }
  .stat__label { display: block; font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.14em; margin-top: 6px; }
  .goals__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 800px) { .goals__grid { grid-template-columns: 1fr; } }
  .goal { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 12px; padding: 20px 22px; }
  .goal__head { margin-bottom: 10px; }
  .goal__id { font-family: var(--font-mono); font-size: 11px; color: var(--violet-200); }
  .goal__name { font-family: var(--font-display); font-size: 18px; font-weight: 500; letter-spacing: -0.01em; color: var(--fg-1); margin: 4px 0 0; line-height: 1.3; }
  .goal__summary { font-size: 13px; color: var(--fg-2); line-height: 1.55; margin: 8px 0 12px; }
  .goal__tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { font-family: var(--font-mono); font-size: 10px; color: var(--fg-3); background: rgba(255,255,255,0.04); padding: 2px 7px; border-radius: 4px; letter-spacing: 0.05em; }
  .uni__list { display: flex; flex-direction: column; gap: 10px; }
  .uni { display: grid; grid-template-columns: 160px 140px 140px 1fr; gap: 16px; align-items: center; background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 10px; padding: 12px 18px; }
  @media (max-width: 800px) { .uni { grid-template-columns: 1fr; gap: 8px; } }
  .uni__name code { font-family: var(--font-mono); font-size: 14px; color: var(--fg-1); font-weight: 600; }
  .uni__words { font-family: var(--font-mono); font-size: 12px; color: var(--fg-2); }
  .uni__when { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); }
  .bugs__lead { font-size: 14px; color: var(--fg-2); margin: 0 0 24px; max-width: 60ch; line-height: 1.55; }
  .bugs__lead code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 12px; color: var(--violet-200); }
  .bugs__list { list-style: none; padding: 0; margin: 0; column-count: 2; column-gap: 20px; }
  @media (max-width: 800px) { .bugs__list { column-count: 1; } }
  .bug { display: grid; grid-template-columns: 80px 1fr; gap: 12px; align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--border-1); break-inside: avoid; font-size: 13px; line-height: 1.5; color: var(--fg-2); }
  .bug__id { font-family: var(--font-mono); font-size: 11px; color: var(--ember-600); background: rgba(233,69,96,0.06); padding: 2px 6px; border-radius: 4px; letter-spacing: 0.06em; text-align: center; }
  .docs__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
  @media (max-width: 700px) { .docs__grid { grid-template-columns: 1fr; gap: 16px; } }
  .doclist { list-style: none; padding: 0; margin: 12px 0 0; }
  .doclist li { display: grid; grid-template-columns: 80px 1fr; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-1); font-size: 13.5px; line-height: 1.5; color: var(--fg-2); }
  .doclist li:last-child { border-bottom: none; }
  .doc__type { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--violet-400); background: rgba(138,99,206,0.08); padding: 3px 6px; border-radius: 4px; text-align: center; }
  .doclist--plans .doc__type { color: var(--ember-500); background: rgba(233,69,96,0.06); }
  .doclist--drafts .doc__type { color: var(--signal-idle); background: rgba(217,168,74,0.08); }
</style>
