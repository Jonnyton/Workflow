<!-- /account — Phase 2+ stub. Auth-gated full implementation requires Supabase Auth + GitHub OAuth wiring. -->
<script lang="ts">
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
</script>

<svelte:head>
  <title>Account — Workflow</title>
</svelte:head>

<section class="stub">
  <div class="wrap">
    <RitualLabel>Account · auth-gated · Phase 2</RitualLabel>
    <h1>Account.</h1>
    <p>Sign in with GitHub. Manage your sessions, see what you've published, export your data, or delete everything (30-day grace window).</p>
    <p>Phase 2 ship. For now, all account-related actions happen via the MCP connector in your chatbot.</p>
  </div>
</section>

<style>
  .stub { padding-block: 80px; }
  .wrap { max-width: 720px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 32px); color: var(--fg-2); }
  h1 { font-family: var(--font-display); font-size: clamp(48px, 8vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.95; margin: 14px 0 18px; }
  p { line-height: 1.7; margin: 0 0 14px; font-size: 16px; }
</style>
