<script lang="ts">
  import strings from '$lib/i18n/en.json';
  const t = strings.host;
  // v0 placeholder: real build does UA-based OS detect + correct installer download link.
</script>

<h1>{t.title}</h1>
<p>{t.instructions}</p>

<div class="download-options">
  <a href="#" class="download-btn">Windows (.exe)</a>
  <a href="#" class="download-btn">macOS (.dmg)</a>
  <a href="#" class="download-btn">Linux (.deb / .AppImage)</a>
</div>
