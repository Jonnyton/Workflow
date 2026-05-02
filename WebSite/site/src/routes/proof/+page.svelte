<script lang="ts">
  import LiveSourceBar from '$lib/components/LiveSourceBar.svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import {
    compactNumber,
    createPulse,
    relativeStamp,
    shortHash
  } from '$lib/live/project';

  const pulse = createPulse();
  const repoUrl = pulse.repo.repo.remote_url?.replace(/\.git$/, '') || 'https://github.com/Jonnyton/Workflow';
  const repoHeadUrl = pulse.repo.repo.head ? `${repoUrl}/commit/${pulse.repo.repo.head}` : repoUrl;
  const liveNodeCount =
    pulse.knowledgeCount +
    pulse.branchCount +
    pulse.routeCount +
    pulse.mcp.goals.length +
    pulse.mcp.universes.length;

  const proofCards = [
    {
      label: 'Connector',
      title: 'The public MCP route is the product surface.',
      fact: `${compactNumber(pulse.knowledgeCount)} commons records, ${compactNumber(pulse.mcp.goals.length)} goals, and ${compactNumber(pulse.mcp.universes.length)} universes are visible in the current snapshot.`,
      check: 'Open /connect, copy the canonical URL, then refresh MCP.',
      href: '/connect'
    },
    {
      label: 'Graph',
      title: 'Project state renders as a live atlas.',
      fact: `${compactNumber(liveNodeCount)} visible nodes with ${compactNumber(pulse.mcp.edges?.length ?? 0)} extracted MCP edges and ${compactNumber(pulse.branchCount)} branch signals.`,
      check: 'Open /graph, search a bug or branch, and pin a node.',
      href: '/graph'
    },
    {
      label: 'Loop',
      title: 'Public friction routes through an operational loop.',
      fact: `${compactNumber(pulse.mcp.wiki.bugs.length)} bug records and ${compactNumber(pulse.repo.branches.length)} GitHub branches feed the current loop lens.`,
      check: 'Open /loop and click Refresh MCP and Refresh GitHub.',
      href: '/loop'
    },
    {
      label: 'Goals',
      title: 'Goals are the public unit of work.',
      fact: `${compactNumber(pulse.mcp.goals.length)} goals are visible to the same MCP connector that chatbot users call.`,
      check: 'Open /goals, filter a tag, and inspect related commons records.',
      href: '/goals'
    },
    {
      label: 'Repository',
      title: 'The codebase is inspectable from the live page.',
      fact: `Current snapshot head is ${shortHash(pulse.repo.repo.head)} with ${compactNumber(pulse.repo.branches.length)} GitHub branch refs.`,
      check: 'Open the commit and compare it with the status and graph pages.',
      href: repoHeadUrl,
      external: true
    },
    {
      label: 'Boundaries',
      title: 'The site names what is not proven yet.',
      fact: 'Directory acceptance, one-click host install, and real Destiny integration stay labeled as pending instead of being sold as live.',
      check: 'Read /status, /host, /connect, and /economy for current gates.',
      href: '/status'
    }
  ];

  const limits = [
    { title: 'Directory listing', body: 'Workflow is not yet accepted in Claude or ChatGPT directories. Custom MCP URL is the current public path.', href: '/connect' },
    { title: 'Host installer', body: 'Local daemon hosting is source-first until installer artifacts and shortcut creation are proven.', href: '/host' },
    { title: 'Currency rail', body: 'Workflow uses test tiny on Base Sepolia only. Real Destiny (tiny) integration is a later roadmap phase.', href: '/economy' },
    { title: 'ChatGPT connector', body: 'BUG-034 still gates the ChatGPT approval path. The site does not claim that path is solved.', href: '/status' }
  ];

  const checks = [
    { step: 'Use it', body: 'Copy the MCP URL from /connect and ask a capable host to browse goals or wiki records.', href: '/connect' },
    { step: 'Watch it', body: 'Open /graph and /loop to see the same public state as an atlas and as a patch route.', href: '/graph' },
    { step: 'Build it', body: 'Open GitHub, clone the repo, and compare current branch state with the live site.', href: repoUrl, external: true },
    { step: 'Challenge it', body: 'Look at the limits section and file the first mismatch you can prove.', href: `${repoUrl}/issues/new`, external: true }
  ];
</script>

<svelte:head>
  <title>Proof packet - Workflow</title>
  <meta
    name="description"
    content="A live evidence packet for developers and serious contributors evaluating Workflow through MCP, GitHub, graph, loop, and status state."
  />
  <link rel="canonical" href="https://tinyassets.io/proof" />
</svelte:head>

<section class="proof-hero">
  <div class="wrap">
    <RitualLabel color="var(--signal-live)">Proof packet</RitualLabel>
    <h1>Evaluate Workflow in five minutes.</h1>
    <p class="lead">
      This page is for developers, contributors, recruiters, and skeptical evaluators. It does not ask you to trust a pitch. It points at the live connector, graph, loop, repo, and the known gaps.
    </p>
    <LiveSourceBar label="Proof packet sources" detail="Refresh MCP and GitHub before you judge the evidence below." />
  </div>
</section>

