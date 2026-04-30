<!--
  WhyWorkflow — four-up reason cards.
  Pulls from en.json.landing.why_points.
-->
<script lang="ts">
  import strings from '$lib/i18n/en.json';
  import RitualLabel from './Primitives/RitualLabel.svelte';

  const points = [
    {
      title: 'Real execution.',
      body: "A daemon actually runs your branch. The chatbot steers. It doesn't pretend.",
      href: '/host'
    },
    {
      title: 'Remix-first.',
      body:
        'Fork any branch. Edit its prompt templates, node graph, or rigor checks. Lineage preserved.',
      href: '/graph'
    },
    {
      title: 'Outcome-gated.',
      body:
        'Ranking is driven by real-world gates, not judge polish. Third-party verification where it counts.',
      href: '/catalog'
    },
    {
      title: 'Your data stays yours.',
      body:
        'Per-piece privacy judged by your chatbot. Concept-layer public, instance-layer private, never training data.',
      href: '/legal'
    }
  ];
</script>

<section class="why">
  <div class="container">
    <RitualLabel>Why Workflow?</RitualLabel>
    <div class="grid">
      {#each points as p (p.title)}
        <a class="card" href={p.href} aria-label={`Open source for ${p.title}`}>
          <div class="card__title">{p.title}</div>
          <p class="card__body">{p.body}</p>
        </a>
      {/each}
    </div>
  </div>
</section>

<style>
  .why {
    border-top: 1px solid var(--border-1);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-top: 18px;
  }
  @media (max-width: 700px) {
    .grid { grid-template-columns: 1fr; }
  }
  .card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 12px;
    color: inherit;
    padding: 24px 26px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    text-decoration: none;
    transition: border-color var(--dur-base) var(--ease-summon), background var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon);
  }
  .card:hover { border-color: rgba(109, 211, 166, 0.42); background: rgba(109, 211, 166, 0.045); transform: translateY(-1px); }
  .card__title {
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--fg-1);
  }
  .card__body {
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--fg-2);
    margin: 0;
  }
</style>
