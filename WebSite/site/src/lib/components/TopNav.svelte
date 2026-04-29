<!-- TopNav — sticky-translucent. Active route gets ember underline. -->
<script lang="ts">
  import { page } from '$app/state';
  import SigilMark from './SigilMark.svelte';
  import Button from './Primitives/Button.svelte';

  const items = [
    { href: '/connect', label: 'Connect' },
    { href: '/wiki', label: 'Wiki' },
    { href: '/graph', label: 'Graph' },
    { href: '/patterns', label: 'Patterns' },
    { href: '/host', label: 'Host' },
    { href: '/contribute', label: 'Contribute' },
    { href: '/alliance', label: 'Alliance' }
  ];

  function isActive(path: string, href: string): boolean {
    if (href === '/') return path === '/';
    return path === href || path.startsWith(href + '/');
  }
</script>

<header class="top">
  <div class="container top__row">
    <a class="brand" href="/" aria-label="Workflow home">
      <SigilMark size={28} />
      <span class="brand__name">Workflow</span>
    </a>
    <nav class="nav" aria-label="Primary">
      {#each items as it (it.href)}
        <a href={it.href} class="nav__item" class:active={isActive(page.url.pathname, it.href)}>{it.label}</a>
      {/each}
    </nav>
    <div class="cta">
      <Button variant="primary" size="sm" href="/connect">Summon a daemon <span class="arrow">→</span></Button>
    </div>
  </div>
</header>

<style>
  .top { position: sticky; top: 0; z-index: 50; background: rgba(14, 14, 26, 0.72); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-1); }
  .top__row { display: flex; align-items: center; justify-content: space-between; padding-block: 14px; gap: 16px; }
  .brand { display: flex; align-items: center; gap: 10px; text-decoration: none; }
  .brand__name { font-family: var(--font-display); font-size: 18px; font-weight: 600; letter-spacing: -0.01em; color: var(--fg-1); }
  .nav { display: flex; gap: 2px; }
  @media (max-width: 1000px) { .nav { display: none; } }
  .nav__item { font-family: var(--font-sans); font-size: 13px; font-weight: 500; color: var(--fg-2); background: transparent; text-decoration: none; padding: 8px 12px; border-radius: 6px; position: relative; transition: color var(--dur-fast) var(--ease-standard); }
  .nav__item:hover { color: var(--fg-1); }
  .nav__item.active { color: var(--ember-600); }
  .nav__item.active::after { content: ''; position: absolute; left: 12px; right: 12px; bottom: 2px; height: 1px; background: var(--ember-600); }
  .arrow { font-family: var(--font-mono); opacity: 0.7; }
</style>
