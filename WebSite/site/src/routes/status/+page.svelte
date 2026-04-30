<!-- /status — Phase 1.5+ stub. Phase 2 wires Realtime widgets per spec §6. -->
<script lang="ts">
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import StatusPill from '$lib/components/Primitives/StatusPill.svelte';
</script>

<svelte:head>
  <title>Status — Workflow</title>
</svelte:head>

<section class="stub">
  <div class="wrap">
    <RitualLabel>Live platform status</RitualLabel>
    <h1>Status.</h1>
    <div class="probe">
      <StatusPill kind="live" pulse>MCP gateway · live</StatusPill>
      <span class="meta">tinyassets.io/mcp · canonical apex · Cloudflare-fronted</span>
    </div>
    <p>Phase 1.5 wires real-time widgets: host count online, request inbox depth, catalog freshness, recent activity ticker. For now this page just confirms the MCP gateway is up. Probe it directly:</p>
    <pre><code>curl -I https://tinyassets.io/mcp</code></pre>
    <p>If you're seeing this page and the curl returns 200, the system is operational.</p>
  </div>
</section>

<style>
  .stub { padding-block: 80px; }
  .wrap { max-width: 720px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); color: var(--fg-2); }
  h1 { font-family: var(--font-display); font-size: clamp(48px, 8vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.95; margin: 14px 0 24px; }
  .probe { display: flex; align-items: center; gap: 14px; margin-bottom: 24px; flex-wrap: wrap; }
  .meta { font-family: var(--font-mono); font-size: 12px; color: var(--fg-3); }
  p { line-height: 1.7; margin: 0 0 14px; font-size: 16px; }
  pre { background: var(--bg-inset); border: 1px solid var(--border-1); padding: 16px; border-radius: 10px; overflow-x: auto; margin: 16px 0 24px; font-family: var(--font-mono); font-size: 13px; color: var(--fg-1); }
</style>
