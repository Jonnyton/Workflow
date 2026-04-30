# Scorched Tanks Original-Media Sources

- Original disk: Scorched Tanks v1.90 public-domain ADF, listed by Retro32 at `https://www.retro32.com/gaming/amiga-public-domain/26042020710-scorched-tanks-v1-90-1994-dark-unicorn-amiga-public-domain-game`.
- Local source asset: `assets/scorched-tanks-v1.90.adf`.
- Source asset hashes:
  - SHA256 `E95E9EBFAC31A6BAB8C182E4DE0E53167C04424AB7B0733A071A2294CC17F953`
  - SHA1 `8797D9CE33DCAA5E39D78676258542C30F774A00`
  - MD5 `CA16CDF1F81DAFDE22157866F0CAF6C1`
- Browser launch asset: `assets/scorched-tanks-v1.90-autostart.adf`.
- Launch patch: `S/Startup-Sequence` changes from `LoadWB\nendcli\n` to `cd SYS:\nScorched_TanksV1.90\nendcli\n`; game executable and data assets are unchanged.
- Launch asset hashes:
  - SHA256 `9ED76FB150EE587EBFAB25530B256B0C288F22722A65C9EEB7108BD5B4198423`
  - SHA1 `2CB64AAB6FD0D6B8E412B9931976D20525BD8696`
  - MD5 `053CA6C3C6C456E1FB4ADEE089B58AC0`
- Reference package: Scorched Tanks v1.85 on Aminet at `https://aminet.net/package/game/shoot/Scorch185`.
- Browser runtime: vAmigaWeb at `https://github.com/vAmigaWeb/vAmigaWeb` and `https://vamigaweb.github.io/`.

This page launches the autostart ADF in vAmigaWeb from a browser-only Workflow result. It tries the open AROS ROM path first. If that runtime is not compatible with the game on a given browser/device, the page accepts a user-owned Kickstart ROM through a local file picker and injects it into the iframe without uploading the ROM.

No proprietary Kickstart ROM is bundled. The browser-native artillery port is kept only as a labeled fallback and must not be reported by Workflow as the exact original game.
