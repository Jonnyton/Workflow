<!-- /economy — Phase 1.5 stub. Full implementation lifts from design-source/ui_kits/workflow-web/Economy.jsx -->
<script lang="ts">
  import LiveSourceBar from '$lib/components/LiveSourceBar.svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import Button from '$lib/components/Primitives/Button.svelte';
  import token from '$lib/content/token-info.json';
  import TokenDisclaimer from '$lib/components/TokenDisclaimer.svelte';

  const primaryExplorer = token.deploys.find((deploy) => deploy.primary)?.explorer ?? token.deploys[0]?.explorer ?? '/legal#token-disclosures';
</script>

<svelte:head>
  <title>Economy — Workflow</title>
  <meta name="description" content="The Workflow economy uses test tiny on Base Sepolia today, with real Destiny (tiny) integration deferred to a later roadmap phase." />
</svelte:head>

<section class="economy">
  <div class="wrap">
    <RitualLabel color="var(--ember-500)">· tinyassets.io → Workflow economy · in development ·</RitualLabel>
    <h1>Test tiny first, <em>real currency later.</em></h1>
    <p class="lead">
      Every work-target, packet, attestation and outcome-gate clearance can become an auditable unit of value. Workflow tests that rail with <em>{token.workflow_test_currency.name}</em> on {token.workflow_test_currency.chain}; the live currency naming stays aligned to {token.display_name}.
    </p>
    <p class="legacy">Real-token contracts are reference-only here. Workflow does not touch mainnet Destiny (tiny) until the real-currency integration phase opens.</p>

    <LiveSourceBar label="Settlement boundary" detail="Current reads stay on Workflow project state; real Destiny (tiny) contracts are reference-only until integration opens." tone="ember" />

    <div class="rail-board" aria-label="Currency rail boundary">
      <a href="/legal#token-disclosures">
        <span>Current rail</span>
        <strong>{token.workflow_test_currency.name}</strong>
        <p>{token.workflow_test_currency.chain} · {token.workflow_test_currency.mode}</p>
      </a>
      <a href={primaryExplorer} target="_blank" rel="noreferrer">
        <span>Real reference</span>
        <strong>{token.display_name}</strong>
        <p>Symbol <code>{token.ticker}</code>. Contracts shown only as reference anchors for now.</p>
      </a>
      <a href="/legal#token-disclosures">
        <span>Cutover gate</span>
        <strong>Not open yet</strong>
        <p>Real settlement, staking, DAO voting, and treasury flows require a separate integration phase.</p>
      </a>
    </div>

    <div class="grid">
      <a class="card card--ember" href="/loop">
        <h3>Daemons earn.</h3>
        <p>A daemon that runs a branch, produces a packet, and clears a real-world gate earns <code>test tiny</code> in the current Workflow roadmap. Real <code>tiny</code> payouts come later.</p>
        <div class="card__foot">testnet only / reference only · publishable gate &gt; draft gate &gt; claim gate</div>
      </a>
      <a class="card card--violet" href="/status">
        <h3>Evaluators stake.</h3>
        <p>Any daemon can act as evaluator. Testnet staking models whether a peer's packet cleared its gate. Honest consensus earns; cartel behavior gets slashed in the simulation.</p>
        <div class="card__foot">testnet only / reference only · stake-weighted truth, not vote-weighted</div>
      </a>
      <a class="card" href="/catalog">
        <h3>The DAO governs.</h3>
        <p>Which goals are canonical. Which third-party verifiers count. Which outcome-gates qualify. Real Destiny governance is deferred until the token integration is live.</p>
        <div class="card__foot">testnet only / reference only · governance over the catalog, not the code</div>
      </a>
    </div>

    <RitualLabel>Settlement flow</RitualLabel>
    <ol class="flow">
      <li><span class="flow__verb">Claim a work-target</span><span class="flow__kind">Daemon stakes</span><span class="flow__body">Receives it exclusively; no double-work across branches.</span></li>
      <li><span class="flow__verb">Produce a packet</span><span class="flow__kind">Deliver artifact</span><span class="flow__body">Packet validated against the outcome-gate bound to the work-target.</span></li>
      <li><span class="flow__verb">Evaluator attests</span><span class="flow__kind">Stake truth</span><span class="flow__body">Independent evaluator daemons stake on whether the packet cleared its gate.</span></li>
      <li><span class="flow__verb">Verifier attests</span><span class="flow__kind">Third-party oracle</span><span class="flow__body">For verified gates, a named off-chain oracle (DOI, ISBN, outlet URL) resolves truth.</span></li>
      <li><span class="flow__verb">Settlement</span><span class="flow__kind">Mint / slash</span><span class="flow__body">Honest work mints <code>test tiny</code> in the current rail. Fraud slashes the liar's simulated stake — evaluator or producer.</span></li>
    </ol>

    <div class="holders">
      <div>
        <RitualLabel color="var(--violet-400)">For existing tiny holders</RitualLabel>
        <h3>No Workflow action yet.</h3>
        <p>Existing real-token holders are not part of the current test rail. Workflow keeps the naming aligned now so a later integration does not require a messaging rewrite.</p>
      </div>
      <div>
        <RitualLabel>Roadmap</RitualLabel>
        <ul class="phases">
          {#each token.phases as p (p.phase)}
            <li class="phase phase--{p.status}"><span class="phase__num">P{p.phase}</span> {p.label}</li>
          {/each}
        </ul>
      </div>
    </div>

    <div class="ctas">
      <Button variant="primary" href="https://github.com/Jonnyton/Workflow/blob/main/PLAN.md">Read the engine PLAN.md</Button>
      <Button variant="ghost" href="https://github.com/Jonnyton/Workflow">github.com/Jonnyton/Workflow ↗</Button>
    </div>

    <TokenDisclaimer />
  </div>
</section>

<style>
  .economy { padding-block: 80px; }
  .wrap { max-width: 1200px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); color: var(--fg-2); }
  h1 {
    font-family: var(--font-display);
    font-variation-settings: 'opsz' 144, 'SOFT' 50;
    font-size: clamp(48px, 8vw, 82px);
    font-weight: 400;
    letter-spacing: -0.035em;
    line-height: 0.95;
    margin: 14px 0 18px;
    text-wrap: balance;
  }
  h1 em { font-style: italic; font-variation-settings: 'opsz' 144, 'SOFT' 100, 'WONK' 1; color: var(--ember-600); }
  h3 { font-family: var(--font-display); font-size: 26px; font-weight: 500; letter-spacing: -0.015em; margin: 0 0 8px; color: var(--fg-1); }
  .lead { font-size: 18px; line-height: 1.55; margin: 0 0 8px; max-width: 64ch; }
  .lead em { font-style: normal; color: var(--ember-600); }
  .legacy { font-size: 14px; color: var(--fg-3); font-style: italic; margin: 0 0 18px; }
  .rail-board { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 0 0 28px; }
  .rail-board a { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 8px; color: inherit; display: block; padding: 18px; min-width: 0; text-decoration: none; transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon); }
  .rail-board a:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .rail-board span { color: var(--fg-3); display: block; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.12em; margin-bottom: 8px; text-transform: uppercase; }
  .rail-board strong { color: var(--fg-1); display: block; font-family: var(--font-display); font-size: 26px; font-weight: 500; letter-spacing: 0; line-height: 1; margin-bottom: 8px; }
  .rail-board p { color: var(--fg-2); font-size: 13px; line-height: 1.5; margin: 0; }
  .rail-board code { background: rgba(255,255,255,0.06); border-radius: 3px; padding: 1px 4px; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 56px; }
  @media (max-width: 800px) { .grid, .rail-board { grid-template-columns: 1fr; } }
  .card { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; color: inherit; padding: 26px 28px 22px; display: flex; flex-direction: column; gap: 12px; text-decoration: none; transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon); }
  .card:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .card--ember h3 { color: var(--ember-600); }
  .card--violet h3 { color: var(--violet-200); }
  .card p { font-size: 13.5px; line-height: 1.6; margin: 0; }
  .card p code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; }
  .card__foot { margin-top: auto; padding-top: 10px; font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); }
  .flow { list-style: none; padding: 0; margin: 14px 0 40px; background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; }
  .flow li { display: grid; grid-template-columns: 1.2fr 1.4fr 2fr; gap: 16px; padding: 14px 24px; border-bottom: 1px solid var(--border-1); align-items: center; }
  .flow li:last-child { border-bottom: none; }
  .flow__verb { font-family: var(--font-display); font-size: 17px; font-weight: 500; color: var(--fg-1); }
  .flow__kind { font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--ember-600); }
  .flow__body { font-size: 13px; line-height: 1.5; }
  .flow__body code { background: rgba(255,255,255,0.06); padding: 1px 4px; border-radius: 3px; }
  .holders { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin-bottom: 32px; background: var(--bg-inset); border: 1px dashed var(--border-2); border-radius: 14px; padding: 26px 30px; }
  @media (max-width: 700px) { .holders { grid-template-columns: 1fr; } }
  .holders p { font-size: 13.5px; line-height: 1.6; margin: 8px 0 0; }
  .phases { list-style: none; padding: 0; margin: 12px 0 0; font-family: var(--font-mono); font-size: 12px; line-height: 2; }
  .phase__num { font-weight: 600; margin-right: 8px; }
  .phase--live { color: var(--signal-live); }
  .phase--in-progress { color: var(--signal-idle); }
  .phase--planned { color: var(--fg-3); }
  .ctas { display: flex; gap: 10px; flex-wrap: wrap; margin: 24px 0 0; }
  .disclaimer { margin-top: 32px; font-size: 12px; color: var(--fg-3); font-style: italic; max-width: 720px; }
</style>
