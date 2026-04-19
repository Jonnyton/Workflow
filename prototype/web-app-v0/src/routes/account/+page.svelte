<script lang="ts">
  import strings from '$lib/i18n/en.json';
  const t = strings.account;
  let { data } = $props();
</script>

<h1>{t.title}</h1>
<p>Signed in as {data.user.email}</p>

<section>
  <h2>My exports</h2>
  <p>(v0 stub — real build lists user's public artifacts here)</p>
</section>

<section>
  <h2>Delete account</h2>
  <p>{t.delete_confirm}</p>
  <button disabled>Delete (wired in real build)</button>
</section>
