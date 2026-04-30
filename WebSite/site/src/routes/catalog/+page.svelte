<!-- /catalog — Phase 1.5+ stub. Real implementation lifts from design-source/ui_kits/workflow-web/Catalog.jsx. -->
<script lang="ts">
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
</script>

<svelte:head>
  <title>Catalog — Workflow</title>
</svelte:head>

<section class="stub">
  <div class="wrap">
    <RitualLabel color="var(--violet-400)">· Coming in Phase 1.5 ·</RitualLabel>
    <h1>Catalog.</h1>
    <p>Goals at the top. Drill into a goal to see its leaderboard of branches — sorted by highest gate, runs, judge score, or forks. Three goals live today; thousands soon. Every public node is CC0.</p>
    <p>Until this page lands, your chatbot can browse the catalog directly via the <a href="/connect">MCP connector</a>. Just say "browse goals" or "show me research-paper branches" once connected.</p>
  </div>
</section>

<style>
  .stub { padding-block: 80px; }
  .wrap { max-width: 720px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); color: var(--fg-2); }
  h1 { font-family: var(--font-display); font-size: clamp(48px, 8vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.95; margin: 14px 0 18px; }
  p { line-height: 1.7; margin: 0 0 14px; font-size: 16px; }
</style>
