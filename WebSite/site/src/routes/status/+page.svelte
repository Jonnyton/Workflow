<!-- /status — Phase 1.5+ stub. Phase 2 wires Realtime widgets per spec §6. -->
<script lang="ts">
  import LiveSourceBar from '$lib/components/LiveSourceBar.svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import StatusPill from '$lib/components/Primitives/StatusPill.svelte';
  import { compactNumber, createPulse, relativeStamp, shortHash } from '$lib/live/project';

  const pulse = createPulse();
  const evidence = [
    {
      label: 'Public MCP',
      value: pulse.mcp.source,
      status: 'observable',
      body: `${compactNumber(pulse.knowledgeCount)} commons pages, ${compactNumber(pulse.mcp.goals.length)} goals, ${compactNumber(pulse.mcp.universes.length)} universes in the current read.`,
      command: 'Connector setup: /connect',
      href: '/connect'
    },
    {
      label: 'Repo head',
      value: shortHash(pulse.repo.repo.head),
      status: 'GitHub source',
      body: `${compactNumber(pulse.repo.branches.length)} git branches visible when the repo snapshot was generated.`,
      command: pulse.repo.repo.remote_url,
      href: pulse.repo.repo.remote_url.replace(/\.git$/, ''),
      external: true
    },
    {
      label: 'Active universe',
      value: pulse.activeUniverse?.id ?? 'none',
      status: pulse.activeUniverse?.phase ?? 'not visible',
      body: pulse.activeUniverse
        ? `${compactNumber(pulse.activeUniverse.word_count)} words of state, last activity ${relativeStamp(pulse.activeUniverse.last_activity_at)}.`
        : 'Refresh MCP to check whether a universe is visible now.',
      command: 'universe action=list',
      href: '/host'
    },
    {
      label: 'Public graph',
      value: `${compactNumber(pulse.knowledgeCount + pulse.branchCount)}`,
      status: 'live lens',
      body: 'The graph page combines MCP commons, visible GitHub branches, workflow branches, route nodes, and project edges into one public proof surface.',
      command: 'MCP + GitHub graph lens',
      href: '/graph'
    }
  ];

  const devEvidence = [
    {
      label: 'Local preview',
      value: 'localhost:5173',
      body: 'Development preview uses WebSite/preview.bat and hot reload. This is a contributor detail, not a public availability signal.'
    },
    {
      label: 'Snapshot caveat',
      value: pulse.repo.repo.current_branch,
      body: pulse.repo.repo.dirty_note ?? 'No dirty-worktree note was recorded in the baked repo snapshot.'
    }
  ];
</script>

<svelte:head>
  <title>Status — Workflow</title>
</svelte:head>

<section class="status-hero">
  <div class="wrap">
    <RitualLabel color="var(--signal-live)">· Operations room · evidence first ·</RitualLabel>
    <h1>Public health, current work, and deployment pulse.</h1>
    <p>Status answers one question: is the system alive, and what evidence says so? Refresh the live sources, then read the surface-specific proof below.</p>
    <LiveSourceBar label="Status probes" detail="Refresh MCP for connector state; Refresh GitHub for repo head and branch state." />
  </div>
</section>

<section class="ops">
  <div class="wrap">
    <div class="probe">
      <StatusPill kind="live" pulse>MCP connector · canonical</StatusPill>
      <span class="meta">tinyassets.io/mcp · Cloudflare-fronted · public connector path</span>
    </div>

    <div class="ops-grid">
      {#each evidence as row}
        <a class="evidence-card" href={row.href} target={row.external ? '_blank' : undefined} rel={row.external ? 'noreferrer' : undefined}>
          <span class="article-label">{row.label}</span>
          <strong>{row.value}</strong>
          <code>{row.command}</code>
          <p>{row.body}</p>
          <small>{row.status}</small>
        </a>
      {/each}
    </div>

    <div class="watchlist">
      <div>
        <span class="article-label">How to read this page</span>
        <h2>Green is not a promise. Evidence is the promise.</h2>
      </div>
      <p>Status is useful only when it names the surface, the source, and the timestamp. The refresh controls above intentionally expose failure instead of smoothing it over.</p>
    </div>

    <details class="dev-trace">
      <summary>Developer trace</summary>
      <div class="dev-grid">
        {#each devEvidence as row}
          <article>
            <span class="article-label">{row.label}</span>
            <strong>{row.value}</strong>
            <p>{row.body}</p>
          </article>
        {/each}
      </div>
    </details>
  </div>
</section>

<style>
  .status-hero { padding-block: 72px 30px; }
  .ops { padding-block: 20px 72px; }
  .wrap { max-width: 1080px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); color: var(--fg-2); }
  h1 { color: var(--fg-1); font-family: var(--font-display); font-size: clamp(42px, 7vw, 68px); font-weight: 400; letter-spacing: 0; line-height: 0.98; margin: 12px 0 16px; max-width: 12ch; text-wrap: balance; }
  .status-hero p { font-size: 16px; line-height: 1.6; margin: 0; max-width: 66ch; }
  .probe { display: flex; align-items: center; gap: 14px; margin-bottom: 24px; flex-wrap: wrap; }
  .meta { font-family: var(--font-mono); font-size: 12px; color: var(--fg-3); }
  .ops-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .evidence-card, .watchlist { border: 1px solid var(--border-1); background: var(--bg-2); border-radius: 8px; padding: 18px; }
  .evidence-card { color: inherit; display: block; text-decoration: none; transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon); }
  .evidence-card:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .article-label { display: block; color: var(--fg-3); font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px; }
  strong { display: block; color: var(--fg-1); font-family: var(--font-display); font-size: 22px; font-weight: 500; line-height: 1.1; margin-bottom: 10px; overflow-wrap: anywhere; }
  code { display: block; background: var(--bg-inset); border: 1px solid var(--border-1); border-radius: 6px; padding: 10px; color: var(--signal-live); font-family: var(--font-mono); font-size: 12px; overflow-x: auto; }
  p { line-height: 1.6; margin: 12px 0 0; font-size: 13.5px; }
  small { display: inline-block; color: var(--fg-3); font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.08em; margin-top: 12px; text-transform: uppercase; }
  .watchlist { display: grid; grid-template-columns: minmax(0, 0.8fr) minmax(0, 1fr); gap: 24px; margin-top: 12px; }
  .dev-trace { border: 1px dashed var(--border-2); border-radius: 8px; color: var(--fg-3); margin-top: 12px; padding: 14px 16px; }
  .dev-trace summary { cursor: pointer; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; width: fit-content; }
  .dev-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 12px; }
  .dev-grid article { background: var(--bg-inset); border: 1px solid var(--border-1); border-radius: 8px; padding: 14px; }
  h2 { color: var(--fg-1); font-family: var(--font-display); font-size: clamp(28px, 4vw, 38px); font-weight: 500; letter-spacing: 0; line-height: 1; margin: 0; }
  .watchlist p { margin: 0; font-size: 15px; }
  @media (max-width: 900px) { .ops-grid { grid-template-columns: repeat(2, 1fr); } .watchlist, .dev-grid { grid-template-columns: 1fr; } }
  @media (max-width: 620px) { .ops-grid { grid-template-columns: 1fr; } }
</style>
