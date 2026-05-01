<script lang="ts">
  import { onMount } from 'svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import {
    LENS_DEFINITIONS,
    compactNumber,
    createPulse,
    initialMcpSnapshot,
    initialRepoSnapshot,
    refreshMcpSnapshot,
    refreshRepoSnapshot,
    relativeStamp,
    shortHash,
    type LensKey,
    type ProjectPulse
  } from '$lib/live/project';

  type Metric = { label: string; value: string; note: string; href?: string; external?: boolean };
  type LensItem = { kicker: string; title: string; body: string; meta?: string; href?: string; external?: boolean };
  type MiniGraphNode = { id: string; x: number; y: number; r: number; kind: string; label: string; active?: boolean };
  type MiniGraphEdge = { id: string; x1: number; y1: number; x2: number; y2: number; kind: string };
  type MiniGraph = { nodes: MiniGraphNode[]; edges: MiniGraphEdge[]; nodeCount: number; edgeCount: number };

  let {
    lens = 'home',
    heading = 'h2',
    compact = false
  } = $props<{
    lens?: LensKey;
    heading?: 'h1' | 'h2';
    compact?: boolean;
  }>();

  let mcp = $state(initialMcpSnapshot);
  let repo = $state(initialRepoSnapshot);
  let mcpLoading = $state(false);
  let githubLoading = $state(false);
  let mcpError = $state('');
  let githubError = $state('');

  const activeLens = $derived(lens as LensKey);
  const pulse = $derived(createPulse(mcp, repo));
  const definition = $derived(LENS_DEFINITIONS[activeLens]);
  const metrics = $derived.by(() => metricsFor(activeLens, pulse));
  const items = $derived.by(() => itemsFor(activeLens, pulse));
  const graphPreview = $derived.by(() => graphPreviewFor(pulse, activeLens));
  const showWatchingCell = $derived(definition.primaryHref !== '/graph');

  async function refreshMcp() {
    mcpLoading = true;
    mcpError = '';
    try {
      mcp = await refreshMcpSnapshot(mcp);
    } catch (err) {
      mcpError = err instanceof Error ? err.message : String(err);
    } finally {
      mcpLoading = false;
    }
  }

  async function refreshGithub() {
    githubLoading = true;
    githubError = '';
    try {
      repo = await refreshRepoSnapshot(repo);
    } catch (err) {
      githubError = err instanceof Error ? err.message : String(err);
    } finally {
      githubLoading = false;
    }
  }

  onMount(() => {
    void refreshMcp();
  });

  function metricsFor(activeLens: LensKey, project: ProjectPulse): Metric[] {
    const repoUrl = project.repo.repo.remote_url?.replace(/\.git$/, '') || 'https://github.com/Jonnyton/Workflow';
    const repoHead = project.repo.repo.head || project.repo.branches[0]?.commit || '';
    const shared = {
      wiki: {
        label: 'Commons',
        value: compactNumber(project.knowledgeCount),
        note: `${project.mcp.wiki.bugs.length} bugs, ${project.mcp.wiki.drafts.length} drafts`,
        href: '/wiki'
      },
      goals: {
        label: 'Goals',
        value: compactNumber(project.mcp.goals.length),
        note: 'live MCP goal targets',
        href: '/goals'
      },
      branches: {
        label: 'Branches',
        value: compactNumber(project.branchCount),
        note: `${project.repo.branches.length} GitHub, ${project.repo.workflow_branches.length} workflow`,
        href: '/graph'
      },
      universes: {
        label: 'Universes',
        value: compactNumber(project.mcp.universes.length),
        note: project.activeUniverse ? project.activeUniverse.phase : 'none visible',
        href: '/host'
      },
      head: {
        label: 'Repo head',
        value: shortHash(repoHead),
        note: 'GitHub repo snapshot',
        href: repoHead ? `${repoUrl}/commit/${repoHead}` : repoUrl,
        external: true
      }
    };

    if (activeLens === 'status') return [shared.wiki, shared.goals, shared.universes, shared.head];
    if (activeLens === 'connect') return [shared.wiki, shared.goals, shared.universes, { label: 'Endpoint', value: '200?', note: 'probe with MCP refresh', href: '/connect' }];
    if (activeLens === 'goals') return [shared.goals, shared.branches, { label: 'Matches', value: compactNumber(project.mcp.edges?.length ?? 0), note: 'goal/wiki relationships', href: '/graph' }, shared.wiki];
    if (activeLens === 'host') return [shared.universes, shared.branches, { label: 'Routes', value: compactNumber(project.routeCount), note: 'website host surfaces', href: '/graph' }, shared.head];
    if (activeLens === 'economy') return [shared.goals, { label: 'Gate work', value: compactNumber(project.mcp.wiki.plans.length), note: 'plans feeding settlement', href: '/loop' }, shared.branches, shared.wiki];
    if (activeLens === 'alliance') return [shared.wiki, shared.goals, { label: 'Entry paths', value: '4', note: 'chatbot, GitHub, email, wiki', href: '/alliance' }, shared.branches];
    return [shared.wiki, shared.goals, shared.branches, shared.universes];
  }

  function itemsFor(activeLens: LensKey, project: ProjectPulse): LensItem[] {
    if (activeLens === 'connect') {
      return [
        { kicker: 'MCP call', title: 'wiki action=list', body: `${project.mcp.stats.wiki_promoted} promoted pages and ${project.mcp.stats.wiki_drafts} drafts are visible to the browser path.`, meta: project.mcp.source, href: '/wiki' },
        { kicker: 'MCP call', title: 'goals action=list', body: `${project.mcp.goals.length} public goals can be browsed by the same connector URL.`, meta: project.currentGoal?.id, href: '/goals' },
        { kicker: 'MCP call', title: 'universe action=list', body: `${project.mcp.universes.length} universes are in the current snapshot.`, meta: project.activeUniverse?.phase, href: '/host' }
      ];
    }

    if (activeLens === 'goals') {
      return project.mcp.goals.slice(0, 4).map((goal) => ({
        kicker: 'Goal',
        title: goal.name,
        body: goal.summary || 'No summary in snapshot.',
        meta: goal.id,
        href: '/goals'
      }));
    }

    if (activeLens === 'host') {
      const universes = project.mcp.universes.map((universe) => ({
        kicker: 'Universe',
        title: universe.id,
        body: `${universe.phase} with ${compactNumber(universe.word_count)} words of state.`,
        meta: universe.last_activity_at ? `activity ${relativeStamp(universe.last_activity_at)}` : 'snapshot universe',
        href: '/graph'
      }));
      return universes.length ? universes : [{ kicker: 'Host surface', title: 'No live universe in snapshot', body: 'Refresh MCP to check the current host-visible state.', meta: project.mcp.source, href: '/host' }];
    }

    if (activeLens === 'economy') {
      return [
        { kicker: 'Work target', title: project.currentGoal?.name ?? 'No public goal', body: project.currentGoal?.summary ?? 'Refresh MCP to inspect current goals.', meta: project.currentGoal?.id, href: '/goals' },
        { kicker: 'Gate source', title: 'Outcome evidence', body: `${project.mcp.wiki.plans.length} plans and ${project.mcp.wiki.bugs.length} bugs can become claim, gate, or settlement inputs.`, meta: 'MCP commons', href: '/wiki' },
        { kicker: 'Repo rail', title: project.repo.repo.name, body: `Settlement code and disclosure copy live with the repo state at ${shortHash(project.repo.repo.head)}.`, meta: project.repo.source, href: '/graph' }
      ];
    }

    if (activeLens === 'alliance') {
      return [
        { kicker: 'Feature want', title: project.currentBug?.id ?? 'No bug selected', body: project.currentBug?.title ?? 'The commons has no current bug in this snapshot.', meta: 'enters the loop through wiki', href: '/wiki' },
        { kicker: 'Public forum', title: 'GitHub Issues', body: 'Long-form ideas, bugs, and RFCs start in the open, then route back into wiki, goals, or branches.', meta: project.repo.repo.remote_url, href: 'https://github.com/Jonnyton/Workflow/issues', external: true },
        { kicker: 'Chatbot path', title: 'Connector-mediated filing', body: 'A real user can ask their chatbot to file the bug or feature request directly.', meta: 'tinyassets.io/mcp', href: '/connect' }
      ];
    }

    if (activeLens === 'status') {
      return [
        { kicker: 'MCP source', title: project.mcp.source, body: `Snapshot fetched ${relativeStamp(project.mcp.fetched_at)}. Refresh probes the live connector path.`, meta: 'tinyassets.io/mcp', href: '/connect' },
        { kicker: 'GitHub source', title: project.repo.source, body: `Repo snapshot fetched ${relativeStamp(project.repo.fetched_at)}. Refresh pulls branch data from GitHub.`, meta: `head ${shortHash(project.repo.repo.head)}`, href: project.repo.repo.remote_url?.replace(/\.git$/, '') || 'https://github.com/Jonnyton/Workflow', external: true },
        { kicker: 'Current universe', title: project.activeUniverse?.id ?? 'No universe', body: project.activeUniverse ? `${project.activeUniverse.phase}, ${compactNumber(project.activeUniverse.word_count)} words.` : 'No live universe in snapshot.', meta: project.activeUniverse?.last_activity_at ? relativeStamp(project.activeUniverse.last_activity_at) : 'snapshot', href: '/host' }
      ];
    }

    return [
      { kicker: 'Now changing', title: project.currentGoal?.name ?? 'No goal', body: project.currentGoal?.summary ?? 'Refresh MCP to fetch current goals.', meta: project.currentGoal?.id, href: '/loop' },
      { kicker: 'Open friction', title: project.currentBug?.id ?? 'No bug', body: project.currentBug?.title ?? 'No bug selected in this snapshot.', meta: 'fills the loop', href: '/wiki' },
      { kicker: 'Repo pulse', title: project.repo.repo.current_branch, body: `${project.repo.branches.length} branches visible. Current head ${shortHash(project.repo.repo.head)}.`, meta: project.repo.source, href: '/graph' }
    ];
  }

  function graphPreviewFor(project: ProjectPulse, activeLens: LensKey): MiniGraph {
    const activeId =
      activeLens === 'home' ? 'site' :
      activeLens === 'goals' ? 'goals' :
      activeLens;
    const nodes: MiniGraphNode[] = [
      { id: 'repo', x: 20, y: 48, r: 7, kind: 'repo', label: project.repo.repo.name || 'repo' },
      { id: 'wiki', x: 67, y: 43, r: 9, kind: 'wiki', label: 'wiki' },
      { id: 'loop', x: 47, y: 70, r: 8, kind: 'loop', label: 'loop' },
      { id: 'graph', x: 49, y: 29, r: 10, kind: 'graph', label: 'graph' },
      { id: 'host', x: 82, y: 64, r: 6, kind: 'host', label: project.activeUniverse?.id ?? 'host' },
      { id: 'site', x: 31, y: 78, r: 6, kind: 'site', label: 'site' },
      { id: 'connect', x: 18, y: 82, r: 4, kind: 'site', label: 'connect' },
      { id: 'status', x: 24, y: 68, r: 4, kind: 'site', label: 'status' },
      { id: 'goals', x: 39, y: 86, r: 4, kind: 'goal', label: 'goals' },
      { id: 'economy', x: 42, y: 92, r: 4, kind: 'goal', label: 'economy' },
      { id: 'alliance', x: 12, y: 72, r: 4, kind: 'wiki', label: 'alliance' }
    ];

    const satellites = [
      ...project.repo.branches.slice(0, 4).map((branch, index) => ({ id: `branch-${index}`, label: branch.name, kind: 'repo', anchor: 'repo' })),
      ...project.mcp.goals.slice(0, 4).map((goal, index) => ({ id: `goal-${index}`, label: goal.name, kind: 'goal', anchor: 'loop' })),
      ...project.mcp.wiki.bugs.slice(0, 6).map((bug, index) => ({ id: `bug-${index}`, label: bug.id, kind: 'bug', anchor: 'wiki' })),
      ...project.mcp.universes.slice(0, 2).map((universe, index) => ({ id: `universe-${index}`, label: universe.id, kind: 'host', anchor: 'host' }))
    ];
    const positions = [
      [12, 32], [14, 66], [32, 34], [30, 61], [77, 25], [85, 42],
      [76, 77], [60, 81], [53, 17], [39, 20], [91, 56], [22, 82],
      [69, 68], [56, 56], [44, 44], [35, 88]
    ];
    satellites.forEach((satellite, index) => {
      const [x, y] = positions[index % positions.length];
      nodes.push({ id: satellite.id, x, y, r: satellite.kind === 'bug' ? 3 : 3.6, kind: satellite.kind, label: satellite.label });
    });

    nodes.forEach((node) => {
      if (node.id === activeId) {
        node.active = true;
        node.r = Math.max(node.r + 2.2, 6.2);
      }
    });

    const byId = new Map(nodes.map((node) => [node.id, node]));
    const edgePairs = [
      ['graph', 'repo'], ['graph', 'wiki'], ['graph', 'loop'], ['graph', 'host'], ['repo', 'loop'], ['wiki', 'loop'], ['host', 'loop'], ['site', 'graph'],
      ['site', 'connect'], ['site', 'status'], ['site', 'goals'], ['site', 'loop'], ['site', 'economy'], ['site', 'alliance'],
      ...satellites.map((satellite) => [satellite.anchor, satellite.id])
    ];
    const edges = edgePairs.flatMap(([from, to], index) => {
      const a = byId.get(from);
      const b = byId.get(to);
      return a && b ? [{ id: `${from}-${to}-${index}`, x1: a.x, y1: a.y, x2: b.x, y2: b.y, kind: b.kind }] : [];
    });

    return {
      nodes,
      edges,
      nodeCount: project.knowledgeCount + project.branchCount + project.mcp.goals.length + project.mcp.universes.length + project.routeCount,
      edgeCount: project.mcp.edges?.length ?? edges.length
    };
  }
