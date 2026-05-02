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
- `NOT_PLAYABLE_YET`: original media and a browser runtime exist, but tested lawful/free paths have not reached gameplay acceptance; record the exact blocker and next capability path.

The chatbot can present `FALLBACK_PORT_READY` as an option only after making the exact-game state explicit.

## Scorched Tanks Slice

The first implementation currently targets Scorched Tanks v1.75 from Amiga Power #41, with v1.77, v1.85, v1.90, and v0.95 retained as diagnostic release variants:

- Public media: Amiga Power #41 disk 2 contains Scorched Tanks v1.75; Retro32 lists Scorched Tanks v1.90 as an Amiga public-domain ADF; Aminet hosts Scorched Tanks v1.85 as `game/shoot/Scorch185.lha`.
- Browser runtime: vAmigaWeb can run Amiga disk media in an iframe and supports same-site disk injection plus Kickstart injection.
- Asset handling: the current v1.75 AP41 autostart ADF is stored under `/play/scorched-tanks/assets/` with hashes in `SOURCES.md`; other release ADFs remain diagnostic until provenance and compatibility are resolved.
- Firmware handling: no Kickstart ROM is bundled. The page first checks for a deployment-provisioned `licensed/kickstart-a500-1.3.rom`, then tries open AROS, then accepts a local user-owned ROM file if the hosted entitlement is absent. Amiga Forever lists Scorched Tanks in its commercial game pack, so a future approved entitlement integration could replace loose file-picking for licensed deployments.

This makes the Scorched Tanks page an exact-media launcher first and a compatibility port second.

Verification update, 2026-05-01: the Scorched Tanks v1.90 launch ADF now has a valid `S/Startup-Sequence` file header and autostarts the executable under browser AROS. The AROS path still stalls on a blank gray runtime display after the AMOS executable takes over. Public emulator documentation also identifies AROS replacement ROMs as less compatible than original Kickstart ROMs for Amiga software. Until a rights-cleared hosted Kickstart path is provisioned and verified, the correct exact-game outcome for Scorched Tanks is `NEEDS_RIGHTS_CLEARED_FIRMWARE`, not `ORIGINAL_MEDIA_PLAYABLE`.

Verification update, 2026-05-02: after broader release and firmware diagnostics, the current exact-game outcome is `NOT_PLAYABLE_YET`. AP41 v1.75 reaches the title/legal screen under bundled AROS and then black-screens before gameplay; v1.77, v1.85, and GameBase fixed v1.90 fail under AROS with `0x0100000F` memory-header/free-list corruption or black/empty-screen states; v0.95 reports not enough memory on A500-style AROS and black-screens or aborts on larger profiles. The older AMOS-for-Windows AROS ROM/ext reset-loops in browser SAE. A licensed Kickstart path remains the leading capability to prove, but it has not been verified on this host, so the branch must not claim `NEEDS_RIGHTS_CLEARED_FIRMWARE` as if licensed Kickstart is already proven.

Shim update, 2026-05-02: adding AMOS-for-Windows `amos.library` on a second floppy and assigning it into `LIBS:` before v1.77 launch did not change the outcome. The low-memory profile still reports not enough memory, and the larger A500 profile still raises `0x0100000F`. The missing primitive is therefore not just a bundled `amos.library`.
