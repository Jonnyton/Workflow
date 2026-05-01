<!--
  /connect — radical simplicity. Add the connector. Then talk.
  Ported from design-source/ui_kits/workflow-web/Connect.jsx.
-->
<script lang="ts">
  import strings from '$lib/i18n/en.json';
  import LiveSourceBar from '$lib/components/LiveSourceBar.svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';

  const t = strings.connect;
  const url = t.mcp_url;
  const requestEnvelope = JSON.stringify(
    {
      server: 'tinyassets.io/mcp',
      calls: [
        { tool: 'wiki', arguments: { action: 'list' } },
        { tool: 'goals', arguments: { action: 'list' } },
        { tool: 'universe', arguments: { action: 'list' } }
      ]
    },
    null,
    2
  );
  const protocolFacts = [
    { label: 'read commons', href: '/wiki' },
    { label: 'browse goals', href: '/catalog' },
    { label: 'inspect universes', href: '/host' }
  ];
  const launchHosts = ['Claude.ai', 'Claude Desktop', 'Claude mobile', 'ChatGPT Apps', 'ChatGPT developer mode'];
  const builderHosts = ['Codex', 'Gemini CLI', 'VS Code / Copilot', 'Cursor', 'Cline / Roo', 'Continue', 'Windsurf', 'Replit Agent'];
  const communityHosts = ['LibreChat', 'Open WebUI', 'LM Studio', 'Goose', 'Zed', '5ire', 'custom MCP hosts'];
  const hostRows = [
    {
      tier: 'P0 launch gates',
      hosts: 'Claude + ChatGPT',
      path: 'Remote MCP at tinyassets.io/mcp',
      proof: 'Live chatbot proof before public parity claims'
    },
    {
      tier: 'P1 builder hosts',
      hosts: 'Codex, Gemini CLI, VS Code, Cursor, Cline/Roo, Continue, Windsurf',
      path: 'Local or remote MCP config',
      proof: 'Host-specific tool-list + safe tool-call smoke'
    },
    {
      tier: 'P1 self-hosted chat',
      hosts: 'LibreChat + Open WebUI',
      path: 'Streamable HTTP, or bridge where the host requires it',
      proof: 'Conversation-level tool call with user-visible result'
    },
    {
      tier: 'P2 ecosystem',
      hosts: 'LM Studio, Goose, Zed, 5ire, custom hosts',
      path: 'MCP-to-spec with documented caveats',
      proof: 'Do not claim until that host is tested'
    }
  ];

  let copied = $state(false);
  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(url);
      copied = true;
      setTimeout(() => (copied = false), 1400);
    } catch {
      /* noop */
    }
  }
</script>

<svelte:head>
  <title>Connect — Workflow</title>
  <meta name="description" content={t.tagline} />
</svelte:head>

