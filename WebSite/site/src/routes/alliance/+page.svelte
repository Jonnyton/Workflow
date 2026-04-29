<!-- /alliance — recruiting + community-mission form, carry-over from legacy tinyassets.io/tiny-alliance -->
<script lang="ts">
  import RitualLabel from '$lib/components/Primitives/RitualLabel.svelte';
  import Button from '$lib/components/Primitives/Button.svelte';
  import legal from '$lib/content/legal-info.json';
</script>

<svelte:head>
  <title>Tiny Alliance — Workflow</title>
  <meta name="description" content="Join the Tiny Alliance. The community of contributors, hosts, and evaluators behind the Workflow protocol." />
</svelte:head>

<section class="hero">
  <div class="container">
    <RitualLabel color="var(--ember-500)">· Tiny Alliance · community ·</RitualLabel>
    <h1>Join the Tiny Alliance.</h1>
    <p class="lead">The Alliance is the community of people who care about the Workflow protocol — contributors, daemon hosts, evaluators, holders, and anyone who wants real-world-effect work to actually ship. Share what you're passionate about. We'll find a place for you.</p>
  </div>
</section>

<section class="form-block">
  <div class="container">
    <form class="form" onsubmit={(e) => { e.preventDefault(); alert('Form submission lands in Phase 1.5 — for now please email ops@tinyassets.io'); }}>
      <RitualLabel>Send a message</RitualLabel>
      <label>Name <input type="text" required /></label>
      <label>Email <input type="email" required /></label>
      <label>Phone (optional) <input type="tel" /></label>
      <label class="full">What community mission are you most passionate about?
        <textarea rows="5" required placeholder="A real-world goal you'd want a daemon to help pursue — your own or someone else's."></textarea>
      </label>
      <Button variant="primary" >Send message</Button>
      <p class="meta">Form delivery lands in Phase 1.5. For now: <a href="mailto:ops@tinyassets.io">ops@tinyassets.io</a></p>
    </form>

    <aside class="book">
      <RitualLabel color="var(--violet-400)">Or book an interview</RitualLabel>
      <h3>30 min · free.</h3>
      <p>Faster than the form. We talk through what you'd want to ship and where the Alliance fits.</p>
      <ul class="slots">
        <li><span>Interview</span><span class="meta-small">30 min · free</span><Button variant="ghost" >Book ↗</Button></li>
        <li><span>Consultation</span><span class="meta-small">30 min · free</span><Button variant="ghost" >Book ↗</Button></li>
      </ul>
      <p class="phone">Or call <a href="tel:+1{legal.contact.phone.replaceAll('-','')}">{legal.contact.phone}</a></p>
    </aside>
  </div>
</section>

<style>
  .hero, .form-block { padding-block: 56px; border-top: 1px solid var(--border-1); }
  .hero { padding-top: 80px; border-top: none; }
  h1 { font-family: var(--font-display); font-size: clamp(48px, 8vw, 72px); font-weight: 400; letter-spacing: -0.035em; line-height: 0.95; margin: 14px 0 18px; }
  h3 { font-family: var(--font-display); font-size: 22px; font-weight: 500; margin: 8px 0 8px; color: var(--fg-1); }
  .lead { font-size: 16px; color: var(--fg-2); line-height: 1.6; max-width: 64ch; margin: 0; }
  .form-block .container { display: grid; grid-template-columns: 1.4fr 1fr; gap: 32px; align-items: start; }
  @media (max-width: 800px) { .form-block .container { grid-template-columns: 1fr; } }
  .form { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; padding: 24px 26px; display: flex; flex-direction: column; gap: 12px; }
  .form label { display: flex; flex-direction: column; gap: 6px; font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.14em; }
  .form input, .form textarea { background: var(--bg-inset); border: 1px solid var(--border-1); color: var(--fg-1); padding: 10px 12px; border-radius: 6px; font-family: var(--font-sans); font-size: 14px; text-transform: none; letter-spacing: 0; }
  .form input:focus, .form textarea:focus { border-color: var(--ember-600); outline: none; box-shadow: var(--glow-ember); }
  .meta { font-size: 12px; color: var(--fg-3); font-style: italic; margin: 4px 0 0; }
  .meta a { color: var(--ember-600); text-decoration: none; }

  .book { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 14px; padding: 24px 26px; }
  .book p { font-size: 13.5px; color: var(--fg-2); line-height: 1.6; margin: 0 0 14px; }
  .slots { list-style: none; padding: 0; margin: 0 0 16px; display: flex; flex-direction: column; gap: 10px; }
  .slots li { display: grid; grid-template-columns: 1fr auto auto; gap: 12px; align-items: center; padding: 10px 14px; background: var(--bg-inset); border-radius: 8px; font-size: 14px; color: var(--fg-1); }
  .meta-small { font-family: var(--font-mono); font-size: 11px; color: var(--fg-3); text-transform: uppercase; letter-spacing: 0.1em; }
  .phone { font-size: 13px; color: var(--fg-2); margin: 0; padding-top: 12px; border-top: 1px solid var(--border-1); }
  .phone a { color: var(--ember-600); text-decoration: none; }
</style>
