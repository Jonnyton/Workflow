<!--
  SigilMark — the Workflow brand mark (summoning sigil).
  Renders as <img> pointing to /logo-mark.svg in static/.
-->
<script lang="ts">
  let {
    size = 28
  } = $props();
</script>

<img
  src="/logo-mark.svg"
  alt="Workflow"
  width={size}
  height={size}
  class="sigil"
/>

<style>
  .sigil {
    display: block;
    flex-shrink: 0;
  }
</style>