<section class="proof-body">
  <div class="wrap">
    <div class="snapshot" aria-label="Current evidence snapshot">
      <article>
        <span>MCP snapshot</span>
        <strong>{relativeStamp(pulse.mcp.fetched_at)}</strong>
        <p>{compactNumber(pulse.knowledgeCount)} commons records and {compactNumber(pulse.mcp.goals.length)} goals.</p>
      </article>
      <article>
        <span>Repo snapshot</span>
        <strong>{shortHash(pulse.repo.repo.head)}</strong>
        <p>{compactNumber(pulse.branchCount)} branches from {pulse.repo.source}.</p>
      </article>
      <article>
        <span>Route surface</span>
        <strong>{compactNumber(pulse.routeCount)}</strong>
        <p>Public route nodes in the project graph snapshot.</p>
      </article>
    </div>

    <div class="section-head">
      <RitualLabel color="var(--ember-500)">Evidence</RitualLabel>
      <h2>What to inspect first.</h2>
    </div>

    <div class="proof-grid">
      {#each proofCards as card (card.label)}
        <a class="proof-card" href={card.href} target={card.external ? '_blank' : undefined} rel={card.external ? 'noreferrer' : undefined}>
          <span>{card.label}</span>
          <strong>{card.title}</strong>
          <p>{card.fact}</p>
          <small>{card.check}</small>
        </a>
      {/each}
    </div>

    <div class="quick-check">
      <div>
        <RitualLabel color="var(--signal-live)">Fast path</RitualLabel>
        <h2>Run the evaluation like a reviewer.</h2>
      </div>
      <ol>
        {#each checks as check (check.step)}
          <li>
            <span>{check.step}</span>
            <p>{check.body}</p>
            <a href={check.href} target={check.external ? '_blank' : undefined} rel={check.external ? 'noreferrer' : undefined}>Open evidence</a>
          </li>
        {/each}
      </ol>
    </div>

    <details class="limits">
      <summary>Known limits that should not be hidden</summary>
      <div class="limit-grid">
        {#each limits as item (item.title)}
          <a href={item.href}>
            <span>{item.title}</span>
            <p>{item.body}</p>
          </a>
        {/each}
      </div>
    </details>
  </div>
</section>

<style>
  .proof-hero {
    padding-block: 80px 28px;
  }

  .proof-body {
    padding-block: 28px 80px;
  }

  .wrap {
    color: var(--fg-2);
    margin: 0 auto;
    max-width: 1180px;
    padding-inline: clamp(16px, 4vw, 32px);
  }

  h1,
  h2 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-weight: 400;
    letter-spacing: 0;
    line-height: 0.98;
    margin: 12px 0 16px;
    text-wrap: balance;
  }

  h1 {
    font-size: clamp(48px, 8vw, 82px);
    max-width: 11ch;
  }

  h2 {
    font-size: clamp(32px, 5vw, 52px);
  }

  .lead {
    font-size: 18px;
    line-height: 1.6;
    margin: 0;
    max-width: 68ch;
  }

  .snapshot,
  .proof-grid,
  .limit-grid {
    display: grid;
    gap: 12px;
  }

  .snapshot {
    grid-template-columns: repeat(3, 1fr);
    margin-bottom: 42px;
  }

  .snapshot article,
  .proof-card,
  .quick-check,
  .limits,
  .limit-grid a {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
  }

  .snapshot article {
    padding: 18px;
  }

  span,
  small,
  .quick-check a,
  .limit-grid a span {
    font-family: var(--font-mono);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  span {
    color: var(--fg-3);
    display: block;
    font-size: 10px;
    margin-bottom: 8px;
  }

  strong {
    color: var(--fg-1);
    display: block;
    font-family: var(--font-display);
    font-size: 25px;
    font-weight: 500;
    line-height: 1.08;
    margin-bottom: 10px;
    overflow-wrap: anywhere;
  }

  p {
    font-size: 14px;
    line-height: 1.6;
    margin: 0;
  }

  .section-head {
    align-items: end;
    display: flex;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 18px;
  }

  .proof-grid {
    grid-template-columns: repeat(3, 1fr);
    margin-bottom: 18px;
  }

  .proof-card,
  .limit-grid a {
    color: inherit;
    display: grid;
    gap: 8px;
    min-width: 0;
    padding: 20px;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }

  .proof-card:hover,
  .limit-grid a:hover {
    background: rgba(109, 211, 166, 0.045);
    border-color: rgba(109, 211, 166, 0.42);
    transform: translateY(-1px);
  }

  .proof-card small {
    color: var(--signal-live);
    font-size: 10px;
    line-height: 1.45;
    margin-top: 8px;
  }

  .quick-check {
    display: grid;
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.2fr);
    gap: 24px;
    margin-top: 18px;
    padding: 24px;
  }

  .quick-check ol {
    counter-reset: proof-step;
    display: grid;
    gap: 10px;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .quick-check li {
    background: var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    counter-increment: proof-step;
    display: grid;
    gap: 6px;
    padding: 14px 16px 14px 44px;
    position: relative;
  }

  .quick-check li::before {
    color: var(--ember-600);
    content: counter(proof-step);
    font-family: var(--font-mono);
    font-size: 12px;
    left: 16px;
    position: absolute;
    top: 16px;
  }

  .quick-check a {
    color: var(--ember-600);
    font-size: 10px;
    text-decoration: none;
    width: fit-content;
  }

  .quick-check a:hover {
    text-decoration: underline;
  }

  .limits {
    margin-top: 18px;
    padding: 16px;
  }

  .limits summary {
    color: var(--fg-1);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    width: fit-content;
  }

  .limit-grid {
    grid-template-columns: repeat(4, 1fr);
    margin-top: 14px;
  }

  .limit-grid a span {
    color: var(--ember-600);
    font-size: 10px;
  }

  @media (max-width: 960px) {
    .proof-grid,
    .limit-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .quick-check {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .snapshot,
    .proof-grid,
    .limit-grid {
      grid-template-columns: 1fr;
    }

    .section-head {
      align-items: start;
      display: block;
    }
  }
</style>
