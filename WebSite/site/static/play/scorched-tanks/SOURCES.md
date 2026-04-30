# Scorched Tanks Original-Media Sources

- Original disk: Scorched Tanks v1.90 public-domain ADF, listed by Retro32 at `https://www.retro32.com/gaming/amiga-public-domain/26042020710-scorched-tanks-v1-90-1994-dark-unicorn-amiga-public-domain-game`.
- Local source asset: `assets/scorched-tanks-v1.90.adf`.
- Source asset hashes:
  - SHA256 `E95E9EBFAC31A6BAB8C182E4DE0E53167C04424AB7B0733A071A2294CC17F953`
  - SHA1 `8797D9CE33DCAA5E39D78676258542C30F774A00`
  - MD5 `CA16CDF1F81DAFDE22157866F0CAF6C1`
- Browser launch asset: `assets/scorched-tanks-v1.90-autostart-0fd8b963.adf` (`assets/scorched-tanks-v1.90-autostart.adf` is retained as a corrected compatibility alias).
- Launch patch: `S/Startup-Sequence` changes from `LoadWB\nendcli\n` to `cd ScorchedTanks:\nScorched_TanksV1.90\nendcli\n`; game executable and data assets are unchanged.
- Launch asset hashes:
  - SHA256 `0FD8B963AB38D917FD3EED9866A11A776AFA4D2022A47DB8B80E06A47F040A94`
  - SHA1 `CB7D3888914CFDB3AB45AFBC0D3E0BC3A4ADA8CE`
  - MD5 `874F9FEF9BD01618F745601D93CCC449`
- Reference package: Scorched Tanks v1.85 on Aminet at `https://aminet.net/package/game/shoot/Scorch185`.
- Browser runtime: vAmigaWeb at `https://github.com/vAmigaWeb/vAmigaWeb` and `https://vamigaweb.github.io/`.

This page launches the autostart ADF in vAmigaWeb from a browser-only Workflow result. It tries the open AROS ROM path first. If that runtime is not compatible with the game on a given browser/device, the page accepts a user-owned Kickstart ROM through a local file picker and injects it into the iframe without uploading the ROM.

No proprietary Kickstart ROM is bundled. The browser-native artillery port is kept only as a labeled fallback and must not be reported by Workflow as the exact original game.
