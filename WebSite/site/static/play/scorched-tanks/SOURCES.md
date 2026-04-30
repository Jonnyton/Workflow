# Scorched Tanks Original-Media Sources

- Original disk: Scorched Tanks v1.90 public-domain ADF, listed by Retro32 at `https://www.retro32.com/gaming/amiga-public-domain/26042020710-scorched-tanks-v1-90-1994-dark-unicorn-amiga-public-domain-game`.
- Local source asset: `assets/scorched-tanks-v1.90.adf`.
- Source asset hashes:
  - SHA256 `E95E9EBFAC31A6BAB8C182E4DE0E53167C04424AB7B0733A071A2294CC17F953`
  - SHA1 `8797D9CE33DCAA5E39D78676258542C30F774A00`
  - MD5 `CA16CDF1F81DAFDE22157866F0CAF6C1`
- Browser launch asset: `assets/scorched-tanks-v1.90-autostart-a642eb46.adf` (`assets/scorched-tanks-v1.90-autostart.adf` is retained as a corrected compatibility alias).
- Launch patch: `S/Startup-Sequence` changes from `LoadWB\nendcli\n` to `cd :\nScorched_TanksV1.90\nendcli\n`; game executable and data assets are unchanged.
- Launch asset hashes:
  - SHA256 `A642EB4693FB8E0D8FF0CA9A0B830BFC6D9F0816A2DB3C77C44102B5B1B86976`
  - SHA1 `1C379C482E0BCBCB14D9F8F61043545440AE4397`
  - MD5 `FF0D3582E97F4A316874BC47BB8B94C3`
- Reference package: Scorched Tanks v1.85 on Aminet at `https://aminet.net/package/game/shoot/Scorch185`.
- Browser runtime: vAmigaWeb at `https://github.com/vAmigaWeb/vAmigaWeb` and `https://vamigaweb.github.io/`.

This page launches the autostart ADF in vAmigaWeb from a browser-only Workflow result. It tries the open AROS ROM path first. If that runtime is not compatible with the game on a given browser/device, the page accepts a user-owned Kickstart ROM through a local file picker and injects it into the iframe without uploading the ROM.

No proprietary Kickstart ROM is bundled. The browser-native artillery port is kept only as a labeled fallback and must not be reported by Workflow as the exact original game.
