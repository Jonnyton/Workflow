<!-- /contribute is a compatibility entry. The contributor path now lives in /loop. -->
<script lang="ts">
  import Button from '$lib/components/Primitives/Button.svelte';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import { compactNumber, createPulse } from '$lib/live/project';

  const pulse = createPulse();
</script>

<svelte:head>
  <title>Contribute moved to the loop - Workflow</title>
  <meta name="description" content="Workflow contribution now happens through the live loop page." />
  <link rel="canonical" href="/loop" />
</svelte:head>

<section class="alias">
  <div class="container">
    <RitualLabel color="var(--signal-live)">· Route merged ·</RitualLabel>
    <h1>Contribute is now part of the loop.</h1>
    <p>The live loop page is the canonical place to watch real project friction move through intake, investigation, gates, branches, release, and observation.</p>
    <div class="counts" aria-label="Current contribution surface counts">
      <article>
        <span>Goals</span>
        <strong>{compactNumber(pulse.mcp.goals.length)}</strong>
      </article>
      <article>
        <span>Wiki pages</span>
        <strong>{compactNumber(pulse.knowledgeCount)}</strong>
      </article>
      <article>
        <span>Branches</span>
        <strong>{compactNumber(pulse.branchCount)}</strong>
      </article>
    </div>
    <Button variant="primary" href="/loop">Open the loop</Button>
  </div>
</section>

<style>
  .alias {
    min-height: 58vh;
    display: grid;
    align-items: center;
    padding-block: 80px;
  }
  h1 {
    max-width: 14ch;
    margin: 14px 0 16px;
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(42px, 7vw, 72px);
    font-weight: 400;
    letter-spacing: 0;
    line-height: 0.98;
  }
  p {
    max-width: 58ch;
    margin: 0 0 24px;
    color: var(--fg-2);
    font-size: 16px;
    line-height: 1.65;
  }
  .counts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin: 0 0 24px;
    max-width: 560px;
  }
  .counts article {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    padding: 14px 16px;
  }
  .counts span {
    color: var(--fg-3);
    display: block;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .counts strong {
    color: var(--fg-1);
    display: block;
    font-family: var(--font-display);
    font-size: 28px;
    font-weight: 500;
    line-height: 1;
    margin-top: 8px;
  }
  @media (max-width: 620px) { .counts { grid-template-columns: 1fr; } }
</style>
