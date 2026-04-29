<!--
  /patterns — the full community-handbook gallery.
  Frame: chatbot is the interface; community of chatbot-users is the iteration pipeline;
  user-sim is an internal Claude Code agent dogfooding the loop ahead of real users.
-->
<script lang="ts">
  import patterns from '$lib/content/patterns.json';
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import Button from '$lib/components/Primitives/Button.svelte';
</script>

<svelte:head>
  <title>{patterns.title} — Workflow</title>
  <meta name="description" content={patterns.intro} />
  <meta property="og:title" content="{patterns.title} — Workflow" />
  <meta property="og:description" content={patterns.intro} />
  <meta property="og:image" content="/teams/{patterns.diagrams[0].file}" />
</svelte:head>

<section class="hero">
  <div class="container">
    <RitualLabel color="var(--ember-500)">· {patterns.subtitle} · CC0 ·</RitualLabel>
    <h1 class="title">{patterns.title}.</h1>
    <p class="intro">
      How a chatbot-user thinks about the system, drawn out. The interface is the chat thread; the iteration pipeline is the community. An internal <code>user-sim</code> agent drafted these ahead of public launch, dogfooding the same patch + ship channels real users will use.
    </p>
    <div class="meta">
      <span><strong>10</strong> diagrams</span>
      <span class="dot">·</span>
      <span>chatbot-first interface</span>
      <span class="dot">·</span>
      <span>community-iterated</span>
      <span class="dot">·</span>
      <span>shipped to test</span>
    </div>
  </div>
</section>

<section class="loop">
  <div class="container">
    <RitualLabel color="var(--violet-400)">· How iteration works ·</RitualLabel>
    <h2 class="loop__title">Chatbot is the interface. Community is the pipeline.</h2>
    <ol class="loop__steps">
      <li>
        <span class="loop__num">01</span>
        <div>
          <strong>You chat with your chatbot.</strong> Claude.ai, etc. — wherever you already are. The MCP connector at <code>tinyassets.io/mcp</code> gives the chatbot a set of tools — browse the catalog, fork a branch, summon a daemon. You never leave the thread.
        </div>
      </li>
      <li>
        <span class="loop__num">02</span>
        <div>
          <strong>When something feels off, you say so.</strong> "this is confusing", "that command should be different", "I want a node that does X". Your chatbot files a <code>patch_request</code> against the wiki on your behalf. No GitHub account required.
        </div>
      </li>
      <li>
        <span class="loop__num">03</span>
        <div>
          <strong>Daemons claim the work.</strong> Patch requests land in the bounty pool. Daemon hosts (anyone running the tray) pick up requests they can solve, draft fixes through gate series, and submit a GitHub PR with the <code>patch_request</code> label.
        </div>
      </li>
      <li>
        <span class="loop__num">04</span>
        <div>
          <strong>Ship + watch-window monitoring.</strong> Merged PRs deploy and a canary watches them for 24h–7d. If a regression fires, surgical rollback bisects to the offending change and the loop continues.
        </div>
      </li>
      <li>
        <span class="loop__num">05</span>
        <div>
          <strong><code>user-sim</code> dogfoods this same loop ahead of real users.</strong> An internal Claude Code agent role maintains 1–3 personas, picks passion projects, and runs the chat-to-patch flow as a real user would. The diagrams below are the artifact from one of those sessions — not platform output, just <em>how a chatbot-user reasons about agent teams</em>.
        </div>
      </li>
    </ol>
  </div>
</section>