<section class="connect">
  <div class="wrap">
    <RitualLabel color="var(--signal-live)">· User entry · tinyassets.io/mcp ·</RitualLabel>
    <h1 class="title">Connect your MCP.</h1>
    <p class="lead">
      Paste one URL into your MCP-capable chatbot or agent host. Your host can browse the commons, read goals, inspect universes, and route work into the same loop the site shows.
    </p>

    <LiveSourceBar label="Connector proof" detail="Refresh the public MCP route or GitHub source before copying the URL." />

    <div class="card" id="mcp-server-url">
      <div class="card__label">MCP Server URL</div>
      <div class="row">
        <input class="row__input" readonly value={url} aria-label="MCP server URL" />
        <button
          class="row__btn"
          class:copied
          onclick={copyUrl}
          aria-label="Copy MCP URL"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
    </div>

    <div class="protocol">
      <div>
        <RitualLabel color="var(--signal-live)">· What the connector unlocks ·</RitualLabel>
        <h3>Same URL for chatbots and site proof.</h3>
        <p>The refresh controls and your chatbot both point at the same public MCP surface. The difference is only who renders the response.</p>
        <div class="protocol__facts">
          {#each protocolFacts as fact}
            <a href={fact.href}>{fact.label}</a>
          {/each}
        </div>
      </div>
      <pre><code>{requestEnvelope}</code></pre>
    </div>

    <section class="host-coverage" aria-labelledby="host-coverage-title">
      <div class="host-coverage__intro">
        <RitualLabel color="var(--signal-live)">· Customer surface ·</RitualLabel>
        <h2 id="host-coverage-title">Claude and ChatGPT are gates, not the boundary.</h2>
        <p>
          A Workflow user is anyone whose chatbot, IDE agent, local model shell, enterprise agent builder, or custom app can connect to an MCP server. Claude and ChatGPT get first-class launch proof because they are the highest-reach chat surfaces; the rest of the host matrix stays visible instead of being treated as an afterthought.
        </p>
      </div>

      <div class="host-clouds" aria-label="MCP host families">
        <div>
          <span>Launch gates</span>
          <p>{launchHosts.join(' / ')}</p>
        </div>
        <div>
          <span>Builder hosts</span>
          <p>{builderHosts.join(' / ')}</p>
        </div>
        <div>
          <span>Community hosts</span>
          <p>{communityHosts.join(' / ')}</p>
        </div>
      </div>

      <div class="host-table" aria-label="Workflow MCP host support matrix">
        <div class="host-table__head">
          <span>Priority</span>
          <span>Hosts</span>
          <span>MCP path</span>
          <span>Proof</span>
        </div>
        {#each hostRows as row (row.tier)}
          <div class="host-table__row">
            <strong>{row.tier}</strong>
            <span>{row.hosts}</span>
            <span>{row.path}</span>
            <span>{row.proof}</span>
          </div>
        {/each}
      </div>
    </section>

    <div class="steps">
      <a class="step" href="#mcp-server-url">
        <div class="step__num">1</div>
        <div class="step__title">Add it.</div>
        <p class="step__body">
          In your chatbot or agent host, open connector settings and paste the URL. Approve.
        </p>
      </a>
      <a class="step" href="/wiki">
        <div class="step__num">2</div>
        <div class="step__title">Talk.</div>
        <p class="step__body">
          Start a new chat. Say: "browse research-paper branches" or "fork fantasy-novel / claim-first." Your chatbot steers.
        </p>
      </a>
    </div>

    <div class="step-by-step">
      <RitualLabel>How to connect (Claude.ai)</RitualLabel>
      <ol class="ol">
        {#each t.step_by_step as s, i (i)}
          <li>{s}</li>
        {/each}
      </ol>
    </div>
  </div>
</section>

<style>
  .connect { padding-block: 80px; }
  .wrap {
    max-width: 820px;
    margin: 0 auto;
    padding-inline: clamp(16px, 4vw, 32px);
  }
  .title {
    font-family: var(--font-display);
    font-variation-settings: 'opsz' 144, 'SOFT' 50;
    font-size: clamp(48px, 8vw, 80px);
    font-weight: 400;
    letter-spacing: -0.035em;
    line-height: 0.95;
    margin: 20px 0 20px;
  }
  .lead {
    font-size: 18px;
    color: var(--fg-2);
    margin: 0 0 52px;
    line-height: 1.5;
  }
  .card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    padding: 28px;
    margin-bottom: 16px;
  }
  .card__label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 14px;
  }
  .row { display: flex; }
  .row__input {
    flex: 1;
    background: var(--bg-inset);
    color: var(--fg-1);
    border: 1px solid var(--border-1);
    border-right: none;
    border-radius: 8px 0 0 8px;
    padding: 16px 18px;
    font-family: var(--font-mono);
    font-size: 15px;
    outline: none;
  }
  .row__btn {
    background: var(--ember-600);
    color: var(--fg-on-ember);
    border: none;
    padding: 0 28px;
    border-radius: 0 8px 8px 0;
    font-family: var(--font-sans);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    min-width: 130px;
    transition: all 200ms;
  }
  .row__btn.copied {
    background: var(--signal-live);
    color: #0e2b1d;
  }
  @media (max-width: 560px) {
    .row { display: grid; grid-template-columns: 1fr; }
    .row__input {
      min-width: 0;
      border-right: 1px solid var(--border-1);
      border-radius: 8px 8px 0 0;
    }
    .row__btn {
      min-width: 0;
      border-radius: 0 0 8px 8px;
      padding: 12px 16px;
    }
  }
  .steps {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 48px;
  }
  @media (max-width: 600px) {
    .steps { grid-template-columns: 1fr; }
  }
  .step {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 12px;
    color: inherit;
    display: block;
    padding: 24px 26px;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }
  .step:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .step__num {
    font-family: var(--font-display);
    font-size: 48px;
    font-weight: 400;
    color: var(--ember-600);
    line-height: 1;
    font-variation-settings: 'opsz' 144, 'SOFT' 50;
    margin-bottom: 12px;
  }
  .step__title {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--fg-1);
    margin-bottom: 8px;
  }
  .step__body {
    font-size: 14px;
    color: var(--fg-2);
    line-height: 1.55;
    margin: 0;
  }
  .step-by-step ol {
    margin-top: 16px;
    padding-left: 22px;
    color: var(--fg-2);
    font-size: 14px;
    line-height: 1.7;
  }
  .step-by-step ol li { margin-bottom: 6px; }
  .protocol {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    display: grid;
    grid-template-columns: minmax(0, 0.85fr) minmax(0, 1fr);
    gap: 16px;
    margin-bottom: 48px;
    padding: 22px;
  }
  .protocol h3 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: 28px;
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1.05;
    margin: 12px 0 10px;
  }
  .protocol p {
    color: var(--fg-2);
    font-size: 13.5px;
    line-height: 1.6;
    margin: 0 0 14px;
  }
  .protocol pre {
    background: var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    margin: 0;
    overflow-x: auto;
    padding: 14px;
  }
  .protocol code {
    color: var(--fg-1);
    display: block;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.55;
  }
  .protocol__facts {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .protocol__facts a {
    border: 1px solid var(--border-1);
    border-radius: 4px;
    color: var(--fg-2);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    padding: 4px 7px;
    text-decoration: none;
    text-transform: uppercase;
    transition: border-color var(--dur-base) var(--ease-summon), color var(--dur-base) var(--ease-summon);
  }
  .protocol__facts a:hover { border-color: rgba(109, 211, 166, 0.42); color: var(--signal-live); }
  @media (max-width: 760px) {
    .protocol { grid-template-columns: 1fr; }
  }
  .host-coverage {
    border-top: 1px solid var(--border-1);
    margin: 6px 0 48px;
    padding-top: 44px;
  }
  .host-coverage__intro h2 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(30px, 5vw, 48px);
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1;
    margin: 14px 0 14px;
  }
  .host-coverage__intro p {
    color: var(--fg-2);
    font-size: 15px;
    line-height: 1.6;
    margin: 0 0 22px;
  }
  .host-clouds {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-bottom: 16px;
  }
  .host-clouds div {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    padding: 16px;
  }
  .host-clouds span {
    color: var(--fg-3);
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    margin-bottom: 8px;
    text-transform: uppercase;
  }
  .host-clouds p {
    color: var(--fg-1);
    font-size: 13px;
    line-height: 1.55;
    margin: 0;
  }
  .host-table {
    border: 1px solid var(--border-1);
    border-radius: 8px;
    overflow: hidden;
  }
  .host-table__head,
  .host-table__row {
    display: grid;
    grid-template-columns: 0.82fr 1.28fr 1.1fr 1.22fr;
  }
  .host-table__head {
    background: var(--bg-inset);
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .host-table__row {
    background: var(--bg-2);
    color: var(--fg-2);
    font-size: 12.5px;
    line-height: 1.45;
  }
  .host-table__row + .host-table__row {
    border-top: 1px solid var(--border-1);
  }
  .host-table__head span,
  .host-table__row span,
  .host-table__row strong {
    padding: 13px 14px;
  }
  .host-table__row strong {
    color: var(--signal-live);
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
  }
  @media (max-width: 760px) {
    .host-clouds { grid-template-columns: 1fr; }
    .host-table__head { display: none; }
    .host-table__row {
      display: grid;
      gap: 8px;
      padding: 14px;
    }
    .host-table__row span,
    .host-table__row strong {
      padding: 0;
    }
  }
</style>
