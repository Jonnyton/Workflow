---
name: classic-game-design-test
description: Designs and verifies old/classic game experiences. Use when a user asks to identify, restore, emulate, port, remix, install, or prove playability of an old game, especially browser/MCP flows where the user expects the real game to become instantly playable.
---

# Classic Game Design and Test

## Overview

This skill protects the user's actual intent: "I want to play the old game I
remember" is not the same as "make a remake." A remake, remix, clone, or
browser-inspired fallback can be useful, but it must be labeled as such and
must not be counted as satisfying a request for the real childhood game.

The target experience is a chatbot/browser user saying the game they remember,
the workflow finding the rights-cleared original or best compatible public
release, adapting it to the current machine without manual emulator setup, and
ending with a single launch surface that plays immediately.

## Owns

- Identifying the intended classic game from partial memory.
- Choosing between original emulation, official release, source port,
  compatibility patch, remake, or fallback.
- Designing browser-first or one-click launch flows for old games.
- Defining playable-proof acceptance tests for input, audio, and actual
  gameplay.
- Recording blockers when rights, firmware, compatibility, or host capability
  prevent the real game path.

## Does Not Own

- Remakes, quick browser clones, or new playable prototypes once the user has
  accepted that class of outcome. Use `game-prototyping`.
- Generic UI implementation details. Use `frontend-ui-engineering`.
- Generic browser debugging. Use `browser-testing-with-devtools`.
- Core test strategy outside game/runtime proof. Use `test-driven-development`.
- Public MCP chatbot acceptance. Use `ui-test` when the chatbot surface changes.
- Durable architectural decisions. Use `documentation-and-adrs`.

## Required Product Distinction

Before building, classify the requested outcome:

1. **Original game path** - the real historical game data runs in a compatible
   runtime, emulator, official web player, or source port.
2. **Compatibility port** - original code/assets are used where allowed, with a
   modern engine or wrapper.
3. **Remake or remix** - newly built gameplay inspired by the old game.
4. **Launcher only** - a wrapper that starts something already installed or
   externally acquired.

If the user asked for the real old game, pursue `Original game path` first.
Only switch to another class when the blocker is explicit and documented.

## Rights and Source Gate

Do not use warez, cracked images, copyrighted firmware, or private downloads.
For every game/runtime/media source, record:

- Public URL or local authoritative source.
- License or distribution status.
- Whether ROM/BIOS/firmware is required.
- Whether the emulator/runtime license allows this use.
- Any known limitations, such as trial firmware or missing save support.

If the first working route appears to require copyrighted firmware or game
media the project cannot provide, actively test any rights-cleared firmware,
BIOS replacement, source port, or compatibility shim path before marking the
task `NOT_PLAYABLE_YET`. Proprietary firmware is a blocker only after the free
compatibility route has been tried with diagnostics. Do not pretend a remake
satisfies it.

## Build Workflow

1. **Identify the game precisely.** Use the user's clues, year/platform hints,
   screenshots, online references, and titles with similar names. Record the
   confidence and alternatives.
2. **Select the target class.** Prefer a rights-cleared original game path.
   Keep remakes/fallbacks subordinate unless the user explicitly requested one.
3. **Choose a proven runtime.** Use an established emulator, source port,
   compatibility layer, or library for the core platform logic. Do not
   hand-roll CPU, disk, audio, physics, parsing, or AI engines when a proven
   runtime exists.
4. **Try the free compatibility path first.** When a game needs platform
   firmware, treat an open replacement such as AROS as an engineering target,
   not a passive fallback. Build a diagnostic loop around it: boot media, log
   startup failures, vary runtime configuration, patch launch scripts, and only
   escalate to licensed firmware after the free path fails with evidence.
5. **Sweep original releases before overfitting.** If one original release
   fails before gameplay, search for adjacent official, shareware,
   author-permitted, magazine-cover, Aminet, GameBase, WHDLoad, or public-
   domain catalog releases before spending all effort on one binary. Record
   provenance and hashes for each diagnostic copy. Count a release variant only
   when the original executable reaches gameplay; Workbench, folders, title
   screens, shell prompts, and "file not executable" messages are launch
   diagnostics, not playability.
