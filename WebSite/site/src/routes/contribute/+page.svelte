<!-- /contribute — Phase 1.5 ship: hero + clone CTAs + 4-step quick start + threads + admin pool. -->
<script lang="ts">
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import Button from '$lib/components/Primitives/Button.svelte';
</script>

<svelte:head>
  <title>Contribute — Workflow</title>
  <meta name="description" content="Open-source. MIT + CC0. Clone the engine, ship a branch, vibe-code with us." />
</svelte:head>

<section class="hero">
  <div class="container">
    <div class="hero__grid">
      <div>
        <RitualLabel color="var(--violet-400)">· Open source · MIT + CC0 · legion of builders ·</RitualLabel>
        <h1>Summon a daemon. <em>Vibe-code with us.</em></h1>
        <p class="lead">The engine is a living Python monorepo. Clone it. Run your own host. Ship a branch back. Soul files preserve your lineage — your daemon was <em>yours</em>, and the commit remembers.</p>
        <p class="legacy">Platform: MIT. Catalog (goals, gates, prompts): CC0. Fork either.</p>
        <div class="ctas">
          <Button variant="primary" href="https://github.com/Jonnyton/Workflow" >github.com/Jonnyton/Workflow ↗</Button>
          <Button variant="ghost" href="https://github.com/Jonnyton/Workflow/blob/main/PLAN.md">Read PLAN.md ↗</Button>
          <Button variant="ghost" href="https://github.com/Jonnyton/Workflow/blob/main/CONTRIBUTING.md">CONTRIBUTING.md ↗</Button>
        </div>
      </div>
      <aside class="repo-card">
        <RitualLabel>Workflow · main</RitualLabel>
        <div class="repo__stat"><span class="repo__num">1</span><span class="repo__label">contributor</span></div>
        <div class="repo__stat"><span class="repo__num">47</span><span class="repo__label">wiki pages</span></div>
        <div class="repo__stat"><span class="repo__num">34</span><span class="repo__label">filed bugs</span></div>
        <div class="repo__stat"><span class="repo__num">4</span><span class="repo__label">live goals</span></div>
        <div class="repo__sla">
          <span>48h</span><span>first response</span>
        </div>
        <div class="repo__sla">
          <span>5d</span><span>full review</span>
        </div>
      </aside>
    </div>
  </div>
</section>

<section class="quickstart">
  <div class="container">
    <RitualLabel>Quick start · local dev</RitualLabel>
    <h2>Four commands to a live daemon.</h2>
    <p class="lead">Poetry-managed under the hood; tests run offline (no API keys needed). The daemon you run locally is the same code that ships in the desktop host.</p>
    <div class="qs-grid">
      <div class="qs-steps">
        <div class="qs-step"><span class="qs-num">1</span> Clone the monorepo.</div>
        <div class="qs-step"><span class="qs-num">2</span> <code>pip install -e .[dev]</code> — one shot.</div>
        <div class="qs-step"><span class="qs-num">3</span> <code>pytest -q</code> — full suite, offline, no keys.</div>
        <div class="qs-step"><span class="qs-num">4</span> Bind a sandbox universe and summon your first daemon.</div>
      </div>
      <pre><code>git clone https://github.com/Jonnyton/Workflow.git
cd Workflow
python -m venv .venv
source .venv/bin/activate    # win: .venv\Scripts\activate
pip install -e .[dev]
pytest -q                    # runs offline
ruff check                   # lints clean

# Bind + summon
python -m fantasy_daemon</code></pre>
    </div>
  </div>
</section>

<section class="threads">
  <div class="container">
    <div class="threads__head">
      <div>
        <RitualLabel color="var(--ember-500)">· Threads · help-wanted ·</RitualLabel>
        <h2>Pick a thread. Ship a fix.</h2>
        <p>Every wiki bug is a <code>patch_request</code> waiting to be claimed. Some are 30-minute fixes; some are architectural arcs. Read PLAN.md, pick what fits.</p>
      </div>
      <Button variant="ghost" href="/wiki">Browse the live wiki →</Button>
    </div>
    <div class="threads__grid">
      {#each [
        { kind: 'good first issue', title: 'BUG-013 — file_feature_request wiki verb', size: 'small', tag: 'good first issue' },
        { kind: 'plan', title: 'Validated state transitions (fixes Cluster A + B)', size: 'arc', tag: 'cluster A · primitive #1' },
        { kind: 'plan', title: 'Sub-branch invocation primitive (BUG-005)', size: 'arc', tag: 'primitive #4' },
        { kind: 'good first issue', title: 'BUG-019 — conditional_edges to END throws KeyError', size: 'small', tag: 'router' },
        { kind: 'plan', title: 'Execution-surface primitive (BUG-017)', size: 'arc', tag: 'primitive #3' },
        { kind: 'good first issue', title: 'BUG-020 — long-poll mode for chatbot tool budget', size: 'medium', tag: 'UX' }
      ] as t}
        <article class="thread thread--{t.size}">
          <span class="thread__kind">{t.kind}</span>
          <h3>{t.title}</h3>
          <span class="thread__tag">{t.tag}</span>
        </article>
      {/each}
    </div>
  </div>
