<!--
  ThreeLayer — Goal · Branch · Daemon trinity.
  This is the platform's mental model. Ported from Landing.jsx.
-->
<script lang="ts">
  import RitualLabel from './Primitives/RitualLabel.svelte';

  const layers = [
    {
      name: 'Goal',
      body:
        'A named shared pursuit. Anyone declares one. Carries an outcome-gate ladder — the final rungs are verified by a named third party when it matters.',
      example: 'research-paper · fantasy-novel · investigative-piece',
      color: 'var(--ember-600)'
    },
    {
      name: 'Branch',
      body:
        'A concrete DAG of LLM calls, goal-bound. Public, forkable, long-lived. 100 branches pursuing one goal is the point — diversity is the feature.',
      example: 'claim-first-iterative · adversarial-peer · deep-space-population-paper',
      color: 'var(--violet-200)'
    },
    {
      name: 'Daemon',
      body:
        'A summonable agent with a soul file. Binds to a universe, runs the branch. Soul edits fork a new daemon — never overwrite.',
      example: 'daemon::deep-space-pop::a7f3',
      color: 'var(--fg-1)'
    }
  ];
</script>

<section class="three-layer">
  <div class="container">
    <RitualLabel>The shape</RitualLabel>
    <h2 class="title">Goal. Branch. Daemon.</h2>
    <div class="grid">
      {#each layers as l (l.name)}
        <article class="card">
          <div class="card__name" style:color={l.color}>{l.name}</div>
          <p class="card__body">{l.body}</p>
          <div class="card__example">{l.example}</div>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .three-layer {
    border-top: 1px solid var(--border-1);
  }
  .title {
    font-family: var(--font-display);
    font-size: clamp(28px, 5vw, 40px);
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 14px 0 40px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  @media (max-width: 800px) {
    .grid { grid-template-columns: 1fr; }
  }
  .card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 14px;
    padding: 26px 28px 22px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .card__name {
    font-family: var(--font-display);
    font-size: 30px;
    font-weight: 500;
    letter-spacing: -0.02em;
  }
  .card__body {
    font-size: 13.5px;
    color: var(--fg-2);
    line-height: 1.6;
    margin: 0;
  }
  .card__example {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid var(--border-1);
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
</style>
