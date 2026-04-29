<!--
  /connect — radical simplicity. Add the connector. Then talk.
  Ported from design-source/ui_kits/workflow-web/Connect.jsx.
-->
<script lang="ts">
  import strings from '$lib/i18n/en.json';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';

  const t = strings.connect;
  const url = t.mcp_url; // https://api.tinyassets.io/mcp from en.json (note: per spec the canonical apex is tinyassets.io/mcp — verify)

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
    <RitualLabel color="var(--violet-400)">· Zero install · two steps ·</RitualLabel>
    <h1 class="title">Add the connector. Then talk.</h1>
    <p class="lead">
      Paste one URL into your chatbot's connector settings. That's it. Your chatbot can now browse goals, fork branches, and summon daemons — just ask it to.
    </p>

    <div class="card">
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

    <div class="steps">
      <article class="step">
        <div class="step__num">1</div>
        <div class="step__title">Add it.</div>
        <p class="step__body">
          In your chatbot (Claude.ai, etc.), open connector settings and paste the URL. Approve.
        </p>
      </article>
      <article class="step">
        <div class="step__num">2</div>
        <div class="step__title">Talk.</div>
        <p class="step__body">
          Start a new chat. Say: "browse research-paper branches" or "fork fantasy-novel / claim-first." Your chatbot steers.
        </p>
      </article>
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
    border-radius: 14px;
    padding: 28px;
    margin-bottom: 48px;
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
    padding: 24px 26px;
  }
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
</style>
