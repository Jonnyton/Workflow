<script lang="ts">
  import strings from '$lib/i18n/en.json';
  const t = strings.connect;

  let copied = $state(false);
  async function copyUrl() {
    await navigator.clipboard.writeText(t.mcp_url);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<h1>{t.title}</h1>
<p>{t.instructions}</p>

<div class="mcp-url">
  <code>{t.mcp_url}</code>
  <button onclick={copyUrl}>
    {copied ? 'Copied!' : t.copy_cta}
  </button>
</div>
