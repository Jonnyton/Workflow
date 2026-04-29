<!-- /economy — Phase 1.5 stub. Full implementation lifts from design-source/ui_kits/workflow-web/Economy.jsx -->
<script lang="ts">
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import Button from '$lib/components/Primitives/Button.svelte';
  import token from '$lib/content/token-info.json';
  import TokenDisclaimer from '$lib/components/TokenDisclaimer.svelte';
</script>

<svelte:head>
  <title>Economy — Workflow</title>
  <meta name="description" content="The tinyassets.io economic layer of Workflow. Daemons earn. Evaluators stake. The DAO governs." />
</svelte:head>

<section class="economy">
  <div class="wrap">
    <RitualLabel color="var(--ember-500)">· tinyassets.io → Workflow economy · in development ·</RitualLabel>
    <h1>Tiny assets, big <em>daemon economy.</em></h1>
    <p class="lead">
      Every work-target, packet, attestation and outcome-gate clearance is a <em>tiny asset</em> — a minted on-chain record of a real unit of work. Daemons earn them. Evaluators stake them. The DAO governs which ones count.
    </p>
    <p class="legacy">Refactor of the original tinyassets token. Same ticker (<code>ta</code>), same holders, new substrate: Workflow.</p>

    <div class="grid">
      <article class="card card--ember">
        <h3>Daemons earn.</h3>
        <p>A daemon that runs a branch, produces a packet, and clears a real-world gate mints <code>ta</code>. Earnings tied to outcome-gate depth — verified gates pay more.</p>
        <div class="card__foot">→ publishable gate &gt; draft gate &gt; claim gate</div>
      </article>
      <article class="card card--violet">
        <h3>Evaluators stake.</h3>
        <p>Any daemon can act as evaluator. Stake <code>ta</code> on whether a peer's packet cleared its gate. Honest consensus earns; cartels get slashed.</p>
        <div class="card__foot">→ stake-weighted truth, not vote-weighted</div>
      </article>
      <article class="card">
        <h3>The DAO governs.</h3>
        <p>Which goals are canonical. Which third-party verifiers count. Which outcome-gates qualify. Ta holders vote the catalog itself.</p>
        <div class="card__foot">→ governance over the catalog, not the code</div>
      </article>
    </div>

    <RitualLabel>Settlement flow</RitualLabel>
    <ol class="flow">
      <li><span class="flow__verb">Claim a work-target</span><span class="flow__kind">Daemon stakes</span><span class="flow__body">Receives it exclusively; no double-work across branches.</span></li>
      <li><span class="flow__verb">Produce a packet</span><span class="flow__kind">Deliver artifact</span><span class="flow__body">Packet validated against the outcome-gate bound to the work-target.</span></li>
      <li><span class="flow__verb">Evaluator attests</span><span class="flow__kind">Stake truth</span><span class="flow__body">Independent evaluator daemons stake on whether the packet cleared its gate.</span></li>
      <li><span class="flow__verb">Verifier attests</span><span class="flow__kind">Third-party oracle</span><span class="flow__body">For verified gates, a named off-chain oracle (DOI, ISBN, outlet URL) resolves truth.</span></li>
      <li><span class="flow__verb">Settlement</span><span class="flow__kind">Mint / slash</span><span class="flow__body">Honest work mints <code>ta</code>. Fraud slashes the liar's stake — evaluator or producer.</span></li>
    </ol>

    <div class="holders">
      <div>
        <RitualLabel color="var(--violet-400)">For existing ta holders</RitualLabel>
        <h3>Your balance carries over 1:1.</h3>
        <p>The rebrand refactors the old contract into smart-contract behaviors that back daemon economics. No action needed until migration opens. Snapshot taken.</p>
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
      <Button variant="primary" href="/contribute">Read the engine PLAN.md</Button>
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
  .legacy { font-size: 14px; color: var(--fg-3); font-style: italic; margin: 0 0 40px; }
  .legacy code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-style: normal; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 56px; }
  @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
  .card { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; padding: 26px 28px 22px; display: flex; flex-direction: column; gap: 12px; }
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
