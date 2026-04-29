<!--
  Footer — bottom chrome.
  Adds legal link, socials placeholder, supply ticker, alliance link.
-->
<script lang="ts">
  import SigilMark from './SigilMark.svelte';
  import RitualLabel from './Primitives/RitualLabel.svelte';
  import legal from '$lib/content/legal-info.json';

  const year = new Date().getFullYear();

  const socials = [
    { name: 'GitHub', href: 'https://github.com/Jonnyton/Workflow' },
    { name: 'X', href: 'https://x.com/' },
    { name: 'YouTube', href: 'https://youtube.com/' },
    { name: 'LinkedIn', href: 'https://linkedin.com/' },
    { name: 'Discord', href: 'https://discord.com/' }
  ];
</script>

<footer class="footer">
  <div class="container footer__row">
    <div class="brand">
      <SigilMark size={22} />
      <span class="brand__name">Workflow</span>
      <span class="brand__sub">at <a href="/">tinyassets.io</a></span>
    </div>
    <RitualLabel>· MIT + CC0 · concept-public · instance-private · {legal.review_status.split('—')[0].trim()} ·</RitualLabel>
  </div>

  <div class="container footer__grid">
    <div class="col">
      <RitualLabel>Use</RitualLabel>
      <ul>
        <li><a href="/connect">Connect</a></li>
        <li><a href="/host">Host a daemon</a></li>
        <li><a href="/contribute">Contribute</a></li>
        <li><a href="/alliance">Tiny Alliance</a></li>
      </ul>
    </div>
    <div class="col">
      <RitualLabel>Browse</RitualLabel>
      <ul>
        <li><a href="/wiki">Live wiki</a></li>
        <li><a href="/graph">Graph</a></li>
        <li><a href="/patterns">Patterns</a></li>
        <li><a href="/economy">Economy</a></li>
      </ul>
    </div>
    <div class="col">
      <RitualLabel>Build</RitualLabel>
      <ul>
        <li><a href="https://tinyassets.io/mcp" target="_blank" rel="noreferrer">MCP gateway ↗</a></li>
        <li><a href="https://github.com/Jonnyton/Workflow" target="_blank" rel="noreferrer">GitHub ↗</a></li>
        <li><a href="https://github.com/Jonnyton/Workflow/blob/main/PLAN.md" target="_blank" rel="noreferrer">PLAN.md ↗</a></li>
        <li><a href="https://github.com/Jonnyton/Workflow/blob/main/CONTRIBUTING.md" target="_blank" rel="noreferrer">CONTRIBUTING.md ↗</a></li>
      </ul>
    </div>
    <div class="col">
      <RitualLabel>Legal</RitualLabel>
      <ul>
        <li><a href="/legal">Terms &amp; privacy</a></li>
        <li><a href="/legal#token-disclosures">Token disclosures</a></li>
        <li><a href="/legal#risk-factors">Risk factors</a></li>
        <li><a href="/legal#dmca">DMCA</a></li>
      </ul>
    </div>
  </div>

  <div class="container footer__supply">
    <RitualLabel color="var(--ember-500)">Tiny Assets · ta · multi-chain</RitualLabel>
    <span class="supply">Total supply 12,344,744,965</span>
    <span class="supply__chains">BASE · PulseChain · BSC</span>
    <a class="supply__more" href="/economy">All chains →</a>
  </div>

  <div class="container footer__socials">
    {#each socials as s}
      <a href={s.href} target="_blank" rel="noreferrer">{s.name}</a>
    {/each}
  </div>

  <div class="container footer__bottom">
    <span class="copyright">© {year} Tiny Assets · All rights reserved.</span>
    <span class="contact">
      <a href="mailto:{legal.contact.general}">{legal.contact.general}</a> ·
      <a href="mailto:{legal.contact.security}">{legal.contact.security}</a>
    </span>
  </div>
</footer>

<style>
  .footer {
    border-top: 1px solid var(--border-1);
    background: var(--bg-inset);
    padding-block: var(--s-8) var(--s-5);
    margin-top: var(--s-12);
  }
  .footer__row { display: flex; flex-wrap: wrap; gap: 18px; align-items: center; justify-content: space-between; padding-bottom: var(--s-5); border-bottom: 1px solid var(--border-1); }
  .brand { display: flex; align-items: center; gap: 10px; }
  .brand__name { font-family: var(--font-display); font-size: 16px; color: var(--fg-1); font-weight: 600; }
  .brand__sub { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); }
  .brand__sub a { color: var(--fg-2); text-decoration: none; }

  .footer__grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; padding: var(--s-6) 0; border-bottom: 1px solid var(--border-1); }
  @media (max-width: 700px) { .footer__grid { grid-template-columns: repeat(2, 1fr); } }
  .col ul { list-style: none; padding: 0; margin: 12px 0 0; display: flex; flex-direction: column; gap: 8px; }
  .col li a { color: var(--fg-2); text-decoration: none; font-size: 13px; }
  .col li a:hover { color: var(--ember-600); }

  .footer__supply { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: var(--s-5) 0; border-bottom: 1px solid var(--border-1); }
  .supply { font-family: var(--font-mono); font-size: 12px; color: var(--fg-1); }
  .supply__chains { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.14em; }
  .supply__more { margin-left: auto; color: var(--ember-600); text-decoration: none; font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; }
  .supply__more:hover { text-decoration: underline; }

  .footer__socials { display: flex; gap: 16px; flex-wrap: wrap; padding: var(--s-5) 0; border-bottom: 1px solid var(--border-1); font-family: var(--font-mono); font-size: 12px; }
  .footer__socials a { color: var(--fg-2); text-decoration: none; }
  .footer__socials a:hover { color: var(--ember-600); }

  .footer__bottom { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: var(--s-4); font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); }
  .contact a { color: var(--fg-2); text-decoration: none; }
  .contact a:hover { color: var(--ember-600); }
</style>