6. **Escalate firmware blockers precisely.** When multiple rights-cleared
   original releases fail at the same firmware/runtime boundary, write the
   blocker as a capability primitive such as "user/host-supplied licensed
   firmware" or "runtime compatibility patch," not as a vague emulator failure.
   Keep testing free replacements, but stop treating a hidden sanity-check
   patch as success unless gameplay proof follows.
7. **Design for browser/chatbot users.** The happy path must not require the
   user to install a desktop app, restart, manually boot an emulator, hunt for
   firmware, or copy files unless that limitation is explicitly accepted.
8. **Integrate media deterministically.** Loading a disk/archive is not enough.
   The launcher must wait for the runtime to be ready, inject media once, avoid
   reload loops, and expose status that distinguishes "loaded" from "playing."
   If the runtime stages media in a file slot, use its explicit boot/mount with
   reset semantics; do not count a post-boot insert as an autostart proof.
   For emulator APIs that acknowledge disk/ROM insertion asynchronously, wire a
   mount acknowledgement or bounded retry. Never schedule blind repeated resets;
   a reset loop is a blocker even when the disk eventually appears mounted.
9. **Map input deliberately.** Define mouse, keyboard, touch, and gamepad
   mappings needed by the target game. Include a real browser click/tap path
   for any action the user naturally expects to perform with the mouse.
10. **Unlock and prove audio.** Browser audio usually needs a user gesture.
   Provide an explicit launch/play gesture, then verify the audio context is
   running and unmuted. Do not claim sound works from code inspection alone.
11. **Instrument launch state.** Emit concise runtime status for media loaded,
   emulator ready, game started, input accepted, audio running, and fatal
   blockers. Avoid mock success states that look playable.
12. **Keep fallbacks honest.** If a remake or quick browser clone exists, label
    it as a fallback/remix and keep it separate from the real-game acceptance
    result.
13. **Handoff prototypes deliberately.** When the accepted scope is a remake,
    remix, compatibility-inspired prototype, or small browser game, hand off to
    `game-prototyping` for the GDD, asset registry, archetype pack, and game
    debug protocol. Keep this skill in the loop only to preserve the
    original/remake distinction and rights/provenance notes.

## Endpoint Delivery Model

Classic-game work must separate the game from the runtime and from the user's
current device. Model every deliverable with three parts:

- `game_package`: rights-cleared game media, patch metadata, launch recipe,
  provenance, and playability proof for one game/version.
- `runtime_package`: reusable emulator/runtime such as PUAE, DOSBox, ScummVM,
  MAME, BasiliskII, SheepShaver, vAmiga/SAE, or a source port. It is installed
  or cached once per endpoint and reused by many games.
- `endpoint_target`: browser session, desktop launcher, phone PWA/app, home
  computer relay, or hosted live state. It owns install authority, storage
  limits, and what "one click to play" means.

Do not create per-game runtime bloat. If 100 games use DOSBox, the endpoint
should have one shared DOSBox runtime package plus 100 small game packages and
launch recipes, not 100 DOSBox installs.

Choose the output by capability and user context:

- Browser-only or work/shared device: hosted browser play, no local install.
- Personal computer with local agent/app authority: desktop shortcut/native
  launcher backed by shared runtimes.
- Personal phone app/PWA: phone launcher or installed PWA backed by shared
  runtimes where the platform allows it.
- Phone while a home computer is reachable: queue or perform install on the
  home computer through an authorized relay; otherwise save a durable install
  intent and provide browser play now.

Design for the same primitive graph across current and likely future clients.
Do not second-class browser-only users; route around missing local authority
with hosted play, queued intents, relays, or durable library entries.

Treat endpoint capability as negotiated runtime state, not a fixed product
assumption. A browser-only chat can launch hosted play and save intent, but it
cannot silently install native runtimes or desktop shortcuts. A local desktop
agent, phone app/PWA, enterprise-managed web app, or home-computer relay may
have more authority. Record which authority was actually available, which
output was chosen, and which future-capability hook would upgrade the result.

## Cheat-To-User Loop Discipline

