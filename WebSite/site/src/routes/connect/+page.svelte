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
  const directoryUrl = 'https://tinyassets.io/mcp-directory';
  const requestEnvelope = JSON.stringify(
    {
      full_custom_connector: url,
      directory_review_endpoint: directoryUrl,
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
    { label: 'browse goals', href: '/goals' },
    { label: 'inspect universes', href: '/host' },
    { label: 'proof registry', href: 'https://github.com/Jonnyton/Workflow/blob/main/docs/ops/mcp-host-proof-registry.md', external: true },
    { label: 'AI docs', href: '/llms.txt' }
  ];
  const customerPaths = [
    {
      title: 'App directory',
      status: 'Pending host acceptance',
      account: 'Normal eligible Claude or ChatGPT user. No Developer Mode or custom URL once that host accepts Workflow.',
      setup: 'Find Workflow in the host connector/app directory after acceptance. Until then, use the custom URL path.',
      proof: 'Do not claim listed until Claude directory or ChatGPT App Directory proof is recorded.',
      anchor: '#directory-status'
    },
    {
      title: 'Custom URL today',
      status: 'Live',
      account: 'Use any host that lets you add a custom remote MCP connector. Claude is the best current hosted-chat path.',
      setup: `Paste ${url} into the host connector settings, then enable it in a conversation.`,
      proof: 'The full custom connector endpoint is live; each host still needs fresh user-surface proof before parity claims.',
      anchor: '#mcp-server-url'
    },
    {
      title: 'No chatbot login',
      status: 'Local/self-hosted path',
      account: 'No Claude or ChatGPT login required when you control the host surface.',
      setup: 'Use Open WebUI, LibreChat, LM Studio, Jan, OpenClaw/channel gateways, or a custom MCP host when that path has proof.',
      proof: 'Open WebUI Streamable HTTP is the first verification target; unverified hosts stay labeled compatible-by-spec.',
      anchor: '#host-coverage-title'
    },
    {
      title: 'IDE agents',
      status: 'Builder path',
      account: 'Depends on the IDE host: VS Code/GitHub Copilot, Cursor, Gemini CLI, Cline/Roo, Continue, Windsurf, Replit Agent.',
      setup: 'Use the official MCP Registry path when available, or host-specific MCP config pointed at the canonical URL.',
      proof: 'Each host needs a tool-list plus safe tool-call smoke before public verified copy.',
      anchor: '#host-coverage-title'
    },
    {
      title: 'Workspace admins',
      status: 'One approval for many users',
      account: 'Admin or owner approval may be required for ChatGPT Business/Enterprise/Edu, Claude Team/Enterprise, Mistral, and Copilot Studio.',
      setup: 'Use the submission/admin packet: scopes, safety copy, tests, support path, and proof registry.',
      proof: 'Submission kits are in progress; public claims wait for host approval.',
      anchor: '#host-coverage-title'
    },
    {
      title: 'Custom MCP host',
      status: 'Protocol path',
      account: 'No specific chatbot account required.',
      setup: 'Implement Streamable HTTP MCP client support and run the public canary/smoke prompts against the right endpoint for your use case.',
      proof: 'Compatible by spec until your host is added to the proof registry.',
      anchor: '#host-coverage-title'
    }
  ];
  const launchHosts = ['Claude.ai', 'Claude Desktop', 'Claude mobile', 'ChatGPT Apps', 'ChatGPT developer mode', 'Mistral Le Chat'];
  const builderHosts = ['Codex', 'Gemini CLI', 'VS Code / Copilot', 'Cursor', 'Cline / Roo', 'Continue', 'Windsurf', 'Replit Agent', 'Copilot Studio'];
  const communityHosts = ['LibreChat', 'Open WebUI', 'LM Studio', 'Jan', 'OpenClaw', 'Goose', 'Zed', '5ire', 'custom MCP hosts'];
  const hostRows = [
    {
      tier: 'P0 launch gates',
      hosts: 'Claude + ChatGPT',
      path: 'Directory listing via /mcp-directory once accepted; custom remote MCP fallback at /mcp',
      proof: 'Claude historical proof exists; ChatGPT app/custom MCP blocked by BUG-034/admin path'
    },
    {
      tier: 'P1 registry + builders',
      hosts: 'Official MCP Registry, Codex, Gemini CLI, VS Code, Cursor, Cline/Roo, Continue, Windsurf',
      path: 'Local or remote MCP config',
      proof: 'Registry server.json validates; each host still needs a smoke trace'
    },
    {
      tier: 'P1 self-hosted chat',
      hosts: 'Open WebUI, LibreChat, LM Studio, Jan, OpenClaw',
      path: 'Streamable HTTP, or bridge where the host requires it',
      proof: 'No-login promise starts with Open WebUI verification'
    },
    {
      tier: 'P2 ecosystem and partners',
      hosts: 'Mistral directory, Copilot Studio, Goose, Zed, 5ire, custom hosts',
      path: 'MCP-to-spec with documented caveats',
      proof: 'Do not claim until that host is tested'
    }
  ];
  const gateRows = [
    { label: 'mcp full custom connector', value: 'Live', note: `${url} is the canonical full custom connector for hosts that accept a URL today.` },
    { label: 'mcp-directory review endpoint', value: 'Live, pending host acceptance', note: `${directoryUrl} is the narrowed directory/review endpoint for registry and host submission flows.` },
    { label: 'Claude directory', value: 'Submission pending', note: 'Workflow is not yet accepted in the Claude Connectors Directory. Use custom URL until proof lands.' },
    { label: 'ChatGPT App Directory', value: 'Submission pending', note: 'Workflow is not yet accepted in the ChatGPT App Directory; BUG-034/admin approval still gates public claims.' }
  ];

  let copied = $state(false);
  let copiedDirectory = $state(false);

  async function copyText(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      if (typeof document === 'undefined') return false;
      const textArea = document.createElement('textarea');
      textArea.value = value;
      textArea.setAttribute('readonly', '');
      textArea.style.left = '-9999px';
      textArea.style.opacity = '0';
      textArea.style.position = 'fixed';
      document.body.appendChild(textArea);
      textArea.select();
      try {
        return document.execCommand('copy');
      } finally {
        document.body.removeChild(textArea);
      }
    }
  }

  async function copyUrl() {
    if (await copyText(url)) {
      copied = true;
      setTimeout(() => (copied = false), 1400);
    }
  }

  async function copyDirectoryUrl() {
    if (await copyText(directoryUrl)) {
      copiedDirectory = true;
      setTimeout(() => (copiedDirectory = false), 1400);
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

    <section class="primary-flow" aria-label="Primary connection actions">
      <button type="button" class="flow-card flow-card--copy" class:copied onclick={copyUrl}>
        <span class="flow-card__num">1</span>
        <span class="flow-card__title">Add it.</span>
        <span class="flow-card__body">Copy the MCP URL, paste it into your chatbot connector settings, then approve.</span>
        <span class="flow-card__action">{copied ? 'Copied URL' : 'Copy MCP URL'}</span>
      </button>
      <a class="flow-card" href="/wiki">
        <span class="flow-card__num">2</span>
        <span class="flow-card__title">Talk.</span>
        <span class="flow-card__body">Start a chat and ask Workflow to browse goals, read the wiki, or route work into the loop.</span>
        <span class="flow-card__action">Open live wiki</span>
      </a>
    </section>

    <div class="endpoint-grid">
      <div class="card" id="mcp-server-url">
        <div class="card__label">Full custom connector URL</div>
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
        <p class="endpoint-note">Use this today in custom remote MCP connector settings.</p>
      </div>

      <div class="card" id="directory-status">
        <div class="card__label">Directory / review endpoint</div>
        <div class="row">
          <input class="row__input" readonly value={directoryUrl} aria-label="MCP directory review endpoint" />
          <button
            class="row__btn"
            class:copied={copiedDirectory}
            onclick={copyDirectoryUrl}
            aria-label="Copy MCP directory review endpoint"
          >
            {copiedDirectory ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <p class="endpoint-note">Live for registry and host review. Not a claim that any host directory has accepted Workflow.</p>
      </div>
    </div>

    <LiveSourceBar label="Connector proof" detail="Refresh the public MCP route or GitHub source before copying the URL." />

    <section class="chooser" aria-labelledby="chooser-title">
      <RitualLabel color="var(--signal-live)">· Pick the customer path ·</RitualLabel>
      <h2 id="chooser-title">Connect from the host you already use.</h2>
      <p class="chooser__lead">
        The goal is not to make people understand MCP. The goal is to make Workflow the obvious durable-work tool when their chatbot, IDE, local model UI, or workspace admin needs one.
      </p>

      <div class="path-grid">
        {#each customerPaths as path (path.title)}
          <article class="path-card">
            <div class="path-card__top">
              <h3>{path.title}</h3>
              <span>{path.status}</span>
            </div>
            <dl>
              <div>
                <dt>Login</dt>
                <dd>{path.account}</dd>
              </div>
              <div>
                <dt>Setup</dt>
                <dd>{path.setup}</dd>
              </div>
              <div>
                <dt>Proof</dt>
                <dd>{path.proof}</dd>
              </div>
            </dl>
            <a href={path.anchor}>See path</a>
          </article>
        {/each}
      </div>
    </section>

    <section class="gate-state" aria-labelledby="gate-title">
      <div>
        <RitualLabel color="var(--ember-500)">· Launch truth ·</RitualLabel>
        <h2 id="gate-title">Listings wait for proof.</h2>
      </div>
      <div class="gate-list">
        {#each gateRows as gate (gate.label)}
          <div class="gate-row">
            <strong>{gate.label}</strong>
            <span>{gate.value}</span>
            <p>{gate.note}</p>
          </div>
        {/each}
      </div>
    </section>

    <div class="protocol">
      <div>
        <RitualLabel color="var(--signal-live)">· What the connector unlocks ·</RitualLabel>
        <h3>Same protocol surface, two public entry points.</h3>
        <p>The full connector URL is for users and custom hosts. The directory endpoint is for reviewed listings. Both describe the same Workflow system without claiming a directory listing before proof exists.</p>
        <div class="protocol__facts">
          {#each protocolFacts as fact}
            <a href={fact.href} target={fact.external ? '_blank' : undefined} rel={fact.external ? 'noreferrer' : undefined}>{fact.label}</a>
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

    <div class="step-by-step">
      <RitualLabel>How to connect (Claude.ai)</RitualLabel>
      <ol class="ol">
        {#each t.step_by_step as s, i (i)}
          <li>{s}</li>
        {/each}
      </ol>
    </div>

    <div class="host-notes" id="chatgpt-status">
      <RitualLabel>ChatGPT status</RitualLabel>
      <p>
        ChatGPT guest users cannot connect apps or MCP. Logged-in eligible users and workspaces use Apps, developer mode, or admin-approved custom connectors depending on plan, region, and workspace policy. Workflow is preparing an Apps SDK path, but public ChatGPT claims stay gated until BUG-034 and workspace approval are resolved.
      </p>
    </div>

    <div class="host-notes" id="claude-setup">
      <RitualLabel>Claude status</RitualLabel>
      <p>
        Claude is the best current hosted-chat path for a custom remote MCP connector. Anthropic documents custom remote MCP support across Free, Pro, Max, Team, and Enterprise, with Free users limited to one custom connector. Directory listing work is still separate from custom-URL setup.
      </p>
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
    margin: 0 0 22px;
    line-height: 1.5;
  }
  .primary-flow {
    display: grid;
    gap: 14px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-bottom: 16px;
  }
  .flow-card {
    background:
      linear-gradient(180deg, rgba(109, 211, 166, 0.08), rgba(109, 211, 166, 0.015)),
      var(--bg-2);
    border: 1px solid rgba(109, 211, 166, 0.3);
    border-radius: 8px;
    color: inherit;
    cursor: pointer;
    display: grid;
    gap: 10px;
    min-height: 210px;
    min-width: 0;
    padding: 22px;
    text-align: left;
    text-decoration: none;
    transition:
      background var(--dur-base) var(--ease-summon),
      border-color var(--dur-base) var(--ease-summon),
      transform var(--dur-base) var(--ease-summon);
  }
  .flow-card:hover,
  .flow-card.copied {
    background:
      linear-gradient(180deg, rgba(109, 211, 166, 0.12), rgba(109, 211, 166, 0.035)),
      var(--bg-2);
    border-color: rgba(109, 211, 166, 0.58);
    transform: translateY(-1px);
  }
  .flow-card__num {
    color: var(--ember-600);
    font-family: var(--font-display);
    font-size: 48px;
    font-weight: 400;
    line-height: 0.9;
  }
  .flow-card__title {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: 32px;
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1;
  }
  .flow-card__body {
    color: var(--fg-2);
    font-size: 14px;
    line-height: 1.55;
  }
  .flow-card__action {
    align-self: end;
    color: var(--signal-live);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    padding: 28px;
    margin-bottom: 16px;
  }
  .endpoint-grid {
    display: grid;
    gap: 14px;
    margin-bottom: 14px;
  }
  .endpoint-grid .card {
    margin-bottom: 0;
  }
  .endpoint-note {
    color: var(--fg-3);
    font-size: 12px;
    line-height: 1.5;
    margin: 10px 0 0;
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
    min-width: 0;
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
  .chooser {
    border-top: 1px solid var(--border-1);
    margin: 36px 0 48px;
    padding-top: 44px;
  }
  .chooser h2,
  .gate-state h2 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(30px, 5vw, 48px);
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1;
    margin: 14px 0 12px;
  }
  .chooser__lead {
    color: var(--fg-2);
    font-size: 15px;
    line-height: 1.6;
    margin: 0 0 22px;
  }
  .path-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .path-card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    display: grid;
    gap: 14px;
    padding: 18px;
  }
  .path-card__top {
    display: grid;
    gap: 8px;
  }
  .path-card h3 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: 24px;
    font-weight: 500;
    letter-spacing: 0;
    line-height: 1.05;
    margin: 0;
  }
  .path-card__top span {
    border: 1px solid rgba(109, 211, 166, 0.32);
    border-radius: 4px;
    color: var(--signal-live);
    font-family: var(--font-mono);
    font-size: 10px;
    justify-self: start;
    letter-spacing: 0.08em;
    padding: 4px 7px;
    text-transform: uppercase;
  }
  .path-card dl {
    display: grid;
    gap: 10px;
    margin: 0;
  }
  .path-card dl div {
    display: grid;
    gap: 3px;
  }
  .path-card dt {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .path-card dd {
    color: var(--fg-2);
    font-size: 13px;
    line-height: 1.5;
    margin: 0;
  }
  .path-card a {
    color: var(--fg-1);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .gate-state {
    align-items: start;
    border-top: 1px solid var(--border-1);
    display: grid;
    gap: 18px;
    grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
    margin: 0 0 48px;
    padding-top: 38px;
  }
  .gate-list {
    border: 1px solid var(--border-1);
    border-radius: 8px;
    overflow: hidden;
  }
  .gate-row {
    background: var(--bg-2);
    display: grid;
    gap: 4px;
    grid-template-columns: 0.8fr 0.5fr 1.4fr;
    padding: 13px 14px;
  }
  .gate-row + .gate-row {
    border-top: 1px solid var(--border-1);
  }
  .gate-row strong,
  .gate-row span {
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .gate-row strong {
    color: var(--fg-1);
  }
  .gate-row span {
    color: var(--ember-500);
    text-transform: uppercase;
  }
  .gate-row p {
    color: var(--fg-2);
    font-size: 12.5px;
    line-height: 1.45;
    margin: 0;
  }
  @media (max-width: 760px) {
    .path-grid,
    .gate-state,
    .gate-row {
      grid-template-columns: 1fr;
    }
  }
  .step-by-step ol {
    margin-top: 16px;
    padding-left: 22px;
    color: var(--fg-2);
    font-size: 14px;
    line-height: 1.7;
  }
  .step-by-step ol li { margin-bottom: 6px; }
  .host-notes {
    border-top: 1px solid var(--border-1);
    margin-top: 28px;
    padding-top: 28px;
  }
  .host-notes p {
    color: var(--fg-2);
    font-size: 14px;
    line-height: 1.65;
    margin: 12px 0 0;
  }
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
    .primary-flow {
      grid-template-columns: 1fr;
    }
    .flow-card {
      min-height: 0;
    }
    .host-clouds { grid-template-columns: 1fr; }
    .host-table__head { display: none; }
    .host-table__row {
      display: grid;
      gap: 8px;
      grid-template-columns: 1fr;
      padding: 14px;
    }
    .host-table__row span,
    .host-table__row strong {
      padding: 0;
    }
  }
</style>
