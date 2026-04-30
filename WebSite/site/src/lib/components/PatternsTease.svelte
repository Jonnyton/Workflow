<!--
  PatternsTease — landing strip for the community handbook.
  Frame: the chatbot is the interface; real chatbot-users are the iteration pipeline;
  user-sim is an internal Claude Code agent that dogfoods that loop ahead of real users.
-->
<script lang="ts">
  import RitualLabel from './Primitives/RitualLabel.svelte';
  import Button from './Primitives/Button.svelte';
  import patterns from '$lib/content/patterns.json';

  // Three most visually informative for the tease.
  const featured = ['01', '06', '08']
    .map((n) => patterns.diagrams.find((d) => d.n === n))
    .filter((d): d is typeof patterns.diagrams[number] => Boolean(d));
</script>

<section class="patterns">
  <div class="container">
    <div class="head">
      <div>
        <RitualLabel color="var(--ember-500)">· Vol. 1 · community handbook · 10 diagrams · CC0 ·</RitualLabel>
        <h2 class="title">Patterns from the canon.</h2>
        <p class="lead">
          The interface is your chatbot. The iteration pipeline is the community of chatbot-users — files patches, ships fixes, ranks branches by real-world outcome. These ten diagrams are how a chatbot-user thinks about the system; an internal <code>user-sim</code> agent drafted them ahead of public launch by dogfooding the same channels real users will use.
        </p>
        <Button variant="primary" href="/patterns">See all 10 →</Button>
      </div>
    </div>

    <div class="thumbs">
      {#each featured as d (d.n)}
        <a class="thumb" href="/patterns#{d.n}" aria-label={d.title}>
          <div class="thumb__img">
            <img src="/teams/{d.file}" alt={d.title} loading="lazy" />
          </div>
          <div class="thumb__meta">
            <span class="thumb__n">{d.n}</span>
            <span class="thumb__title">{d.title}</span>
          </div>
        </a>
      {/each}
    </div>
  </div>
</section>

<style>
  .patterns {
    border-top: 1px solid var(--border-1);
  }
  .head {
    margin-bottom: 32px;
  }
  .title {
    font-family: var(--font-display);
    font-size: clamp(28px, 5vw, 40px);
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 14px 0 14px;
  }
  .lead {
    font-size: 15.5px;
    color: var(--fg-2);
    line-height: 1.6;
    margin: 0 0 20px;
    max-width: 64ch;
  }
  .lead code {
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 13px;
    color: var(--violet-200);
  }
  .thumbs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
  }
  @media (max-width: 800px) {
    .thumbs { grid-template-columns: 1fr; }
  }
  .thumb {
    text-decoration: none;
    color: inherit;
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 12px;
    overflow: hidden;
    display: block;
    transition: all var(--dur-base) var(--ease-summon);
  }
  .thumb:hover {
    border-color: rgba(233, 69, 96, 0.35);
    box-shadow: var(--glow-ember);
    transform: translateY(-2px);
  }
  .thumb__img {
    background: #faf6ee;
    padding: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 4 / 3;
  }
  .thumb__img img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    display: block;
  }
  .thumb__meta {
    padding: 14px 16px;
    display: flex;
    align-items: baseline;
    gap: 10px;
  }
  .thumb__n {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ember-600);
    letter-spacing: 0.14em;
  }
  .thumb__title {
    font-family: var(--font-display);
    font-size: 16px;
    font-weight: 500;
    color: var(--fg-1);
    letter-spacing: -0.01em;
  }
</style>
