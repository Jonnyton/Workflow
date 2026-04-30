<!--
  /graph — Obsidian-style live constellation.
  Live readout from tinyassets.io/mcp. Renders the baked snapshot
  immediately, then re-runs the layout with live data when fetch lands.

  Layout: force-directed (springs along real edges, repulsion between
  every pair, weak centering force). Real edges come from the snapshot
  which was crawled from page bodies' [[wiki-links]] + frontmatter sources.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import baked from '$lib/content/mcp-snapshot.json';
  import { fetchLive, liveToSnapshotShape } from '$lib/mcp/live';
  import type { Snapshot, Edge } from '$lib/mcp/types';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import LiveBadge from '$lib/components/LiveBadge.svelte';

  let snapshot: Snapshot = $state(baked as unknown as Snapshot);
  let loading = $state(false);
  let liveError = $state<string | null>(null);

  type NodeType = 'goal' | 'universe' | 'bug' | 'concept' | 'note' | 'plan' | 'draft';
  type SimNode = {
    id: string; type: NodeType; title: string; summary?: string;
    x: number; y: number; vx: number; vy: number; r: number;
  };

  const W = 1100, H = 720;
  const TYPE_META: Record<NodeType, { color: string; label: string; r: number }> = {
    goal: { color: 'var(--ember-600)', label: 'Goal', r: 14 },
    universe: { color: 'var(--signal-live)', label: 'Universe', r: 12 },
    bug: { color: 'var(--ember-500)', label: 'Bug', r: 6 },
    concept: { color: 'var(--violet-200)', label: 'Concept', r: 8 },
    note: { color: 'var(--violet-400)', label: 'Note', r: 8 },
    plan: { color: 'var(--ember-300)', label: 'Plan', r: 9 },
    draft: { color: 'var(--signal-idle)', label: 'Draft', r: 7 }
  };

  // Build node set from snapshot.
  function buildNodes(s: Snapshot): SimNode[] {
    const nodes: SimNode[] = [];
    const cx = W / 2, cy = H / 2;
    let i = 0;
    function seed(): { x: number; y: number } {
      // Deterministic but spread-out seed positions.
      const angle = i * 2.39996;
      const radius = 80 + Math.sqrt(i) * 18;
      i++;
      return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
    }
    function push(id: string, type: NodeType, title: string, summary?: string) {
      const meta = TYPE_META[type];
      const { x, y } = seed();
      nodes.push({ id, type, title, summary, x, y, vx: 0, vy: 0, r: meta.r });
    }
    for (const g of s.goals ?? []) push(`goal:${g.id}`, 'goal', g.name, g.summary);
    for (const u of s.universes ?? []) push(`universe:${u.id}`, 'universe', u.id, `${u.phase} · ${u.word_count.toLocaleString()} words`);
    for (const b of s.wiki?.bugs ?? []) push(`bug:${b.id}`, 'bug', `${b.id} ${b.title}`, b.title);
    for (const p of s.wiki?.plans ?? []) push(`plan:${slugId(p.slug)}`, 'plan', p.title, p.title);
    for (const c of s.wiki?.concepts ?? []) push(`concept:${slugId(c.slug)}`, 'concept', c.title, c.title);
    for (const n of s.wiki?.notes ?? []) push(`note:${slugId(n.slug)}`, 'note', n.title, n.title);
    for (const d of s.wiki?.drafts ?? []) push(`draft:${d.slug}`, 'draft', d.title, d.title);
    return nodes;
  }
  function slugId(path: string): string {
    return path.split('/').pop()?.replace(/\.md$/, '') ?? path;
  }

  // Build edge list — use real snapshot edges if available, otherwise fall back
  // to a minimal goal→bug + plan→bug heuristic so the graph still has shape.
  function buildEdges(s: Snapshot, nodes: SimNode[]): Edge[] {
    const ids = new Set(nodes.map((n) => n.id));
    const real = (s.edges ?? []).filter((e) => ids.has(e.from) && ids.has(e.to));
    if (real.length > 0) return real;
    // Heuristic fallback — patch_loop goal binds to all bugs, etc.
    const fallback: Edge[] = [];
    const patchGoal = nodes.find((n) => n.id.startsWith('goal:') && /patch/i.test(n.title));
    if (patchGoal) {
      for (const n of nodes) if (n.type === 'bug') fallback.push({ from: patchGoal.id, to: n.id });
    }
    return fallback;
  }

  // Force-directed simulation. Run synchronously for ~250 iterations on data change.
  function runSimulation(nodes: SimNode[], edges: Edge[]): SimNode[] {
    if (!nodes.length) return nodes;
    const idIndex = new Map(nodes.map((n, i) => [n.id, i]));
    const linked = edges.flatMap((e) => {
      const a = idIndex.get(e.from);
      const b = idIndex.get(e.to);
      return a !== undefined && b !== undefined ? [[a, b]] : [];
    });
    const cx = W / 2, cy = H / 2;
    const REPULSION = 1800;     // pairwise inverse-square push
    const SPRING_K = 0.022;     // edge spring coefficient
    const SPRING_LEN = 110;     // ideal edge length
    const CENTER_K = 0.0035;    // pull toward center
    const DAMPING = 0.78;
    const MIN_DIST = 12;        // avoid singularities
    const ITERATIONS = 320;

    for (let iter = 0; iter < ITERATIONS; iter++) {
      // Pairwise repulsion (O(n²) — fine for hundreds of nodes).
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = Math.max(dx * dx + dy * dy, MIN_DIST * MIN_DIST);
          const d = Math.sqrt(d2);
          const f = REPULSION / d2;
          const fx = (dx / d) * f;
          const fy = (dy / d) * f;
          a.vx += fx; a.vy += fy;
          b.vx -= fx; b.vy -= fy;
        }
        // Centering.
        a.vx += (cx - a.x) * CENTER_K;
        a.vy += (cy - a.y) * CENTER_K;
      }
      // Edge springs.
      for (const [ai, bi] of linked) {
        const a = nodes[ai], b = nodes[bi];
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (d - SPRING_LEN) * SPRING_K;
        const fx = (dx / d) * f;
        const fy = (dy / d) * f;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }
      // Integrate.
      for (const n of nodes) {
        n.vx *= DAMPING; n.vy *= DAMPING;
        n.x += n.vx; n.y += n.vy;
        // Soft bounds.
        n.x = Math.max(20, Math.min(W - 20, n.x));
        n.y = Math.max(20, Math.min(H - 20, n.y));
      }
    }
    return nodes;
  }

  let nodes = $state<SimNode[]>([]);
  let edges = $state<Edge[]>([]);
  const nodeById = $derived(new Map(nodes.map((n) => [n.id, n])));
  const orphanCount = $derived.by(() => {
    if (!nodes.length) return 0;
    const connected = new Set<string>();
    for (const e of edges) { connected.add(e.from); connected.add(e.to); }
    return nodes.filter((n) => !connected.has(n.id)).length;
  });

  // Recompute layout whenever the snapshot changes.
  $effect(() => {
    const fresh = buildNodes(snapshot);
    const e = buildEdges(snapshot, fresh);
    nodes = runSimulation(fresh, e);
    edges = e;
  });

  let active = $state<string | null>(null);
  let pinned = $state<string | null>(null);
  const visible = $derived(pinned ?? active);
  const visibleNode = $derived(visible ? nodeById.get(visible) : null);
  const highlit = $derived.by(() => {
    if (!visible) return new Set<string>();
    const set = new Set<string>([visible]);
    for (const e of edges) {
      if (e.from === visible) set.add(e.to);
      if (e.to === visible) set.add(e.from);
    }
    return set;
  });

  function handleClick(id: string, ev: MouseEvent) {
    ev.stopPropagation();
    pinned = pinned === id ? null : id;
  }

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
  <title>Graph — Workflow</title>
  <meta name="description" content="Live Obsidian-style view of the project — every goal, wiki page, and the threads connecting them." />
