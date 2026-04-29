<script lang="ts">
  import '../app.css';
  import TopNav from '$lib/components/TopNav.svelte';
  import Footer from '$lib/components/Footer.svelte';

  let { children } = $props();
</script>

<TopNav />

<main>
  {@render children()}
</main>

<Footer />
