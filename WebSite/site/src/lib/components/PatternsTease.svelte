<!--
  Home-page strip introducing the iteration loop.
  Used to be "Patterns from the canon" (architecture-doc framing).
  Now: "The loop." — a 5-step horizontal walkthrough teasing the full
  community-driven iteration cycle, with a CTA into /loop/.
-->
<script lang="ts">
  import RitualLabel from './Primitives/RitualLabel.svelte';
  import Button from './Primitives/Button.svelte';

  // Five compressed beats from the full continued conversation on /loop/.
  const beats = [
    { n: '01', label: 'Real work',     blurb: "You ask your chatbot for the thing. A daemon does it. CSV, draft, synthesis, BOM — the actual artifact, not a description." },
    { n: '02', label: 'Friction',      blurb: "Almost. One thing's missing — a feature, a fix, a finer evaluator. You say so naturally." },
    { n: '03', label: 'Patch filed',   blurb: "Your chatbot files a patch_request to the wiki. No git, no GitHub, no command. Stays in chat." },
    { n: '04', label: 'Daemon ships',  blurb: "A daemon picks the patch up, drafts a fix, clears gates, opens a PR. The fix doesn't merge until it's real." },
    { n: '05', label: 'Loop evolves',  blurb: "Same flow edits the goals themselves — gates, branches, and routing. The substrate changes through the loop." }
  ];
</script>

<section class="loop">
  <div class="container">
    <div class="head">
      <RitualLabel color="var(--violet-400)">· How the project evolves itself ·</RitualLabel>
      <h2 class="title">The loop.</h2>
      <p class="lead">
        Your chatbot doesn't just <em>use</em> Workflow — it helps build it. A user has a real-world thing they want done. A daemon does the work. The user notices what's missing. The chatbot files a patch. A different daemon picks it up. The fix ships. Settlement mints. The next user benefits — and the goals themselves, the rules of the game, get forked and re-tuned by the people running the loop.
      </p>
      <p class="origin">
        <strong>Even this loop — the very first version of it — was built by users.</strong> Drawn out of <code>user-sim</code> sessions where chatbot-personas filed the first patches, named what was missing, forked what didn't fit. The protocol's first patches are the protocol. There has never been a separate design committee.
      </p>
      <Button variant="primary" href="/loop">Walk the whole loop →</Button>
    </div>

    <ol class="beats">
      {#each beats as b (b.n)}
        <li class="beat">
          <span class="beat__n">{b.n}</span>
          <span class="beat__label">{b.label}</span>
          <p class="beat__blurb">{b.blurb}</p>
        </li>
      {/each}
    </ol>
  </div>
</section>

<style>
  .loop { border-top: 1px solid var(--border-1); }
  .head { margin-bottom: 28px; max-width: 72ch; }
  .title { font-family: var(--font-display); font-size: clamp(36px, 6vw, 56px); font-weight: 400; letter-spacing: -0.03em; margin: 14px 0 14px; line-height: 1; }
  .lead { font-size: 16px; color: var(--fg-2); line-height: 1.65; margin: 0 0 14px; max-width: 64ch; }
  .lead em { color: var(--fg-1); font-style: italic; }
  .origin { font-size: 14px; color: var(--fg-2); line-height: 1.6; margin: 0 0 20px; padding: 14px 18px; background: rgba(138,99,206,0.06); border-left: 2px solid var(--violet-400); border-radius: 0 8px 8px 0; max-width: 64ch; }
  .origin strong { color: var(--fg-1); font-weight: 600; }
  .origin code { background: rgba(255,255,255,0.06); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 12.5px; color: var(--violet-200); }

  .beats { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; counter-reset: beat; position: relative; }
  @media (max-width: 1100px) { .beats { grid-template-columns: repeat(3, 1fr); } }
  @media (max-width: 700px)  { .beats { grid-template-columns: 1fr; } }
  .beat { background: var(--bg-2); border: 1px solid var(--border-1); border-radius: 12px; padding: 18px 18px 16px; position: relative; transition: border-color var(--dur-base) var(--ease-summon), transform var(--dur-base) var(--ease-summon); }
  .beat:hover { border-color: rgba(138,99,206,0.35); transform: translateY(-2px); }
  .beat__n { display: block; font-family: var(--font-mono); font-size: 11px; color: var(--violet-400); letter-spacing: 0.16em; }
  .beat__label { display: block; font-family: var(--font-display); font-size: 17px; font-weight: 500; color: var(--fg-1); letter-spacing: -0.01em; margin: 4px 0 8px; }
  .beat__blurb { font-size: 13px; color: var(--fg-2); line-height: 1.55; margin: 0; }
  .beat__blurb :global(code) { background: rgba(255,255,255,0.06); padding: 1px 4px; border-radius: 3px; font-family: var(--font-mono); font-size: 11.5px; color: var(--violet-200); }
</style>
