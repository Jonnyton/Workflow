# Scorched Tanks Browser Play Sources

- Reference game: Scorched Tanks v1.85, published on Aminet at `https://aminet.net/package/game/shoot/Scorch185`.
- Reference disk: Scorched Tanks v1.90 public-domain ADF, listed by Retro32 at `https://www.retro32.com/gaming/amiga-public-domain/26042020710-scorched-tanks-v1-90-1994-dark-unicorn-amiga-public-domain-game`.
- Runtime shape: static browser PWA. No local native emulator, local project checkout, desktop MCP host, or browser extension is required.

The exact Amiga binary was tested in open browser Amiga runtimes, including vAmigaWeb with open AROS ROMs. The disk mounted and booted, but the game executable did not reach a playable screen without a Kickstart-compatible runtime. Because a browser-only chatbot/MCP flow cannot assume a proprietary Kickstart ROM or a local emulator install, this page is a browser-native compatibility port that preserves the artillery-tank play loop while satisfying the no-local-app constraint.

The Workflow branch should return `/play/scorched-tanks/` as the browser-only playable surface. Browser installation is handled by the browser PWA install prompt.
