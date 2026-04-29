<!-- TopNav — sticky-translucent. Active route gets ember underline. Mobile hamburger drawer. -->
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

  let drawerOpen = $state(false);

  function isActive(path: string, href: string): boolean {
    if (href === '/') return path === '/';
    return path === href || path.startsWith(href + '/');
  }

  function close() { drawerOpen = false; }
</script>

<header class="top">
  <div class="container top__row">
    <a class="brand" href="/" aria-label="Workflow home" onclick={close}>
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
    <button
      class="hamburger"
      class:open={drawerOpen}
      aria-label={drawerOpen ? 'Close menu' : 'Open menu'}
      aria-expanded={drawerOpen}
      onclick={() => (drawerOpen = !drawerOpen)}
    >
      <span></span><span></span><span></span>
    </button>
  </div>
</header>

{#if drawerOpen}
  <div class="drawer" role="dialog" aria-label="Site navigation">
    <nav aria-label="Mobile primary">
      <a href="/" class="drawer__item" class:active={isActive(page.url.pathname, '/')} onclick={close}>Home</a>
      {#each items as it (it.href)}
        <a href={it.href} class="drawer__item" class:active={isActive(page.url.pathname, it.href)} onclick={close}>{it.label}</a>
      {/each}
    </nav>
    <div class="drawer__cta">
      <Button variant="primary" href="/connect" onclick={close}>Summon a daemon →</Button>
    </div>
  </div>
{/if}

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

  /* Hamburger — only at narrow widths */
  .hamburger { display: none; flex-direction: column; gap: 4px; background: transparent; border: 1px solid var(--border-1); padding: 8px 9px; border-radius: 6px; cursor: pointer; }
  .hamburger span { display: block; width: 18px; height: 2px; background: var(--fg-1); border-radius: 2px; transition: transform 0.18s ease, opacity 0.18s ease; }
  .hamburger.open span:nth-child(1) { transform: translateY(6px) rotate(45deg); }
  .hamburger.open span:nth-child(2) { opacity: 0; }
  .hamburger.open span:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }
  @media (max-width: 1000px) {
    .hamburger { display: flex; }
    .cta { display: none; }
  }

  /* Drawer */
  .drawer { position: sticky; top: 56px; z-index: 49; background: var(--bg-1); border-bottom: 1px solid var(--border-1); padding: 12px clamp(16px, 4vw, 24px) 18px; box-shadow: 0 8px 24px rgba(0,0,0,0.35); display: none; }
  @media (max-width: 1000px) { .drawer { display: block; } }
  .drawer nav { display: flex; flex-direction: column; gap: 2px; }
  .drawer__item { display: block; padding: 10px 12px; border-radius: 6px; text-decoration: none; color: var(--fg-2); font-family: var(--font-sans); font-size: 15px; font-weight: 500; }
  .drawer__item:hover { background: var(--bg-2); color: var(--fg-1); }
  .drawer__item.active { color: var(--ember-600); background: var(--bg-2); }
  .drawer__cta { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-1); }
</style>
