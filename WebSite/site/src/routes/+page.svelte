<!--
  Landing page (/) — Phase 1 ship.
  Sections: Hero (with ChatDemo) → ThreeLayer → PatternsTease → WhatYouCanDo → OutcomeGates → WhyWorkflow → TokenStrip
-->
<script lang="ts">
  import strings from '$lib/i18n/en.json';
  import Hero from '$lib/components/Hero.svelte';
  import ThreeLayer from '$lib/components/ThreeLayer.svelte';
  import PatternsTease from '$lib/components/PatternsTease.svelte';
  import WhatYouCanDo from '$lib/components/WhatYouCanDo.svelte';
  import OutcomeGates from '$lib/components/OutcomeGates.svelte';
  import WhyWorkflow from '$lib/components/WhyWorkflow.svelte';
  import TokenStrip from '$lib/components/TokenStrip.svelte';

  const t = strings.landing;
</script>

<svelte:head>
  <title>Workflow — {t.hero_title}</title>
  <meta name="description" content={t.hero_subtitle} />
  <meta property="og:title" content="Workflow — {t.hero_title}" />
  <meta property="og:description" content={t.hero_subtitle} />
  <meta property="og:image" content="/og-image.svg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<Hero />
<ThreeLayer />
<PatternsTease />
<WhatYouCanDo />
<OutcomeGates />
<WhyWorkflow />
<TokenStrip />
