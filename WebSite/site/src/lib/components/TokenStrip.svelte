<!--
  TokenStrip — tinyassets economy reframe + 3-chain contract addresses.
  Pulls from $lib/content/token-info.json (single source of truth).
-->
<script lang="ts">
  import RitualLabel from './Primitives/RitualLabel.svelte';
  import Button from './Primitives/Button.svelte';
  import token from '$lib/content/token-info.json';
  import TokenDisclaimer from './TokenDisclaimer.svelte';

  let copied: string | null = $state(null);
  async function copyAddr(addr: string) {
    try {
      await navigator.clipboard.writeText(addr);
      copied = addr;
      setTimeout(() => (copied = null), 1400);
    } catch {
      /* noop — fallback could prompt user to copy manually */
    }
  }

  function short(addr: string) {
    return addr.length > 14 ? `${addr.slice(0, 8)}…${addr.slice(-6)}` : addr;
  }
</script>

<section class="token">
  <div class="container">
    <div class="header">
      <div>
        <RitualLabel color="var(--ember-500)">· Economy · on-chain · DAO-governed ·</RitualLabel>
        <h2 class="title">Daemons earn. Evaluators stake. The catalog governs itself.</h2>
        <p class="lead">{token.tagline}</p>
        <p class="legacy">
          Refactor of the original <strong>{token.name}</strong> token. Same ticker (<code>{token.ticker}</code>), same holders, new substrate: Workflow.
        </p>
      </div>
      <div class="cta-col">
        <Button variant="ghost" href="/economy">Read the economy →</Button>
      </div>
    </div>

    <div class="chains">
      {#each token.deploys as d (d.chain)}
        <article class="chain" class:legacy={d.legacy} class:primary={d.primary}>
          <header class="chain__head">
            <span class="chain__name">{d.label}</span>
            {#if d.primary}<span class="badge badge--primary">primary</span>{/if}
            {#if d.legacy}<span class="badge badge--legacy">legacy · 1:1 migration</span>{/if}
          </header>
          <div class="addr">
            <code class="address">{short(d.address_main)}</code>
            <button class="copy" onclick={() => copyAddr(d.address_main)} aria-label="Copy address">
              {copied === d.address_main ? 'Copied' : 'Copy'}
            </button>
          </div>
          {#if d.address_others}
            <div class="addr addr--secondary">
              <span class="addr__label">other:</span>
              <code class="address">{short(d.address_others)}</code>
              <button class="copy copy--ghost" onclick={() => copyAddr(d.address_others)}>
                {copied === d.address_others ? 'Copied' : 'Copy'}
              </button>
            </div>
          {/if}
          <div class="links">
            <a class="link" href={d.explorer} target="_blank" rel="noreferrer">Explorer ↗</a>
            {#if d.bridge}
              <span class="meta">Bridge: {d.bridge}</span>
            {/if}
            {#if d.buy}
              <a class="link" href={d.buy} target="_blank" rel="noreferrer">Buy ↗</a>
            {/if}
            {#if d.migration}
              <a class="link" href={d.migration} target="_blank" rel="noreferrer">{d.migration_note} ↗</a>
            {/if}
          </div>
        </article>
      {/each}
    </div>

    <div class="phases">
      <RitualLabel>Roadmap</RitualLabel>
      <div class="phases__row">
        {#each token.phases as p (p.phase)}
          <div class="phase phase--{p.status}">
            <span class="phase__num">P{p.phase}</span>
            <span class="phase__label">{p.label}</span>
          </div>
        {/each}
      </div>
    </div>

    <TokenDisclaimer compact={true} />
  </div>
</section>

<style>
  .token {
    border-top: 1px solid var(--border-1);
    background: var(--bg-0);
  }
  .header {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 24px;
    align-items: end;
    margin-bottom: 36px;
  }
  @media (max-width: 800px) {
    .header { grid-template-columns: 1fr; align-items: start; }
  }
  .title {
    font-family: var(--font-display);
    font-size: clamp(24px, 4vw, 30px);
    font-weight: 500;
    letter-spacing: -0.015em;
    margin: 10px 0 10px;
  }
  .lead {
    font-size: 14px;
    color: var(--fg-2);
    line-height: 1.6;
    margin: 0 0 6px;
    max-width: 60ch;
  }
  .legacy {
    font-size: 12px;
    color: var(--fg-3);
    font-style: italic;
    margin: 0;
  }
  .legacy code {
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 5px;
    border-radius: var(--radius-xs);
    font-style: normal;
  }
  .chains {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 28px;
  }
  @media (max-width: 800px) {
    .chains { grid-template-columns: 1fr; }
  }
  .chain {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 12px;
    padding: 18px 18px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .chain.primary { border-color: rgba(233, 69, 96, 0.3); }
  .chain.legacy { opacity: 0.85; }
  .chain__head { display: flex; align-items: center; gap: 8px; }
  .chain__name {
    font-family: var(--font-display);
    font-size: 18px;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--fg-1);
  }
  .badge {
    font-family: var(--font-mono);
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    padding: 2px 7px;
    border-radius: 999px;
  }
  .badge--primary { background: rgba(233,69,96,0.15); color: var(--ember-500); }
  .badge--legacy { background: rgba(255,255,255,0.06); color: var(--fg-3); }
  .addr {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .addr--secondary { font-size: 11px; }
  .addr__label {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  .address {
    flex: 1;
    background: var(--bg-inset);
    border: 1px solid var(--border-1);
    padding: 6px 10px;
    border-radius: 6px;
    color: var(--violet-200);
  }
  .copy {
    background: var(--ember-600);
    color: var(--fg-on-ember);
    border: none;
    padding: 6px 10px;
    border-radius: 6px;
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
  }
  .copy:hover { background: var(--ember-500); }
  .copy--ghost {
    background: transparent;
    color: var(--fg-2);
    border: 1px solid var(--border-1);
  }
  .copy--ghost:hover { background: rgba(255,255,255,0.05); }
  .links {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 14px;
    align-items: center;
    font-size: 11.5px;
    margin-top: 4px;
  }
  .link {
    color: var(--ember-600);
    text-decoration: none;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 10.5px;
  }
  .link:hover { text-decoration: underline; }
  .meta {
    color: var(--fg-3);
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .phases__row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 12px;
  }
  .phase {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--border-1);
    border-radius: 8px;
    background: rgba(255,255,255,0.02);
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .phase--live { border-color: rgba(109,211,166,0.3); color: var(--signal-live); }
  .phase--in-progress { border-color: rgba(217,168,74,0.3); color: var(--signal-idle); }
  .phase--planned { color: var(--fg-3); }
  .phase__num { font-weight: 600; }
  .phase__label { color: var(--fg-2); }

  .disclaimer {
    margin-top: 28px;
    font-size: 11.5px;
    color: var(--fg-3);
    font-style: italic;
    max-width: 680px;
  }
</style>
