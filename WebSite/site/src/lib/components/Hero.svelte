<!--
  Hero — landing top section. Copy left, ChatDemo right.
  Combines en.json copy with the Landing.jsx structure.
-->
<script lang="ts">
  import strings from '$lib/i18n/en.json';
  import RitualLabel from './Primitives/RitualLabel.svelte';
  import Button from './Primitives/Button.svelte';
  import ChatDemo from './ChatDemo.svelte';

  const t = strings.landing;
</script>

<section class="hero">
  <div class="container hero__grid">
    <div class="hero__copy">
      <RitualLabel color="var(--violet-400)">· Real-world effect engine ·</RitualLabel>
      <h1 class="hero__title">
        <span class="hero__line">Summon the</span>
        <span class="hero__emph">daemon.</span>
      </h1>
      <p class="hero__sub">{t.hero_subtitle}</p>
      <p class="hero__tagline">{t.hero_tagline}</p>
      <div class="hero__ctas">
        <Button variant="primary" size="lg" href="/connect">
          {t.cta_connect} <span class="arrow">→</span>
        </Button>
        <Button variant="secondary" size="lg" href="/host">
          {t.cta_host}
        </Button>
        <Button variant="ghost" size="lg" href="/contribute">
          {t.cta_contribute}
        </Button>
      </div>
      <div class="hero__steps">
        <span><span class="hero__num">1.</span> Paste MCP URL into your chatbot</span>
        <span class="hero__sep">·</span>
        <span><span class="hero__num">2.</span> Run a daemon (desktop or cloud)</span>
        <span class="hero__sep">·</span>
        <span><span class="hero__num">3.</span> Or help build the engine</span>
      </div>
    </div>
    <div class="hero__demo">
      <ChatDemo />
    </div>
  </div>
</section>

<style>
  .hero {
    position: relative;
    padding-block: clamp(56px, 8vw, 100px) clamp(48px, 6vw, 72px);
    overflow: hidden;
  }
  .hero__grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 56px;
    align-items: center;
  }
  @media (max-width: 900px) {
    .hero__grid { grid-template-columns: 1fr; gap: 40px; }
  }
  .hero__title {
    font-family: var(--font-display);
    font-variation-settings: 'opsz' 144, 'SOFT' 50;
    font-size: clamp(48px, 8vw, 84px);
    font-weight: 400;
    line-height: 0.95;
    letter-spacing: -0.035em;
    margin: 22px 0 20px;
    text-wrap: balance;
  }
  .hero__line { display: block; color: var(--fg-1); }
  .hero__emph {
    display: block;
    font-style: italic;
    font-variation-settings: 'opsz' 144, 'SOFT' 100, 'WONK' 1;
    color: var(--ember-600);
    padding-bottom: 8px;
  }
  .hero__sub {
    font-size: 17px;
    line-height: 1.5;
    color: var(--fg-2);
    margin: 0 0 10px;
    max-width: 56ch;
  }
  .hero__tagline {
    font-size: 14px;
    color: var(--fg-3);
    font-style: italic;
    margin: 0 0 32px;
    max-width: 56ch;
  }
  .hero__ctas {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .hero__steps {
    margin-top: 18px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    line-height: 1.8;
  }
  .hero__num { color: var(--ember-600); }
  .hero__sep { padding: 0 6px; }
  .arrow {
    font-family: var(--font-mono);
    opacity: 0.8;
    margin-left: 4px;
  }
</style>
