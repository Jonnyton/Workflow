<script lang="ts">
  import strings from '$lib/i18n/en.json';
  const t = strings.status;
  let { data } = $props();
</script>

<h1>{t.title}</h1>

<div class="widgets">
  <div class="widget">
    <h2>{t.widgets.hosts_online}</h2>
    <p class="number">{data.hostsOnline}</p>
  </div>
  <div class="widget">
    <h2>{t.widgets.inbox_depth}</h2>
    <p class="number">{data.inboxDepth}</p>
  </div>
  <div class="widget">
    <h2>{t.widgets.catalog_freshness}</h2>
    <p>{data.catalogFreshness ?? '—'}</p>
  </div>
  <div class="widget">
    <h2>{t.widgets.recent_activity}</h2>
    <ul>
      {#each data.recentActivity as entry}
        <li>{entry}</li>
      {:else}
        <li>—</li>
      {/each}
    </ul>
  </div>
</div>