</section>

<section class="admin">
  <div class="container">
    <RitualLabel>Review SLA</RitualLabel>
    <h2>48 hours, then 5 days, then merge.</h2>
    <p>First response within 48 hours. Full review within 5 calendar days. If we miss, escalate via <code>@maintainers</code> on the PR or email <a href="mailto:security@tinyassets.io">security@tinyassets.io</a>.</p>
    <p>Admin pool currently size 1 (host) + co-maintainer recruitment open. Drive-by reviews welcome and weighted in the maintainer-health dashboard. The forever-rule: <em>Workflow is always up, always downloadable, always reviewable.</em> Contributors make the third clause real.</p>
  </div>
</section>

<style>
  .hero, .quickstart, .threads, .admin { padding-block: 56px; border-top: 1px solid var(--border-1); }
  .hero { padding-top: 80px; border-top: none; }
  h1 { font-family: var(--font-display); font-size: clamp(44px, 7vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.98; margin: 14px 0 18px; text-wrap: balance; }
  h1 em { font-style: italic; font-variation-settings: 'opsz' 144, 'SOFT' 100, 'WONK' 1; color: var(--ember-600); }
  h2 { font-family: var(--font-display); font-size: clamp(28px, 5vw, 38px); font-weight: 500; letter-spacing: -0.02em; margin: 14px 0 18px; line-height: 1.05; }
  h3 { font-family: var(--font-display); font-size: 17px; font-weight: 500; letter-spacing: -0.01em; color: var(--fg-1); margin: 6px 0 10px; line-height: 1.3; }
  .lead { font-size: 16px; line-height: 1.6; color: var(--fg-2); margin: 0 0 16px; max-width: 56ch; }
  .legacy { font-size: 13px; color: var(--fg-3); font-style: italic; margin: 0 0 24px; }
  .ctas { display: flex; gap: 10px; flex-wrap: wrap; }

  .hero__grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 48px; align-items: start; }
  @media (max-width: 900px) { .hero__grid { grid-template-columns: 1fr; gap: 32px; } }
  .repo-card { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; padding: 22px 24px; }
  .repo__stat { display: flex; align-items: baseline; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-1); }
  .repo__stat:last-of-type { border-bottom: none; }
  .repo__num { font-family: var(--font-display); font-size: 28px; font-weight: 500; color: var(--ember-600); min-width: 50px; }
  .repo__label { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.1em; }
  .repo__sla { display: flex; gap: 12px; margin-top: 12px; padding: 8px 12px; background: var(--bg-inset); border-radius: 6px; align-items: baseline; }
  .repo__sla span:first-child { font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--violet-200); }
  .repo__sla span:last-child { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.1em; }

  .qs-grid { display: grid; grid-template-columns: 1fr 1.3fr; gap: 32px; align-items: start; }
  @media (max-width: 800px) { .qs-grid { grid-template-columns: 1fr; } }
  .qs-steps { display: flex; flex-direction: column; gap: 8px; }
  .qs-step { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: center; padding: 10px 14px; background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 8px; font-size: 14px; color: var(--fg-2); }
  .qs-num { font-family: var(--font-mono); font-size: 11px; color: var(--ember-600); letter-spacing: 0.14em; background: var(--bg-inset); padding: 3px 8px; border-radius: 4px; }
  .qs-step code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 12.5px; color: var(--violet-200); }
  pre { background: var(--bg-inset); border: 1px solid var(--border-1); padding: 16px; border-radius: 10px; overflow-x: auto; margin: 0; }
  pre code { font-family: var(--font-mono); font-size: 12.5px; color: var(--fg-1); display: block; line-height: 1.6; }

  .threads__head { display: flex; justify-content: space-between; align-items: end; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; }
  .threads p { font-size: 14px; color: var(--fg-2); line-height: 1.6; margin: 0; max-width: 56ch; }
  .threads p code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 12px; color: var(--violet-200); }
  .threads__grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  @media (max-width: 800px) { .threads__grid { grid-template-columns: 1fr; } }
  .thread { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 12px; padding: 18px 20px; }
  .thread--small { border-color: rgba(109,211,166,0.2); }
  .thread--arc { border-color: rgba(138,99,206,0.25); }
  .thread__kind { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--ember-600); }
  .thread--arc .thread__kind { color: var(--violet-400); }
  .thread__tag { font-family: var(--font-mono); font-size: 10px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.1em; }

  .admin p { font-size: 14.5px; line-height: 1.7; margin: 0 0 14px; max-width: 64ch; }
  .admin p code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 12.5px; color: var(--violet-200); }
  .admin p em { color: var(--fg-1); font-style: italic; }
  .admin a { color: var(--ember-600); text-decoration: none; }
  .admin a:hover { text-decoration: underline; }
</style>
