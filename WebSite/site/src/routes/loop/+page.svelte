<!--
  /loop — "The loop." Leads with the three concrete entry paths and uses a
  snapshot-backed patch-loop playground to show how live work moves.
-->
<script lang="ts">
  import baked from '$lib/content/mcp-snapshot.json';
  import type { Snapshot, Edge } from '$lib/mcp/types';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import { compactNumber, createPulse, shortHash } from '$lib/live/project';

  type StageId = 'intake' | 'investigation' | 'gate' | 'coding' | 'release' | 'observe';
  type RouteState = 'wired' | 'active' | 'scope' | 'blocked' | 'planned';
  type ScenarioId = 'BUG-019' | 'BUG-034' | 'BUG-005' | 'BUG-009' | '4ff5862cc26d';
  type Scenario = {
    id: ScenarioId;
    nodeId: string;
    kind: 'bug' | 'goal';
    label: string;
    eyebrow: string;
    headline: string;
    description: string;
    current: StageId;
    outcome: string;
    stages: Partial<Record<StageId, { state: RouteState; note: string }>>;
  };

  const snapshot = baked as unknown as Snapshot;
  const pulse = createPulse();
  const repoUrl = pulse.repo.repo.remote_url?.replace(/\.git$/, '') || 'https://github.com/Jonnyton/Workflow';

  const STAGES: Array<{
    id: StageId;
    label: string;
    short: string;
    title: string;
    description: string;
    proof: string[];
  }> = [
    {
      id: 'intake',
      label: 'Intake',
      short: 'file or classify',
      title: 'A chatbot turns friction into a public report',
      description: 'The loop starts when a user hits a gap and the chatbot decides whether it is a Workflow primitive problem, a connector issue, or a caller-specific branch problem.',
      proof: ['wiki action=list exposes public BUG pages', 'BUG-013 names the missing feature-request sibling', 'Goal 4ff5862cc26d defines public patch requests as the entry point']
    },
    {
      id: 'investigation',
      label: 'Investigation',
      short: 'turn bug into packet',
      title: 'The report becomes a patch packet',
      description: 'The investigation branch normalizes the report, finds a minimal reproduction, maps root cause, sketches the fix, and writes regression-test expectations before anybody tries to ship code.',
      proof: ['Goal f10caea2e437 is the patch-packet goal', 'BUG-019 is a clean engine example', 'BUG-034 shows why investigation can still re-scope a report']
    },
    {
      id: 'gate',
      label: 'Gate',
      short: 'scope and evidence check',
      title: 'The loop decides whether work moves forward or backward',
      description: 'The gate is the showcase mechanic: it can pass the packet onward, reject weak evidence, or route the item to a different track when the bug is real but not a Workflow engine fix.',
      proof: ['BUG-019 should pass as engine behavior', 'BUG-034 should route to connector approval UX', 'The loop goal explicitly sends work backward with edits']
    },
    {
      id: 'coding',
      label: 'Coding',
      short: 'agent team builds PR',
      title: 'A daemon team turns the packet into a proposed change',
      description: 'Once the gate passes, a lead/dev/checker style branch can plan, implement, and review the patch. Today this stage is honest about the sandbox execution caveat.',
      proof: ['Goal 454b6e72348b covers agent-team project execution', 'BUG-017 blocks reliable dev/checker execution today', 'The original capture names agent_team_3node_v4 as the intended team shape']
    },
    {
      id: 'release',
      label: 'Release',
      short: 'ship with rollback path',
      title: 'Review and release-safety gates protect the live surface',
      description: 'Release is not just merge. The loop needs tests, scoped diffs, migration safety, feature-flag wiring, and a rollback path before a patch earns live traffic.',
      proof: ['Goal 4ff5862cc26d includes review/release and release-safety gates', 'STATUS.md requires freshness-stamped verification claims', 'Public-surface changes require post-change probes']
    },
    {
      id: 'observe',
      label: 'Watch',
      short: 'ratify or loop back',
      title: 'Observation closes the loop instead of ending the pipeline',
      description: 'After shipping, real or simulated usage decides whether the patch is ratified or whether new evidence re-enters intake as a fresh report.',
      proof: ['BUG-009 blocks autonomous scheduled/event-triggered watchers', 'The goal names real or simulated users as evidence', 'The wiki snapshot keeps unresolved blockers visible instead of hiding them']
    }
  ];

  const SCENARIOS: Scenario[] = [
    {
      id: 'BUG-019',
      nodeId: 'bug:BUG-019',
      kind: 'bug',
      label: 'Engine bug',
      eyebrow: 'clean primitive fix',
      headline: 'conditional_edges to END belongs in the patch loop',
      description: 'A real runtime failure in the graph engine. This is the example where intake should keep the item inside Workflow instead of pushing it back to a caller integration.',
      current: 'gate',
      outcome: 'Passes the primitive-fix gate and moves toward a patch packet.',
      stages: {
        intake: { state: 'wired', note: 'Already filed as a wiki bug with a concrete failure mode.' },
        investigation: { state: 'wired', note: 'The patch-packet goal can normalize the report, reproduce the END routing failure, and map root cause.' },
        gate: { state: 'active', note: 'This is a Workflow engine behavior, not a chatbot UI issue, so the gate should keep it in the core loop.' },
        coding: { state: 'blocked', note: 'Coding-team execution is still caveated by BUG-017 sandbox limits.' },
        release: { state: 'planned', note: 'Release gates exist as the intended loop contract; automated enforcement is still emerging.' },
        observe: { state: 'planned', note: 'A live watcher would verify whether terminal routing stays fixed under real runs.' }
      }
    },
    {
      id: 'BUG-034',
      nodeId: 'bug:BUG-034',
      kind: 'bug',
      label: 'Re-scope case',
      eyebrow: 'connector-side failure',
      headline: '"No approval received" should not become an engine patch',
      description: 'A real user-facing failure, but the important move is routing: the loop should recognize that this belongs to connector approval UX, not Workflow graph semantics.',
      current: 'gate',
      outcome: 'Fails the engine-fix gate and gets re-scoped to the connector track.',
      stages: {
        intake: { state: 'wired', note: 'The bug is public, numbered, and visible in the wiki feed.' },
        investigation: { state: 'active', note: 'Investigation still matters: it separates Workflow behavior from client approval behavior.' },
        gate: { state: 'scope', note: 'The gate routes it out of the primitive lane and into connector/platform mitigation.' },
        coding: { state: 'planned', note: 'A patch may still exist, but not as an engine primitive patch packet.' },
        release: { state: 'planned', note: 'Any mitigation needs live chatbot-surface proof before it is accepted.' },
        observe: { state: 'blocked', note: 'Clean-use evidence depends on later real ChatGPT/connector activity.' }
      }
    },
    {
      id: 'BUG-005',
      nodeId: 'bug:BUG-005',
      kind: 'bug',
      label: 'Missing primitive',
      eyebrow: 'why handoff is not yet enough',
      headline: 'sub-branch invocation is the gap between a packet and a real loop',
      description: 'The current page says claim is a packet handoff. BUG-005 is the reason: a node cannot yet invoke a sub-branch and receive the result as first-class state.',
      current: 'intake',
      outcome: 'Stays visible as infrastructure debt that prevents full autonomous chaining.',
      stages: {
        intake: { state: 'active', note: 'This is filed as a primitive gap, not a one-off branch problem.' },
        investigation: { state: 'wired', note: 'The investigation can describe the missing branch-call contract.' },
        gate: { state: 'active', note: 'The gate should confirm this is a platform primitive, because many domains would need it.' },
        coding: { state: 'planned', note: 'A real fix needs API and state-contract design before implementation.' },
        release: { state: 'planned', note: 'Release needs compatibility proof because branch invocation affects many workflows.' },
        observe: { state: 'planned', note: 'Observation would watch whether autonomous handoffs stop degrading into prose packets.' }
      }
    },
    {
      id: 'BUG-009',
      nodeId: 'bug:BUG-009',
      kind: 'bug',
      label: 'Watcher blocker',
      eyebrow: 'the loop cannot wake itself yet',
      headline: 'scheduled or event-triggered branch invocation is the watch-stage blocker',
      description: 'The live-observation module only becomes real when a branch can run on a schedule or event. BUG-009 explains why the final stage is still planned.',
      current: 'observe',
      outcome: 'Blocks autonomous observation and keeps the current loop from closing itself.',
      stages: {
        intake: { state: 'wired', note: 'The missing scheduler is already filed as a primitive bug.' },
        investigation: { state: 'wired', note: 'A patch packet can define the trigger contract and safety boundaries.' },
        gate: { state: 'active', note: 'The gate needs to decide schedule, event, and budget semantics.' },
        coding: { state: 'planned', note: 'Implementation touches daemon invocation and concurrency controls.' },
        release: { state: 'planned', note: 'Release must prove it cannot wake unbounded work.' },
        observe: { state: 'blocked', note: 'Without this, live_observation_watch_v1 remains planned instead of autonomous.' }
      }
    },
    {
      id: '4ff5862cc26d',
      nodeId: 'goal:4ff5862cc26d',
      kind: 'goal',
      label: 'Whole loop',
      eyebrow: 'goal-backed system shape',
      headline: 'the community patch loop is already a public goal',
      description: 'This is the goal that binds the whole story: request, investigate, gate, PR, release, watch, and route backward when evidence fails.',
      current: 'observe',
      outcome: 'Shows the intended end-to-end contract, with planned pieces called out instead of hidden.',
      stages: {
        intake: { state: 'wired', note: 'Wiki reports and public bug IDs are already the intake surface.' },
        investigation: { state: 'wired', note: 'The patch-packet goal exists as a dedicated sub-goal.' },
        gate: { state: 'active', note: 'The design explicitly sends work backward when evidence is weak.' },
        coding: { state: 'blocked', note: 'Agent-team coding is real as a goal, but execution has current sandbox caveats.' },
        release: { state: 'planned', note: 'Review and release-safety gates are part of the design contract.' },
        observe: { state: 'planned', note: 'Live observation is the final missing piece that makes the process a loop.' }
      }
    }
  ];

  let selectedScenarioId = $state<ScenarioId>('BUG-019');
  let selectedStageId = $state<StageId>('intake');

  function findBug(id: string) {
    return snapshot.wiki.bugs.find((bug) => bug.id === id);
  }

  function findGoal(id: string) {
    return snapshot.goals.find((goal) => goal.id === id);
  }

  function pageArg(slug?: string) {
    return slug?.replace(/\.md$/, '') ?? '';
  }

  function stageFor(scenario: Scenario, stage: StageId) {
    return scenario.stages[stage] ?? { state: 'planned' as RouteState, note: 'No live backing artifact is visible yet.' };
  }

  function routeClass(state: RouteState) {
    return `route-state route-state--${state}`;
  }

  const selectedScenario = $derived.by(() => SCENARIOS.find((scenario) => scenario.id === selectedScenarioId) ?? SCENARIOS[0]);
  const selectedStage = $derived.by(() => STAGES.find((stage) => stage.id === selectedStageId) ?? STAGES[0]);
  const selectedStageIndex = $derived.by(() => STAGES.findIndex((stage) => stage.id === selectedStage.id) + 1);
  const selectedStageRoute = $derived.by(() => stageFor(selectedScenario, selectedStage.id));

  const backingTitle = $derived.by(() => {
    if (selectedScenario.kind === 'bug') {
      const bug = findBug(selectedScenario.id);
      return bug ? `${bug.id}: ${bug.title}` : selectedScenario.id;
    }
    const goal = findGoal(selectedScenario.id);
    return goal ? `${goal.id}: ${goal.name}` : selectedScenario.id;
  });

  const relatedEdges = $derived.by((): Edge[] => {
    return (snapshot.edges ?? [])
      .filter((edge) => edge.from === selectedScenario.nodeId || edge.to === selectedScenario.nodeId)
      .slice(0, 7);
  });

  const mcpTrace = $derived.by(() => {
    const bug = selectedScenario.kind === 'bug' ? findBug(selectedScenario.id) : null;
    const stageQueries: Record<StageId, Array<{ tool: string; args: Record<string, string> }>> = {
      intake: [
        { tool: 'wiki', args: { action: 'list', category: 'bugs' } },
        { tool: 'wiki', args: { action: 'search', query: 'file_bug primitive gap patch_request' } }
      ],
      investigation: [
        { tool: 'goals', args: { action: 'list', search: 'patch packet' } },
        { tool: 'wiki', args: { action: 'search', query: 'minimal repro root cause regression tests' } }
      ],
      gate: [
        { tool: 'goals', args: { action: 'list', search: 'patch loop gatekeeping' } },
        { tool: 'wiki', args: { action: 'search', query: 'connector approval engine defect gate' } }
      ],
      coding: [
        { tool: 'goals', args: { action: 'list', search: 'agent teams' } },
        { tool: 'wiki', args: { action: 'search', query: 'BUG-017 sandbox agent_team_3node_v4' } }
      ],
      release: [
        { tool: 'goals', args: { action: 'list', search: 'review release safety rollback' } },
        { tool: 'wiki', args: { action: 'search', query: 'release gate rollback path' } }
      ],
      observe: [
        { tool: 'wiki', args: { action: 'search', query: 'BUG-009 live observation scheduled event-triggered' } },
        { tool: 'goals', args: { action: 'list', search: 'live observation' } }
      ]
    };
    return JSON.stringify(
      {
        source: snapshot.source,
        fetched_at: snapshot.fetched_at,
        selected_stage: selectedStage.id,
        selected: selectedScenario.nodeId,
        requests:
          selectedScenario.kind === 'bug'
            ? [
                { tool: 'wiki', args: { action: 'list', category: 'bugs' } },
                { tool: 'wiki', args: { action: 'read', page: pageArg(bug?.slug) || selectedScenario.id } },
                ...stageQueries[selectedStage.id]
              ]
            : [
                { tool: 'goals', args: { action: 'list', search: 'patch loop' } },
                ...stageQueries[selectedStage.id]
              ]
      },
      null,
      2
    );
  });
