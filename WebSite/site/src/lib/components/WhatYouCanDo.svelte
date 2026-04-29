<!--
  WhatYouCanDo — 8 worked vignettes pulled from en.json.connect.examples.
  The "show, don't just describe" beat that proves real-world utility.
  Categories: Accounting, Research, Writing, Cooking, Legal, Code, Journalism, Email.
-->
<script lang="ts">
  import strings from '$lib/i18n/en.json';
  import RitualLabel from './Primitives/RitualLabel.svelte';

  const examples = strings.connect.examples ?? [];
</script>

<section class="what">
  <div class="container">
    <RitualLabel color="var(--violet-400)">· Real things real people get done ·</RitualLabel>
    <h2 class="title">What you can do.</h2>
    <p class="lead">Eight working vignettes — each one a real prompt and the real outcome a daemon produces. Same shape works for whatever you actually do.</p>

    <div class="grid">
      {#each examples as ex (ex.category)}
        <article class="card">
          <header class="card__head">
            <span class="card__cat">{ex.category}</span>
          </header>
          <div class="card__invoke"><span class="prefix">Workflow:</span>{ex.invocation.replace(/^Workflow:\s*/, '')}</div>
          <p class="card__outcome">{ex.outcome}</p>
        </article>
      {/each}
    </div>
  </div>
</section>

<style>
  .what {
    border-top: 1px solid var(--border-1);
    background: var(--bg-0);
  }
  .title {
    font-family: var(--font-display);
    font-size: clamp(28px, 5vw, 40px);
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 14px 0 14px;
  }
  .lead {
    font-size: 15px;
    color: var(--fg-2);
    margin: 0 0 36px;
    max-width: 64ch;
    line-height: 1.6;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
  }
  @media (max-width: 800px) {
    .grid { grid-template-columns: 1fr; }
  }
  .card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 12px;
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .card__head {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card__cat {
    font-family: var(--font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--ember-600);
    padding: 3px 8px;
    border: 1px solid rgba(233, 69, 96, 0.3);
    border-radius: 999px;
  }
  .card__invoke {
    font-family: var(--font-mono);
    font-size: 12.5px;
    color: var(--fg-1);
    background: var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    padding: 10px 12px;
    line-height: 1.55;
  }
  .prefix {
    color: var(--ember-600);
    margin-right: 6px;
    font-weight: 600;
  }
  .card__outcome {
    font-size: 13.5px;
    color: var(--fg-2);
    line-height: 1.6;
    margin: 0;
  }
</style>