Diagnostic work may use direct developer tools to discover what is technically
possible, but final product proof must come from the same class of surface a
future user will use.

When a direct diagnostic path teaches you something useful:

1. Save the evidence as a cheat sheet: source URLs, disk hashes, runtime
   profile, launch patch, screenshots, logs, and exact blocker.
2. Convert the finding into branch primitives: `game_package`,
   `runtime_package`, `endpoint_target`, capability probe, install intent, or
   library entry.
3. Re-drive the live chatbot/MCP path as a user would, asking the chatbot to
   propose missing primitives or patches instead of silently patching around
   the workflow.
4. Patch the live branch only to give that user path the missing capability.
5. Re-test through the user surface. Do not count the diagnostic path as final
   success if the user surface cannot reproduce it.

This keeps reverse-engineering useful without letting it replace the target
experience: a user asks in chat and ends at the correct playable output for
their endpoint.

## Playable-Proof Acceptance

"Playable" means a real gameplay objective was achieved in the live runtime.
For an artillery/tank game, the minimum proof is:

- A match starts from the real game path.
- The user can aim or otherwise control the shot.
- A mouse click or equivalent user-facing action fires.
- The projectile or action hits a tank.
- The game visibly changes state, such as damage, health, score, turn advance,
  or explosion.
- Audio is enabled and verified after a user gesture.

For other genres, replace "hit a tank" with the smallest genre-authentic proof:
move a character and collect an item, complete a menu-start-to-gameplay loop,
win/lose a round, enter a level, or trigger a visible scored action.

Never claim final playability from:

- The launcher page rendering.
- A canvas being nonblank.
- A disk/archive being assigned.
- An emulator boot screen.
- A title screen only.
- A remake running when the user requested the original.
- Code inspection without live runtime evidence.

Observation-only test instrumentation is allowed, but it must not change game
state to manufacture the proof. The user-facing input path, such as a real
button or canvas click, still has to trigger the gameplay action.

## Browser Verification Checklist

Use `browser-testing-with-devtools` or an equivalent real browser path.
Capture evidence with date, environment, URL, and exact build/version.

- [ ] Desktop viewport reaches gameplay without manual emulator setup.
- [ ] Mobile or narrow viewport is usable when the experience is public web.
- [ ] Canvas/frame fills the intended window or tab; no tiny default viewport.
- [ ] Runtime does not restart, reload, or lose media after start.
- [ ] Bootable media actually boots after injection; a shell prompt with a
      mounted disk is not proof that Startup-Sequence ran.
- [ ] Console and network logs have no fatal load/input/audio errors.
- [ ] Input proof uses real browser events, not only internal function calls.
- [ ] Audio proof shows user gesture, `AudioContext` running/unmuted, and
      observable runtime audio activity; use headed/manual proof when needed.
- [ ] Emulator pages that monkey-patch browser globals can break object
      serialization in test tools; read proof/state as JSON strings before
      parsing in the test process.
- [ ] Screenshots or video show before/action/after gameplay state.
- [ ] The original/remake/fallback class is stated in the verification note.

For canvas-heavy games, include a pixel or screenshot check so a blank canvas
cannot pass. For public Workflow/MCP behavior, supporting probes are not final:
run the live chatbot `ui-test` when connector behavior changed.

## Failure Handling

If the game is not fully playable:

1. Mark the result `NOT_PLAYABLE_YET`.
2. State the exact blocker: rights, firmware, media, emulator compatibility,
   browser autoplay, input mapping, restart loop, performance, or platform
   install capability.
3. Preserve any working fallback, but label it accurately.
4. Add the smallest next work item to `STATUS.md` if the blocker remains active.
5. Do not remove or downgrade the acceptance standard to make the result pass.

## Handoff Pattern

Typical sequence:

```text
classic-game-design-test
  -> game-prototyping (only for accepted remake/prototype/fallback builds)
  -> frontend-ui-engineering
  -> browser-testing-with-devtools
  -> test-driven-development
  -> code-review-and-quality
```

Add `security-and-hardening` when handling user uploads, external archives, or
remote game metadata. Add `documentation-and-adrs` when the solution changes
the product architecture for browser-only game delivery.
