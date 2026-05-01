<!--
  OutcomeGates — landing teaser explaining outcome gates + verified rungs.
  Distills Landing.jsx OUTCOME GATES section without the full ladder visualization.
-->
<script lang="ts">
  import RitualLabel from './Primitives/RitualLabel.svelte';
  import Button from './Primitives/Button.svelte';

  // Demo rungs for the right-side mini-ladder.
  const rungs = [
    { key: 'draft', label: 'Draft committed', state: 'cleared' },
    { key: 'beta', label: 'Beta-read accepted', state: 'cleared' },
    { key: 'submit', label: 'Submitted to venue', state: 'cleared' },
    { key: 'doi', label: 'DOI issued', state: 'pending' },
    { key: 'cited', label: 'Cited (Semantic Scholar)', state: 'planned' },
    { key: 'breakthrough', label: 'Field reframed', state: 'planned' }
  ];
</script>

<section class="gates">
  <div class="container gates__grid">
    <div class="gates__copy">
      <RitualLabel color="var(--violet-400)">· Outcome gates ·</RitualLabel>
      <h2 class="title">Real-world truth, not polish.</h2>
      <p>
        Each goal declares a ladder. Early rungs are personal — draft committed, beta-read accepted, submitted. Final rungs, when they exist, are verified by a named third party: a DOI on doi.org, a byline in a named outlet, an ISBN in a store, citations on Semantic Scholar.
      </p>
      <p>
        Leaderboards rank branches by the <em>highest gate reached</em>, not by judge scores. Personal goals stop wherever you want. Public ones go as far as the real world agrees.
      </p>
      <Button variant="ghost" href="/goals">Browse goals</Button>
    </div>
    <a class="gates__panel" href="/goals" aria-label="Open live goals and outcome gates">
      <div class="panel__head">
        <span class="panel__name">research-paper</span>
        <RitualLabel>Goal · 6 gates</RitualLabel>
      </div>
      <ol class="ladder">
        {#each rungs as r, i (r.key)}
          <li class="rung rung--{r.state}">
            <span class="rung__num">0{i + 1}</span>
            <span class="rung__label">{r.label}</span>
            <span class="rung__state">{r.state === 'cleared' ? '✓' : r.state === 'pending' ? '·' : '○'}</span>
          </li>
        {/each}
      </ol>
    </a>
  </div>
</section>

<style>
  .gates {
    border-top: 1px solid var(--border-1);
    background: var(--bg-0);
  }
  .gates__grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 56px;
    align-items: center;
  }
  @media (max-width: 900px) {
    .gates__grid { grid-template-columns: 1fr; gap: 32px; }
  }
  .title {
    font-family: var(--font-display);
    font-size: clamp(28px, 5vw, 42px);
    font-weight: 500;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin: 16px 0 18px;
  }
  .gates__copy p {
    font-size: 15.5px;
    color: var(--fg-2);
    line-height: 1.6;
    margin: 0 0 14px;
    max-width: 56ch;
  }
  .gates__copy p em { color: var(--ember-600); font-style: normal; font-weight: 600; }
  .gates__panel {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 14px;
    color: inherit;
    display: block;
    padding: 24px 28px;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }
  .gates__panel:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .panel__head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 16px;
  }
  .panel__name {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 500;
    color: var(--fg-1);
  }
  .ladder { list-style: none; padding: 0; margin: 0; }
  .rung {
    display: grid;
    grid-template-columns: 32px 1fr 24px;
    gap: 12px;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid var(--border-1);
  }
  .rung:last-child { border-bottom: none; }
  .rung__num { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); }
  .rung__label { font-size: 13.5px; color: var(--fg-2); }
  .rung__state { text-align: right; font-family: var(--font-mono); font-size: 14px; }
  .rung--cleared .rung__label { color: var(--fg-1); }
  .rung--cleared .rung__state { color: var(--signal-live); }
  .rung--pending .rung__state { color: var(--signal-idle); }
  .rung--planned { opacity: 0.65; }
  .rung--planned .rung__state { color: var(--fg-4); }
</style>