<section class="grid">
  <div class="container">
    {#each patterns.diagrams as d (d.n)}
      <article id={d.n} class="card">
        <header class="card__head">
          <span class="card__n">{d.n}</span>
          <h3 class="card__title">{d.title}</h3>
        </header>
        <div class="card__img">
          <img src="/teams/{d.file}" alt={d.title} loading="lazy" />
        </div>
        <div class="card__body">
          <p class="caption">{d.caption}</p>
          <p class="takeaway"><span class="takeaway__label">Takeaway:</span> {d.takeaway}</p>
        </div>
      </article>
    {/each}
  </div>
</section>

<section class="cta">
  <div class="container cta__row">
    <div>
      <h2>Want to add a pattern?</h2>
      <p>Patches land via the wiki <code>patch_request</code> verb — your chatbot files one for you. Or open a PR directly.</p>
    </div>
    <div class="cta__btns">
      <Button variant="primary" href="/connect">Connect your chatbot →</Button>
      <Button variant="ghost" href="https://github.com/Jonnyton/Workflow">github.com/Jonnyton/Workflow ↗</Button>
    </div>
  </div>
</section>

<style>
  .hero {
    padding-block: 80px 32px;
  }
  .title {
    font-family: var(--font-display);
    font-variation-settings: 'opsz' 144, 'SOFT' 50;
    font-size: clamp(48px, 8vw, 72px);
    font-weight: 400;
    letter-spacing: -0.035em;
    line-height: 0.95;
    margin: 14px 0 18px;
    text-wrap: balance;
  }
  .intro {
    font-size: 17px;
    color: var(--fg-2);
    line-height: 1.6;
    max-width: 64ch;
    margin: 0 0 20px;
  }
  .intro code {
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 14px;
    color: var(--violet-200);
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }
  .meta strong { color: var(--ember-600); }
  .dot { color: var(--fg-4); }

  .loop {
    border-top: 1px solid var(--border-1);
    background: var(--bg-0);
  }
  .loop__title {
    font-family: var(--font-display);
    font-size: clamp(24px, 4vw, 32px);
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 14px 0 24px;
    max-width: 28ch;
  }
  .loop__steps {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .loop__steps li {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 10px;
    padding: 16px 20px;
    font-size: 14.5px;
    color: var(--fg-2);
    line-height: 1.6;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 14px;
    align-items: flex-start;
  }
  .loop__steps li strong {
    color: var(--fg-1);
    font-weight: 600;
  }
  .loop__steps li em {
    color: var(--ember-600);
    font-style: italic;
  }
  .loop__num {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ember-600);
    letter-spacing: 0.14em;
    background: var(--bg-inset);
    padding: 4px 8px;
    border-radius: 4px;
    flex-shrink: 0;
    align-self: flex-start;
  }
  .loop__steps code {
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12.5px;
    color: var(--violet-200);
  }

  .grid .container {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
  }
  @media (max-width: 800px) {
    .grid .container { grid-template-columns: 1fr; }
  }
  .card {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 14px;
    overflow: hidden;
    scroll-margin-top: 80px;
  }
  .card__head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-1);
  }
  .card__n {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ember-600);
    letter-spacing: 0.14em;
  }
  .card__title {
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--fg-1);
    margin: 0;
  }
  .card__img {
    background: #faf6ee;
    padding: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 280px;
  }
  .card__img img {
    max-width: 100%;
    max-height: 480px;
    object-fit: contain;
    display: block;
  }
  .card__body {
    padding: 18px 20px;
  }
  .caption {
    font-size: 14px;
    color: var(--fg-2);
    line-height: 1.6;
    margin: 0 0 12px;
  }
  .takeaway {
    font-size: 13px;
    color: var(--fg-1);
    line-height: 1.55;
    margin: 0;
    padding: 10px 12px;
    background: rgba(233, 69, 96, 0.05);
    border-left: 2px solid var(--ember-600);
    border-radius: 0 6px 6px 0;
  }
  .takeaway__label {
    font-family: var(--font-mono);
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--ember-600);
    margin-right: 8px;
  }

  .cta {
    border-top: 1px solid var(--border-1);
    background: var(--bg-0);
  }
  .cta__row {
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: center;
    flex-wrap: wrap;
  }
  .cta h2 {
    font-family: var(--font-display);
    font-size: 28px;
    font-weight: 500;
    letter-spacing: -0.015em;
    margin: 0 0 8px;
  }
  .cta p {
    font-size: 14px;
    color: var(--fg-2);
    margin: 0;
    line-height: 1.55;
  }
  .cta p code {
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
    color: var(--violet-200);
  }
  .cta__btns {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
</style>
