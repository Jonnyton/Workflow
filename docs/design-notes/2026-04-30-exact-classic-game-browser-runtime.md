# Exact Classic-Game Browser Runtime

## Problem

The old-game branch cannot satisfy "play the game I remember" by silently shipping a remake or a compatibility clone. A browser-native remake is useful when the user asks for a remix, but it is a different product promise from playing the original childhood game.

The browser-only constraint still stands: the user may be in Claude.ai or ChatGPT web with only an MCP connector. They should not need a local project checkout, native emulator install, desktop helper app, browser extension, or OS restart.

## Decision

Classic-game branches use this order:

1. Identify the exact title and platform.
2. Find lawful public media or ask the user for their own media.
3. Launch the original media in a hosted browser runtime when a runtime exists.
4. If required system firmware is proprietary, use a rights-cleared hosted firmware/runtime entitlement before asking the user for a local file.
5. If no entitlement is available, import firmware only from a user-owned local file in the browser session.
6. Label any remake, reimplementation, or compatibility port as a fallback, never as the exact-game success state.

For browser-only users, "installed" means a browser-installable PWA/result URL. A native `.lnk` or `.desktop` file requires a local-app capability and cannot be the browser-only acceptance path.

## Branch Contract

The branch output must report one of these states:

- `ORIGINAL_MEDIA_PLAYABLE`: original media booted in a browser runtime with lawful assets available.
- `NEEDS_RIGHTS_CLEARED_FIRMWARE`: original media is available and the browser runtime exists, but instant play requires a hosted proprietary firmware entitlement.
- `NEEDS_USER_OWNED_FIRMWARE`: original media is available, but the runtime needs proprietary firmware the platform cannot bundle.
- `NEEDS_USER_MEDIA`: no lawful public media is available; the user must provide their own disk/image.
- `UNAVAILABLE_NO_BROWSER_RUNTIME`: no viable browser runtime exists for the target platform yet.
- `FALLBACK_PORT_READY`: a remake/port exists, but it is not the requested exact game.

The chatbot can present `FALLBACK_PORT_READY` as an option only after making the exact-game state explicit.

## Scorched Tanks Slice

The first implementation uses Scorched Tanks v1.90:

- Public media: Retro32 lists Scorched Tanks v1.90 as an Amiga public-domain ADF.
- Reference package: Aminet hosts Scorched Tanks v1.85 as `game/shoot/Scorch185.lha`.
- Browser runtime: vAmigaWeb can run Amiga disk media in an iframe and supports same-site disk injection plus Kickstart injection.
- Asset handling: the v1.90 ADF is stored under `/play/scorched-tanks/assets/` with hashes in `SOURCES.md`.
- Firmware handling: no Kickstart ROM is bundled. The page first checks for a deployment-provisioned `licensed/kickstart-a500-1.3.rom`, then tries open AROS, then accepts a local user-owned ROM file if the hosted entitlement is absent.

This makes the Scorched Tanks page an exact-media launcher first and a compatibility port second.

Verification update, 2026-04-30: Scorched Tanks v1.90, Aminet v1.85, and public-domain v0.95 all boot in browser AROS paths but black-screen when the AMOS executable takes over. Public emulator documentation also identifies AROS replacement ROMs as less compatible than original Kickstart ROMs for Amiga software. Until a rights-cleared hosted Kickstart path is provisioned and verified, the correct exact-game outcome for Scorched Tanks is `NEEDS_RIGHTS_CLEARED_FIRMWARE`, not `ORIGINAL_MEDIA_PLAYABLE`.