</script>

<section class:compact class="live-lens" aria-label={`${definition.eyebrow}: ${definition.title}`}>
  <div class="lens-wrap">
    <div class="lens-head">
      <div>
        <RitualLabel color="var(--signal-live)">· {definition.eyebrow} ·</RitualLabel>
        {#if heading === 'h1'}
          <h1>{definition.title}</h1>
        {:else}
          <h2>{definition.title}</h2>
        {/if}
        <p class="question">{definition.question}</p>
      </div>

      <div class="refresh-box" aria-label="Live data controls">
        <button type="button" onclick={refreshMcp} disabled={mcpLoading}>
          {mcpLoading ? 'MCP...' : 'Refresh MCP'}
        </button>
        <button type="button" onclick={refreshGithub} disabled={githubLoading}>
          {githubLoading ? 'GitHub...' : 'Refresh GitHub'}
        </button>
        <span>MCP {relativeStamp(mcp.fetched_at)}</span>
        <span>GitHub {relativeStamp(repo.fetched_at)}</span>
      </div>
    </div>

    {#if mcpError || githubError}
      <div class="errors" role="status">
        {#if mcpError}<p>MCP refresh failed: <code>{mcpError}</code></p>{/if}
        {#if githubError}<p>GitHub refresh failed: <code>{githubError}</code></p>{/if}
      </div>
    {/if}

    {#if activeLens === 'home'}
      <div class="demo-prompt" aria-label="Concrete Workflow demo">
        <span>Demo prompt</span>
        <p>"Using Workflow, show open project work and file a patch request for the issue I describe."</p>
        <strong>Result: the chatbot reads the MCP commons, routes the request into the loop, and the graph/status pages show the same live state changing.</strong>
      </div>
      <div class="home-actions" aria-label="Primary Workflow actions">
        <a class="home-action" href="/connect">
          <span>1 · Use it</span>
          <strong>Connect your chatbot.</strong>
          <p>Paste one MCP URL. Your chatbot can browse goals, file bugs, and summon work.</p>
          <small>{mcp.source} · {relativeStamp(mcp.fetched_at)}</small>
        </a>

        <a class="home-action home-action--graph" href="/graph">
          <span>2 · Watch it</span>
          <strong>Open the live graph.</strong>
          <svg viewBox="0 0 100 100" role="img" aria-label="Live mini project graph">
            {#each graphPreview.edges as edge (edge.id)}
              <line class="mini-edge mini-edge--{edge.kind}" x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} />
            {/each}
            {#each graphPreview.nodes as node (node.id)}
              <g class="mini-node mini-node--{node.kind}" class:active={node.active}>
                <circle cx={node.x} cy={node.y} r={node.r} />
                {#if node.r >= 7 || node.active}
                  <text x={node.x + node.r + 2} y={node.y + 1.5}>{node.label}</text>
                {/if}
              </g>
            {/each}
          </svg>
          <small>{compactNumber(graphPreview.nodeCount)} live nodes · {compactNumber(graphPreview.edgeCount)} edges</small>
        </a>

        <a class="home-action" href="/loop">
          <span>3 · Help build it</span>
          <strong>Join the loop.</strong>
          <p>Pick up public friction, contribute a branch, or host capacity for live work.</p>
          <small>{compactNumber(pulse.mcp.wiki.bugs.length)} bugs · {compactNumber(pulse.branchCount)} branches</small>
        </a>
      </div>
    {:else}
      <div class:truth-strip--without-watch={!showWatchingCell} class="truth-strip" aria-label="What this lens is watching">
      {#if showWatchingCell}
        <a class="truth-cell truth-cell--link truth-cell--wide" href={definition.primaryHref}>
          <span>Watching</span>
          <strong>{definition.watches}</strong>
          <small>{definition.proof}</small>
        </a>
      {/if}
      <div class="source-cells">
        <article class="truth-cell truth-cell--source">
          <span>MCP source</span>
          <strong>{mcp.source}</strong>
          <small>{relativeStamp(mcp.fetched_at)}</small>
        </article>
        <article class="truth-cell truth-cell--source">
          <span>GitHub source</span>
          <strong>{repo.source}</strong>
          <small>{relativeStamp(repo.fetched_at)}</small>
        </article>
      </div>
      <a class="graph-preview-link" href="/graph" aria-label={`Open live project graph from ${definition.eyebrow}`}>
        <svg viewBox="0 0 100 100" role="img" aria-label="Live mini project graph">
          {#each graphPreview.edges as edge (edge.id)}
            <line class="mini-edge mini-edge--{edge.kind}" x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} />
          {/each}
          {#each graphPreview.nodes as node (node.id)}
            <g class="mini-node mini-node--{node.kind}" class:active={node.active}>
              <circle cx={node.x} cy={node.y} r={node.r} />
              {#if node.r >= 7 || node.active}
                <text x={node.x + node.r + 2} y={node.y + 1.5}>{node.label}</text>
              {/if}
            </g>
          {/each}
        </svg>
        <span>Open live project graph</span>
        <small>{compactNumber(graphPreview.nodeCount)} live nodes · {compactNumber(graphPreview.edgeCount)} edges · {activeLens}</small>
      </a>
      </div>

    <div class="metrics" aria-label="Live project metrics">
      {#each metrics as metric (metric.label)}
        {#if metric.href}
          <a class="metric metric--link" href={metric.href} target={metric.external ? '_blank' : undefined} rel={metric.external ? 'noreferrer' : undefined} aria-label={`Open live source for ${metric.label}`}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.note}</small>
          </a>
        {:else}
          <article class="metric">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.note}</small>
          </article>
        {/if}
      {/each}
    </div>

    <div class="items" aria-label="Lens readout">
      {#each items as item (item.kicker + item.title)}
        {#if item.href}
          <a class="item item--link" href={item.href} target={item.external ? '_blank' : undefined} rel={item.external ? 'noreferrer' : undefined}>
            <span>{item.kicker}</span>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            {#if item.meta}<small>{item.meta}</small>{/if}
          </a>
        {:else}
          <article class="item">
            <span>{item.kicker}</span>
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            {#if item.meta}<small>{item.meta}</small>{/if}
          </article>
        {/if}
      {/each}
    </div>
    {/if}
  </div>
</section>

<style>
  .live-lens {
    border-top: 1px solid var(--border-1);
    border-bottom: 1px solid var(--border-1);
    background:
      linear-gradient(180deg, rgba(109, 211, 166, 0.055), transparent 38%),
      var(--bg-0);
    padding-block: 64px;
  }

  .live-lens.compact {
    padding-block: 42px;
  }

  .lens-wrap {
    max-width: 1200px;
    margin: 0 auto;
    padding-inline: clamp(16px, 4vw, 32px);
  }

  .lens-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 250px;
    gap: 32px;
    align-items: start;
    margin-bottom: 24px;
  }

  h1,
  h2 {
    font-family: var(--font-display);
    font-weight: 400;
    letter-spacing: 0;
    line-height: 0.98;
    color: var(--fg-1);
    margin: 12px 0 14px;
    text-wrap: balance;
  }

  h1 {
    font-size: clamp(48px, 8vw, 82px);
  }

  h2 {
    font-size: clamp(32px, 5vw, 52px);
  }

  .question {
    color: var(--fg-2);
    font-size: 16px;
    line-height: 1.65;
    max-width: 74ch;
    margin: 0;
  }

  .refresh-box {
    border: 1px solid var(--border-1);
    background: var(--bg-2);
    border-radius: 8px;
    padding: 12px;
    display: grid;
    gap: 8px;
  }

  .refresh-box button {
    border: 1px solid var(--border-1);
    background: var(--bg-inset);
    color: var(--fg-1);
    border-radius: 6px;
    padding: 9px 10px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    cursor: pointer;
  }

  .refresh-box button:hover:not(:disabled) {
    border-color: rgba(109, 211, 166, 0.5);
    color: var(--signal-live);
  }

  .refresh-box button:disabled {
    opacity: 0.55;
    cursor: wait;
  }

  .refresh-box span {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    line-height: 1.4;
  }

  .errors {
    border: 1px solid rgba(233, 69, 96, 0.3);
    background: rgba(233, 69, 96, 0.08);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 16px;
  }

  .errors p {
    color: var(--fg-2);
    font-size: 12px;
    line-height: 1.5;
    margin: 0;
  }

  .truth-strip {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr) auto;
    gap: 10px;
    align-items: stretch;
    margin-bottom: 14px;
  }

  .home-actions {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 24px;
  }

  .demo-prompt {
    border: 1px solid rgba(109, 211, 166, 0.28);
    border-radius: 8px;
    background: rgba(109, 211, 166, 0.045);
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 6px 14px;
    margin-top: 18px;
    padding: 14px 16px;
  }

  .demo-prompt span {
    color: var(--signal-live);
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .demo-prompt p,
  .demo-prompt strong {
    margin: 0;
    min-width: 0;
  }

  .demo-prompt p {
    color: var(--fg-1);
    font-family: var(--font-mono);
    font-size: 13px;
    grid-column: 2;
    line-height: 1.45;
  }

  .demo-prompt strong {
    color: var(--fg-2);
    font-size: 13px;
    font-weight: 500;
    grid-column: 2;
    line-height: 1.5;
  }

  .home-action {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    color: var(--fg-2);
    display: grid;
    gap: 10px;
    min-height: 260px;
    min-width: 0;
    padding: 20px;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }

  .home-action:hover {
    background: rgba(109, 211, 166, 0.045);
    border-color: rgba(109, 211, 166, 0.42);
    transform: translateY(-1px);
  }

  .home-action span,
  .home-action small {
    font-family: var(--font-mono);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .home-action span {
    color: var(--ember-600);
    font-size: 10.5px;
  }

  .home-action strong {
    color: var(--fg-1);
    display: block;
    font-family: var(--font-display);
    font-size: clamp(26px, 3vw, 36px);
    font-weight: 500;
    letter-spacing: 0;
    line-height: 0.98;
    text-wrap: balance;
  }

  .home-action p {
    color: var(--fg-2);
    font-size: 15px;
    line-height: 1.58;
    margin: 0;
  }

  .home-action small {
    align-self: end;
    color: var(--fg-3);
    font-size: 10px;
    line-height: 1.35;
  }

  .home-action--graph {
    background: rgba(21, 35, 68, 0.88);
  }

  .home-action--graph svg {
    aspect-ratio: 1.6;
    background: radial-gradient(circle at 50% 44%, rgba(109, 211, 166, 0.12), transparent 42%), var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 6px;
    display: block;
    overflow: hidden;
    width: 100%;
  }

  .source-cells {
    display: contents;
  }

  .truth-cell,
  .graph-preview-link {
    border: 1px solid var(--border-1);
    background: rgba(255, 255, 255, 0.025);
    border-radius: 8px;
    color: inherit;
    padding: 12px 14px;
    min-width: 0;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }

  .truth-cell--link:hover,
  .graph-preview-link:hover {
    border-color: rgba(109, 211, 166, 0.42);
    background: rgba(109, 211, 166, 0.045);
    transform: translateY(-1px);
  }

  .truth-cell--source {
    cursor: default;
  }

  .truth-cell span {
    display: block;
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 9.5px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .truth-cell strong {
    display: block;
    color: var(--fg-1);
    font-family: var(--font-mono);
    font-size: 11.5px;
    font-weight: 600;
    line-height: 1.35;
    overflow-wrap: anywhere;
  }

  .truth-cell small {
    display: block;
    color: var(--fg-3);
    font-size: 11.5px;
    line-height: 1.45;
    margin-top: 6px;
  }

  .graph-preview-link {
    display: grid;
    gap: 8px;
    min-width: 210px;
    padding: 10px;
  }

  .graph-preview-link svg {
    aspect-ratio: 1.65;
    background: radial-gradient(circle at 50% 44%, rgba(109, 211, 166, 0.12), transparent 42%), var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 6px;
    display: block;
    overflow: hidden;
    width: 100%;
  }

  .graph-preview-link span,
  .graph-preview-link small {
    font-family: var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .graph-preview-link span {
    color: var(--ember-600);
    font-size: 10.5px;
    line-height: 1.25;
  }

  .graph-preview-link small {
    color: var(--fg-3);
    font-size: 9.5px;
    line-height: 1.35;
  }

  .mini-edge {
    stroke: rgba(255, 255, 255, 0.19);
    stroke-linecap: round;
    stroke-width: 0.8;
  }

  .mini-edge--bug { stroke: rgba(233, 69, 96, 0.34); }
  .mini-edge--goal,
  .mini-edge--host { stroke: rgba(109, 211, 166, 0.33); }
  .mini-edge--repo { stroke: rgba(160, 183, 255, 0.32); }

  .mini-node circle {
    fill: var(--bg-2);
    stroke: var(--fg-3);
    stroke-width: 1.25;
  }

  .mini-node text {
    fill: rgba(255, 255, 255, 0.72);
    font-family: var(--font-mono);
    font-size: 3.6px;
    letter-spacing: 0;
    text-transform: none;
  }

  .mini-node--graph circle {
    fill: rgba(233, 69, 96, 0.26);
    stroke: var(--ember-500);
    stroke-width: 1.7;
  }

  .mini-node--wiki circle,
  .mini-node--goal circle,
  .mini-node--host circle {
    fill: rgba(109, 211, 166, 0.18);
    stroke: var(--signal-live);
  }

  .mini-node--repo circle {
    fill: rgba(160, 183, 255, 0.16);
    stroke: var(--violet-200);
  }

  .mini-node--bug circle {
    fill: rgba(233, 69, 96, 0.2);
    stroke: var(--ember-600);
  }

  .mini-node--loop circle,
  .mini-node--site circle {
    fill: rgba(138, 99, 206, 0.2);
    stroke: var(--violet-400);
  }

  .mini-node.active circle {
    filter: drop-shadow(0 0 5px rgba(233, 69, 96, 0.75));
    stroke: var(--ember-500);
    stroke-width: 2;
  }

  .mini-node.active text {
    fill: var(--fg-1);
    font-size: 4.1px;
    font-weight: 700;
  }

  .metrics {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 14px;
  }

  .metric {
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: var(--bg-2);
    padding: 14px 16px;
    min-width: 0;
    color: inherit;
    display: block;
    text-decoration: none;
  }

  .metric--link,
  .item--link {
    cursor: pointer;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }

  .metric--link:hover,
  .item--link:hover {
    border-color: rgba(109, 211, 166, 0.42);
    background: rgba(109, 211, 166, 0.045);
    transform: translateY(-1px);
  }

  .metric span,
  .item span {
    display: block;
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .metric strong {
    display: block;
    color: var(--signal-live);
    font-family: var(--font-display);
    font-size: 32px;
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1;
    margin-bottom: 6px;
  }

  .metric small,
  .item small {
    color: var(--fg-3);
    font-size: 12px;
    line-height: 1.45;
  }

  .items {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  .item {
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: var(--bg-inset);
    padding: 18px;
    min-width: 0;
    color: inherit;
    display: block;
    text-decoration: none;
  }

  .item h3 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1.12;
    margin: 0 0 10px;
    overflow-wrap: anywhere;
  }

  .item p {
    color: var(--fg-2);
    font-size: 13.5px;
    line-height: 1.58;
    margin: 0 0 12px;
  }

  @media (min-width: 901px) {
    .truth-strip--without-watch {
      grid-template-columns: minmax(0, 0.86fr) minmax(280px, 1.14fr);
      align-items: start;
    }

    .truth-strip--without-watch .source-cells {
      display: grid;
      gap: 10px;
      align-self: start;
    }
  }

  @media (max-width: 900px) {
    .lens-head {
      grid-template-columns: 1fr;
    }

    .refresh-box {
      grid-template-columns: 1fr 1fr;
    }

    .home-actions,
    .metrics,
    .items,
    .truth-strip {
      grid-template-columns: repeat(2, 1fr);
    }

  }

  @media (max-width: 620px) {
    .home-actions,
    .metrics,
    .items,
    .truth-strip {
      grid-template-columns: 1fr;
    }

    .refresh-box {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      padding: 10px;
    }

    .refresh-box span {
      font-size: 9px;
    }

    .demo-prompt {
      grid-template-columns: 1fr;
    }

    .demo-prompt p,
    .demo-prompt strong {
      grid-column: 1;
    }
  }
</style>
