<script lang="ts">
  import { onMount } from 'svelte';

  onMount(() => {
    window.location.replace('/wiki');
  });
</script>

<svelte:head>
  <title>Community wiki - Workflow</title>
  <meta http-equiv="refresh" content="0; url=/wiki" />
  <link rel="canonical" href="https://tinyassets.io/wiki" />
</svelte:head>

<section class="redirect">
  <div>
    <h1>Goals retired into the community wiki.</h1>
    <p>The live public work surface now lives at <a href="/wiki">/wiki</a>.</p>
  </div>
</section>

<style>
  .redirect {
    align-items: center;
    color: var(--fg-2);
    display: grid;
    min-height: 55vh;
    padding: 72px clamp(16px, 4vw, 32px);
  }

  .redirect div {
    margin: 0 auto;
    max-width: 720px;
  }

  h1 {
    color: var(--fg-1);
    font-family: var(--font-display);
    font-size: clamp(40px, 7vw, 68px);
    font-weight: 400;
    letter-spacing: 0;
    line-height: 0.98;
    margin: 0 0 16px;
  }

  p {
    font-size: 16px;
    line-height: 1.7;
    margin: 0;
  }

  a {
    color: var(--ember-600);
    text-decoration: none;
  }

  a:hover {
    text-decoration: underline;
  }
</style>