</script>

<svelte:head>
  <title>The loop - Workflow</title>
  <meta name="description" content="Watch live Workflow bugs, goals, branches, and gates move through the public contribution loop." />
</svelte:head>

<section class="join-loop join-loop--hero" aria-labelledby="join-loop-title">
  <div class="container">
    <div class="join-copy">
      <RitualLabel color="var(--signal-live)">· Choose your entry ·</RitualLabel>
      <h1 id="join-loop-title">Move the loop from the side that fits you.</h1>
      <p class="lead">The loop is the proof. These are the three things a visitor should do after seeing it: contribute through GitHub, connect the MCP as a user, or host daemon capacity.</p>

      <div class="entry-steps" aria-label="Loop action choices">
        <a class="entry-step" href={`${repoUrl}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noreferrer">
          <span class="entry-step__number">1</span>
          <strong>Contribute through GitHub</strong>
          <p>Open the repo path.</p>
          <small>{compactNumber(pulse.mcp.wiki.bugs.length)} public bugs · {compactNumber(pulse.branchCount)} branches · head {shortHash(pulse.repo.repo.head)}</small>
        </a>
        <a class="entry-step" href="/connect">
          <span class="entry-step__number">2</span>
          <strong>Connect your MCP</strong>
          <p>Use it from your chatbot.</p>
          <small>{pulse.mcp.source} · {compactNumber(pulse.mcp.goals.length)} goals · {compactNumber(pulse.mcp.wiki.bugs.length)} bugs</small>
        </a>
        <a class="entry-step" href="/host">
          <span class="entry-step__number">3</span>
          <strong>Host a daemon</strong>
          <p>Add capacity to the loop.</p>
          <small>{compactNumber(pulse.mcp.universes.length)} universes · {compactNumber(pulse.repo.workflow_branches.length)} workflow branches</small>
        </a>
      </div>
    </div>
  </div>
</section>

<section id="loop-playground" class="playground">
  <div class="container">
    <div class="playground__header">
      <div>
        <RitualLabel color="var(--violet-400)">· Patch loop playground ·</RitualLabel>
        <h2>Click through the loop itself</h2>
        <p>The 1-6 route is the showcase. Real bugs and goals from the MCP snapshot fill the route so the stage behavior is grounded instead of decorative.</p>
      </div>
      <div class="snapshot-meter" aria-label="MCP snapshot counts">
        <span><strong>{snapshot.stats.wiki_promoted}</strong> wiki pages</span>
        <span><strong>{snapshot.stats.goals}</strong> goals</span>
        <span><strong>{snapshot.stats.edges ?? snapshot.edges?.length ?? 0}</strong> edges</span>
      </div>
    </div>

    <div class="loop-workbench">
      <div class="route-map" aria-label="Patch loop route">
        {#each STAGES as stage, index}
          {@const info = stageFor(selectedScenario, stage.id)}
          <button
            class="route-step"
            class:selected={selectedStage.id === stage.id}
            class:current={selectedScenario.current === stage.id}
            aria-label={`${stage.label}: ${info.note}`}
            title={info.note}
            aria-pressed={selectedStage.id === stage.id}
            onclick={() => (selectedStageId = stage.id)}
          >
            <span class={routeClass(info.state)}>{info.state}</span>
            <strong>{index + 1}. {stage.label}</strong>
            <small>{stage.short}</small>
          </button>
        {/each}
        <div class="example-picker">
          <span>Fill the loop with</span>
          <div class="scenario-strip" aria-label="Example artifacts">
            {#each SCENARIOS as scenario}
              <button
                class:selected={selectedScenario.id === scenario.id}
                class="scenario-button"
                aria-pressed={selectedScenario.id === scenario.id}
                onclick={() => (selectedScenarioId = scenario.id)}
              >
                <span>{scenario.label}</span>
                <strong>{scenario.id}</strong>
              </button>
            {/each}
          </div>
        </div>
      </div>

      <article class="artifact-panel">
        <div class="artifact-panel__eyebrow">Stage {selectedStageIndex} · {selectedStage.short}</div>
        <h3>{selectedStage.title}</h3>
        <strong class="artifact-panel__headline">{selectedStage.description}</strong>
        <div class="stage-filled-by">
          <span class={routeClass(selectedStageRoute.state)}>{selectedStageRoute.state}</span>
          <div>
            <small>Filled by {selectedScenario.label.toLowerCase()}</small>
            <strong>{backingTitle}</strong>
            <p>{selectedStageRoute.note}</p>
          </div>
        </div>
        <div class="outcome">
          <span>Loop result for {selectedScenario.id}</span>
          <strong>{selectedScenario.outcome}</strong>
        </div>
        <div class="stage-proof">
          <h4>What backs this stage</h4>
          <ul>
            {#each selectedStage.proof as proof}
              <li>{proof}</li>
            {/each}
          </ul>
        </div>
        <div class="stage-notes">
          {#each STAGES as stage}
            {@const info = stageFor(selectedScenario, stage.id)}
            <div class="stage-note">
              <span class={routeClass(info.state)}>{info.state}</span>
              <div>
                <strong>{stage.label}</strong>
                <p>{info.note}</p>
              </div>
            </div>
          {/each}
        </div>
      </article>

      <aside class="evidence-panel" aria-label="Backing evidence">
        <div class="evidence-block">
          <h3>MCP trace</h3>
          <pre>{mcpTrace}</pre>
        </div>
        <div class="evidence-block">
          <h3>Related edges</h3>
          {#if relatedEdges.length}
            <ul class="edge-list">
              {#each relatedEdges as edge}
                <li>
                  <a href="/graph" aria-label="Open this related edge in the project graph">
                    <span>{edge.kind ?? 'ref'}</span>
                    <code>{edge.from === selectedScenario.nodeId ? edge.to : edge.from}</code>
                  </a>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="empty-evidence">No parsed graph edges in the current snapshot.</p>
          {/if}
        </div>
      </aside>
    </div>
  </div>
</section>

<style>
  .playground, .join-loop { padding-block: 56px; border-top: 1px solid var(--border-1); }
  .join-loop--hero { padding-top: 72px; border-top: none; }
  h1 { font-family: var(--font-display); font-size: clamp(42px, 7vw, 68px); font-weight: 400; letter-spacing: 0; margin: 8px 0 14px; line-height: 0.98; text-wrap: balance; }
  h2 { font-family: var(--font-display); font-size: clamp(28px, 5vw, 40px); font-weight: 500; letter-spacing: 0; margin: 8px 0 14px; line-height: 1.05; }
  .lead { font-size: 17px; color: var(--fg-2); line-height: 1.65; margin: 0 0 14px; max-width: 64ch; }

  .join-loop {
    background: var(--bg-0);
  }
  .join-copy {
    min-width: 0;
  }
  .entry-steps {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    margin-top: 24px;
  }
  .entry-step {
    display: grid;
    gap: 8px;
    grid-template-rows: auto auto 1fr auto;
    min-height: 188px;
    min-width: 0;
    padding: 18px;
    color: inherit;
    text-decoration: none;
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: var(--bg-inset);
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }
  .entry-step:hover {
    border-color: rgba(109, 211, 166, 0.42);
    background: rgba(109, 211, 166, 0.045);
    transform: translateY(-1px);
  }
  .entry-step__number,
  .entry-step small {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    line-height: 1.45;
    text-transform: uppercase;
  }
  .entry-step__number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border: 1px solid rgba(109, 211, 166, 0.32);
    border-radius: 50%;
    background: rgba(109, 211, 166, 0.08);
    color: var(--signal-live);
  }
  .entry-step strong {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(24px, 3vw, 34px);
    font-weight: 500;
    line-height: 1.08;
    overflow-wrap: anywhere;
  }
  .entry-step p {
    color: var(--fg-2);
    font-size: 15px;
    line-height: 1.45;
    margin: 0;
  }

  .playground {
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.025), rgba(255, 255, 255, 0)),
      var(--bg-1);
  }
  .playground__header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 24px;
    align-items: end;
    margin-bottom: 18px;
  }
  .playground__header p {
    color: var(--fg-2);
    font-size: 15px;
    line-height: 1.65;
    max-width: 70ch;
    margin: 0;
  }
  .snapshot-meter {
    display: grid;
    grid-template-columns: repeat(3, minmax(86px, 1fr));
    border: 1px solid var(--border-1);
    background: var(--bg-inset);
    border-radius: 8px;
    overflow: hidden;
  }
  .snapshot-meter span {
    display: grid;
    gap: 2px;
    padding: 10px 12px;
    border-left: 1px solid var(--border-1);
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
  }
  .snapshot-meter span:first-child { border-left: 0; }
  .snapshot-meter strong {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: 24px;
    font-weight: 500;
    line-height: 1;
    text-transform: none;
  }
  .scenario-strip {
    display: grid;
    grid-template-columns: 1fr;
    gap: 6px;
    margin-top: 8px;
  }
  .example-picker {
    grid-column: 1 / -1;
    margin-top: 6px;
    padding-top: 12px;
    border-top: 1px solid var(--border-1);
  }
  .example-picker > span {
    display: block;
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
  }
  .scenario-button {
    display: grid;
    gap: 4px;
    text-align: left;
    min-height: 54px;
    padding: 9px 10px;
    border: 1px solid var(--border-1);
    background: var(--bg-inset);
    color: var(--fg-2);
    border-radius: 8px;
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease-standard), background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  }
  .scenario-button:hover,
  .scenario-button.selected {
    border-color: rgba(204, 120, 92, 0.55);
    background: rgba(204, 120, 92, 0.08);
    color: var(--fg-1);
  }
  .scenario-button span {
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--fg-3);
    text-transform: uppercase;
  }
  .scenario-button strong {
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 500;
    line-height: 1.05;
    overflow-wrap: anywhere;
  }
  .loop-workbench {
    display: grid;
    grid-template-columns: minmax(180px, 0.55fr) minmax(0, 1fr) minmax(270px, 0.8fr);
    gap: 16px;
    align-items: stretch;
  }
  .route-map {
    display: grid;
    gap: 8px;
    align-content: start;
  }
  .route-step {
    position: relative;
    display: grid;
    gap: 5px;
    min-height: 76px;
    padding: 11px 12px 11px 14px;
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: var(--bg-inset);
    color: var(--fg-2);
    text-align: left;
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease-standard), background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  }
  .route-step::after {
    content: "";
    position: absolute;
    left: 24px;
    bottom: -10px;
    width: 1px;
    height: 10px;
    background: var(--border-1);
  }
  .route-step:last-child::after { display: none; }
  .route-step:hover,
  .route-step.selected {
    border-color: rgba(204, 120, 92, 0.6);
    background: rgba(204, 120, 92, 0.075);
  }
  .route-step.current {
    border-color: rgba(138, 99, 206, 0.75);
    background: rgba(138, 99, 206, 0.09);
  }
  .route-step.selected.current {
    border-color: rgba(204, 120, 92, 0.7);
    background: linear-gradient(135deg, rgba(204, 120, 92, 0.08), rgba(138, 99, 206, 0.09));
  }
  .route-step strong {
    color: var(--fg-1);
    font-size: 14px;
    line-height: 1.2;
  }
  .route-step small {
    color: var(--fg-3);
    font-size: 12px;
    line-height: 1.25;
  }
  .route-state {
    width: fit-content;
    border: 1px solid var(--border-1);
    border-radius: 999px;
    padding: 2px 7px;
    font-family: var(--font-mono);
    font-size: 10px;
    line-height: 1.25;
    text-transform: uppercase;
  }
  .route-state--wired { color: var(--signal-live); border-color: rgba(74, 179, 126, 0.45); background: rgba(74, 179, 126, 0.08); }
  .route-state--active { color: var(--violet-200); border-color: rgba(138, 99, 206, 0.45); background: rgba(138, 99, 206, 0.09); }
  .route-state--scope { color: var(--ember-300); border-color: rgba(204, 120, 92, 0.45); background: rgba(204, 120, 92, 0.09); }
  .route-state--blocked { color: var(--ember-600); border-color: rgba(233, 69, 96, 0.45); background: rgba(233, 69, 96, 0.09); }
  .route-state--planned { color: var(--fg-3); border-color: var(--border-1); background: rgba(255, 255, 255, 0.025); }
  .artifact-panel,
  .evidence-panel {
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: var(--bg-inset);
  }
  .artifact-panel {
    padding: 22px;
  }
  .artifact-panel__eyebrow {
    color: var(--ember-300);
    font-family: var(--font-mono);
    font-size: 11px;
    text-transform: uppercase;
  }
  .artifact-panel h3 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(24px, 3vw, 34px);
    font-weight: 500;
    line-height: 1.04;
    margin: 10px 0 10px;
  }
  .artifact-panel__headline {
    display: block;
    color: var(--fg-1);
    font-size: 15px;
    line-height: 1.45;
    margin-bottom: 10px;
  }
  .artifact-panel p {
    color: var(--fg-2);
    font-size: 14.5px;
    line-height: 1.65;
    margin: 0;
  }
  .stage-filled-by {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 12px;
    align-items: start;
    margin: 18px 0;
    padding: 14px;
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.025);
  }
  .stage-filled-by small {
    display: block;
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    line-height: 1.3;
    margin-bottom: 4px;
    text-transform: uppercase;
  }
  .stage-filled-by strong {
    display: block;
    color: var(--fg-1);
    font-size: 14px;
    line-height: 1.35;
    overflow-wrap: anywhere;
  }
  .stage-filled-by p {
    color: var(--fg-3);
    font-size: 13px;
    line-height: 1.55;
    margin-top: 6px;
  }
  .outcome {
    display: grid;
    gap: 5px;
    margin: 18px 0;
    padding: 13px 14px;
    border-left: 2px solid rgba(204, 120, 92, 0.55);
    background: rgba(204, 120, 92, 0.06);
  }
  .outcome span {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
  }
  .outcome strong {
    color: var(--fg-1);
    font-size: 14px;
    line-height: 1.45;
  }
  .stage-notes {
    display: grid;
    gap: 8px;
  }
  .stage-proof {
    margin: 0 0 18px;
    padding: 14px;
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: rgba(74, 179, 126, 0.045);
  }
  .stage-proof h4 {
    color: var(--fg-1);
    font-size: 13px;
    margin: 0 0 8px;
  }
  .stage-proof ul {
    display: grid;
    gap: 6px;
    margin: 0;
    padding-left: 18px;
  }
  .stage-proof li {
    color: var(--fg-2);
    font-size: 13px;
    line-height: 1.45;
  }
  .stage-note {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 10px;
    align-items: start;
    padding: 10px 0;
    border-top: 1px solid var(--border-1);
  }
  .stage-note strong {
    color: var(--fg-1);
    font-size: 13.5px;
  }
  .stage-note p {
    color: var(--fg-3);
    font-size: 13px;
    line-height: 1.55;
    margin-top: 2px;
  }
  .evidence-panel {
    display: grid;
    grid-template-rows: 1fr auto;
    overflow: hidden;
  }
  .evidence-block {
    padding: 16px;
    border-top: 1px solid var(--border-1);
  }
  .evidence-block:first-child { border-top: 0; }
  .evidence-block h3 {
    color: var(--fg-1);
    font-size: 14px;
    margin: 0 0 10px;
  }
  .evidence-block pre {
    max-height: 260px;
    margin: 0;
    overflow: auto;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--fg-2);
    font-family: var(--font-mono);
    font-size: 11px;
    line-height: 1.55;
  }
  .edge-list {
    display: grid;
    gap: 7px;
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .edge-list a {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr);
    gap: 8px;
    align-items: center;
    color: var(--fg-2);
    font-size: 12px;
    background: rgba(255,255,255,0.035);
    border: 1px solid var(--border-1);
    border-radius: 4px;
    padding: 4px 6px;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon);
  }
  .edge-list a:hover {
    border-color: rgba(109, 211, 166, 0.42);
    background: rgba(109, 211, 166, 0.045);
  }
  .edge-list span {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
  }
  .edge-list code {
    overflow-wrap: anywhere;
    color: var(--violet-200);
    font-family: var(--font-mono);
    font-size: 11.5px;
  }
  .empty-evidence {
    color: var(--fg-3);
    font-size: 13px;
    line-height: 1.5;
    margin: 0;
  }

  @media (max-width: 1100px) {
    .playground__header {
      grid-template-columns: 1fr;
      align-items: start;
    }
    .loop-workbench {
      grid-template-columns: minmax(0, 1fr);
    }
    .route-map {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .route-step::after {
      display: none;
    }
    .evidence-panel {
      grid-template-rows: auto;
    }
  }

  @media (max-width: 700px) {
    .playground,
    .join-loop {
      padding-block: 40px;
    }
    .join-loop--hero {
      padding-top: 48px;
    }
    .entry-steps,
    .snapshot-meter,
    .scenario-strip,
    .route-map {
      grid-template-columns: 1fr;
    }
    .entry-step {
      min-height: 188px;
      padding: 18px;
    }
    .artifact-panel {
      padding: 16px;
    }
    .stage-notes {
      grid-template-columns: 1fr;
    }
  }
</style>