</svelte:head>

<section class="hero">
  <div class="container">
    <div class="head__row">
      <RitualLabel color="var(--violet-400)">· Live constellation · {snapshot.source} ·</RitualLabel>
      <LiveBadge fetchedAt={snapshot.fetched_at} source={snapshot.source} {loading} />
    </div>
    <h1>Everything, wired up.</h1>
    <p class="lead">
      Every goal, every wiki page, every active universe — and the real connections between them, parsed from <code>[[wiki-links]]</code>, bare <code>BUG-NNN</code> tokens, and frontmatter <code>related:</code> / <code>sources:</code> fields in page bodies. Hover a node to highlight its 1-hop neighbors. Click to pin. Orphans are honestly orphans — if a node has no edges, the wiki page hasn't been cross-referenced yet, and that's a thread waiting to be filed.
    </p>
    {#if liveError}
      <p class="error">Live fetch failed: <code>{liveError}</code> — showing baked snapshot.</p>
    {/if}
    <div class="legend">
      {#each Object.entries(TYPE_META) as [t, m]}
        <div class="legend__item">
          <span class="legend__dot" style:background={m.color}></span>
          <span class="legend__label">{m.label}</span>
        </div>
      {/each}
      <div class="legend__item legend__counts">
        <span>{nodes.length} nodes · {edges.length} edges · {orphanCount} orphan{orphanCount === 1 ? '' : 's'}</span>
      </div>
    </div>
  </div>
</section>

<section class="canvas-wrap">
  <div class="canvas">
    <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" class="graph" onclick={() => (pinned = null)} role="presentation">
      <g class="edges">
        {#each edges as e (e.from + '|' + e.to + '|' + e.kind)}
          {@const a = nodeById.get(e.from)}
          {@const b = nodeById.get(e.to)}
          {#if a && b}
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} class="edge" class:edge--hot={visible && (highlit.has(e.from) && highlit.has(e.to))}/>
          {/if}
        {/each}
      </g>
      <g class="nodes">
        {#each nodes as n (n.id)}
          <g
            class="node node--{n.type}"
            class:dim={visible && !highlit.has(n.id)}
            class:hot={visible && highlit.has(n.id)}
            class:pinned={pinned === n.id}
            transform="translate({n.x},{n.y})"
            onmouseenter={() => (active = n.id)}
            onmouseleave={() => (active = null)}
            onclick={(e) => handleClick(n.id, e)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(n.id, e as unknown as MouseEvent); } }}
            role="button"
            tabindex="0"
            aria-label={n.title}
          >
            <circle r={n.r} class="node__halo" />
            <circle r={n.r} class="node__core" style:fill={TYPE_META[n.type].color} />
          </g>
        {/each}
      </g>
    </svg>
    <aside class="panel">
      {#if visibleNode}
        <RitualLabel color={TYPE_META[visibleNode.type].color}>· {TYPE_META[visibleNode.type].label} ·</RitualLabel>
        <h3 class="panel__title">{visibleNode.title}</h3>
        {#if visibleNode.summary && visibleNode.summary !== visibleNode.title}
          <p class="panel__summary">{visibleNode.summary}</p>
        {/if}
        <code class="panel__id">{visibleNode.id}</code>
        {#if pinned}<button class="panel__close" onclick={(e) => { e.stopPropagation(); pinned = null; }}>Unpin</button>{/if}
      {:else}
        <RitualLabel>· Hover a node ·</RitualLabel>
        <p class="panel__empty">
          Force-directed layout — connected nodes pull together, unrelated nodes push apart. Edges are real <code>[[wiki-link]]</code> + frontmatter <code>sources:</code> references parsed from page bodies.
        </p>
      {/if}
    </aside>
  </div>
</section>

<style>
  .hero { padding-top: 80px; padding-bottom: 32px; }
  .head__row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
  h1 { font-family: var(--font-display); font-size: clamp(48px, 8vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.95; margin: 14px 0 18px; }
  .lead { font-size: 16px; color: var(--fg-2); line-height: 1.6; max-width: 64ch; margin: 0 0 18px; }
  .lead code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 13px; color: var(--violet-200); }
  .error { font-size: 13px; color: var(--signal-error); margin: 0 0 16px; font-family: var(--font-mono); }
  .error code { color: var(--signal-error); }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
  .legend__item { display: flex; align-items: center; gap: 6px; }
  .legend__dot { width: 10px; height: 10px; border-radius: 50%; }
  .legend__label { font-family: var(--font-mono); font-size: 11px; color: var(--fg-2); text-transform: uppercase; letter-spacing: 0.14em; }
  .legend__counts { margin-left: auto; font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); }

  .canvas-wrap { padding-block: 0 56px; }
  .canvas { max-width: 1240px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); display: grid; grid-template-columns: 1fr 280px; gap: 16px; align-items: stretch; }
  @media (max-width: 900px) { .canvas { grid-template-columns: 1fr; } }
  .graph { display: block; width: 100%; height: auto; background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; cursor: default; }

  .panel { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; padding: 18px 20px; align-self: flex-start; position: sticky; top: 88px; }
  .panel__title { font-family: var(--font-display); font-size: 18px; font-weight: 500; line-height: 1.3; color: var(--fg-1); margin: 8px 0 10px; }
  .panel__summary { font-size: 13px; color: var(--fg-2); line-height: 1.55; margin: 0 0 12px; }
  .panel__id { font-family: var(--font-mono); font-size: 11px; color: var(--violet-200); background: var(--bg-inset); padding: 3px 7px; border-radius: 4px; word-break: break-all; }
  .panel__empty { font-size: 13px; color: var(--fg-2); line-height: 1.55; margin: 8px 0 0; }
  .panel__empty code { background: rgba(255,255,255,0.06); padding: 1px 4px; border-radius: 3px; font-size: 12px; color: var(--violet-200); }
  .panel__close { margin-top: 14px; background: transparent; border: 1px solid var(--border-1); color: var(--fg-2); font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; padding: 6px 10px; border-radius: 6px; cursor: pointer; }
  .panel__close:hover { color: var(--fg-1); border-color: var(--border-2); }

  .node { cursor: pointer; }
  .node__halo { fill: transparent; stroke: currentColor; stroke-opacity: 0; transition: stroke-opacity var(--dur-fast) var(--ease-standard); }
  .node__core { transition: filter var(--dur-fast), opacity var(--dur-base); }
  .node:hover .node__halo { stroke-opacity: 0.5; stroke-width: 2; }
  .node:hover .node__core { filter: drop-shadow(0 0 4px currentColor); }
  .node.dim .node__core { opacity: 0.18; }
  .node.hot .node__halo { stroke-opacity: 0.6; stroke-width: 2; }
  .node.hot .node__core { filter: drop-shadow(0 0 6px currentColor); }
  .node.pinned .node__halo { stroke-opacity: 0.9; stroke-width: 3; stroke: var(--ember-600); }

  .node--goal { color: var(--ember-600); }
  .node--universe { color: var(--signal-live); }
  .node--bug { color: var(--ember-500); }
  .node--concept { color: var(--violet-200); }
  .node--note { color: var(--violet-400); }
  .node--plan { color: var(--ember-300); }
  .node--draft { color: var(--signal-idle); }

  .edge { stroke: var(--border-1); stroke-width: 1; transition: stroke var(--dur-base), stroke-width var(--dur-base), stroke-opacity var(--dur-base); }
  .edge--hot { stroke: var(--ember-600); stroke-width: 1.5; stroke-opacity: 0.7; }
</style>
