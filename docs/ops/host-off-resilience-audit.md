---
title: Host-off resilience audit — what breaks when host's computer is off
date: 2026-04-21
author: lead
status: actionable; tracks open gaps to host-independence
---

# Host-off resilience audit

Captures the concrete gaps between "works when host is online" and
"works 24/7 with zero hosts online" (forever rule, AGENTS.md
top-of-file). Every row is actionable. When a gap closes, delete the
row.

## Currently host-independent (good ✓)

- **MCP daemon** — runs on DO Droplet `workflow-daemon-1`
  (`161.35.237.133`), container auto-restarts, watchdog + compose both
  set to `restart: unless-stopped`. Fully independent.
- **Cloudflare Worker + tunnel + DNS** — all at Cloudflare.
- **GitHub repo + GHCR image** — at GitHub; new pushes auto-build via
  `build-image.yml`.
- **GHA uptime-canary.yml** — every 5 min; opens `p0-outage` issue on
  consecutive red.
- **GHA dns-canary.yml** — every 15 min; opens `dns-red` issue on
  consecutive red.
- **GHA emergency-dns.yml** — manually triggerable from dashboard to
  flip DNS without host SSH.
- **GHA build-image.yml** — publishes GHCR on push to main.
- **Claude.ai MCP connector** — cloud; reaches the Droplet
  independently of host's machine.

## Host-dependent today — must close ✗

### HD-1 — Droplet SSH key only on host's disk

- **Where it lives:** `~/.ssh/workflow_deploy_ed25519` (private) +
  `~/.ssh/workflow_deploy_ed25519.pub` (public) on host's Windows
  machine.
- **Also in:** `/root/.ssh/authorized_keys` on the Droplet (public
  half — one line, matches the key above).
- **What breaks when host is off:** Nobody can SSH the Droplet.
  `deploy-prod.yml` can't deploy. Emergency repairs stall.
- **Close action (host, ~2 min):**
  1. GitHub → repo Settings → Secrets and variables → Actions → New
     repository secret.
  2. Add `DO_SSH_KEY` = contents of `~/.ssh/workflow_deploy_ed25519`
     (the full private-key PEM including `-----BEGIN` and `-----END`
     lines).
  3. Add `DO_DROPLET_HOST` = `161.35.237.133`.
  4. Add `DO_SSH_USER` = `root`.
- **Also recommended:** save a password-manager backup of the private
  key. If the single `authorized_keys` line is corrupted, you need
  this key to restore access.

### HD-2 — `workflow-secrets.env` only on host's disk

- **Where it lives:** `$HOME/workflow-secrets.env` on host's Windows
  machine (referenced from the in-repo `.env` pointer per
  `memory/project_secrets_outside_repo.md`).
- **Contents (redacted):** `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`,
  `DIGITALOCEAN_TOKEN`, `HETZNER_EMAIL`, `HETZNER_PASSWORD`,
  `OPENAI_API_KEY`.
- **What breaks when host is off:** Any lead session on a different
  machine can't source secrets; token rotation can't happen locally.
- **Close action:** password-manager backup of the full file
  (1Password / Bitwarden / age-encrypted blob in a separate private
  repo). Not committed anywhere.
- **Also needed in GH Actions secrets:**
  - `CLOUDFLARE_API_TOKEN` — for Worker deploy + emergency DNS.
  - `DIGITALOCEAN_TOKEN` — for droplet-level actions from CI (reboot,
    resize, snapshot).

### HD-3 — LLM endpoint not bound on prod daemon

- **What's missing:** `/etc/workflow/env` on the Droplet has no
  `ANTHROPIC_BASE_URL` / `OLLAMA_HOST` / API key. Daemon reports
  `llm_endpoint_bound: unset`.
- **What breaks when host is off:** daemon can accept + queue
  requests but can't execute any. `concordance` universe currently
  has 1 pending request, `phase: starved`.
- **Why local Ollama won't work:** Droplet is 960 MB RAM / 1 vCPU; no
  usable model fits.
- **Close action (host):**
  1. Generate an `ANTHROPIC_API_KEY` at https://console.anthropic.com.
  2. Paste into `$HOME/workflow-secrets.env` as
     `ANTHROPIC_API_KEY=sk-ant-...` and tell the lead.
  3. Lead adds it to `/etc/workflow/env` on the Droplet + restarts
     compose.
  4. Eventually: also add `ANTHROPIC_API_KEY` as a GH Actions secret
     so CI can seed it to fresh Droplets without host SSH.
- **Alternative:** resize Droplet to ≥ 4 GB, install Ollama locally.

### HD-4 — Cloudflare Global API Key exposed in host's terminal history

- **Provenance:** host pasted `CLOUDFLARE_GLOBAL_KEY` in-session
  2026-04-20; lead used it in `cf_access_cutover.py --apply`. Key is
  now in lead's conversation context + terminal scrollback.
- **What breaks when host is off:** low risk; Global Key rotation is
  dashboard-only so host going off doesn't change the risk profile.
- **Close action (host, ~30 sec):** Cloudflare → My Profile → API
  Keys → Global API Key → Change. No paste-back needed.

### HD-5 — Layer-1 canary on host's Windows Task Scheduler

- **Where it runs:** host's Windows Task Scheduler, every 2 min,
  writes `.agents/uptime.log` on host.
- **What breaks when host is off:** this canary silently stops. GHA
  uptime-canary.yml (Row H) is the host-independent replacement and
  is green — keep both for defense in depth, but the GHA one is the
  load-bearing layer.
- **Close action:** none needed (GHA replacement already live);
  document expected-stop-when-host-off in
  `docs/ops/host-independence-runbook.md`.

### HD-6 — This Claude Code lead session itself

- **Where it runs:** host's terminal.
- **What breaks when host is off:** current lead + teammate processes
  die; coordination state survives only via committed files
  (STATUS.md, memory, git, audit docs).
- **Close action:** guardrails already in place — every material
  decision gets committed to STATUS.md / a design note before session
  end. The next session on any machine rehydrates from those files.

## Summary ledger

| ID | Gap | Host-action-minutes | Blocks |
|---|---|---|---|
| HD-1 | SSH key host-only | ~2 | CI auto-deploy |
| HD-2 | secrets.env host-only | ~5 | Disaster recovery |
| HD-3 | LLM endpoint unset | ~1 + key mint | Daemon requests execute |
| HD-4 | Global API Key rotation | ~0.5 | Credential hygiene |
| HD-5 | Windows Task canary host-only | 0 (deprecated) | Nothing (GHA replaces) |
| HD-6 | Lead session host-only | 0 (by design) | Nothing (state in files) |

Actionable today: HD-1, HD-2, HD-3, HD-4. All require host input. When
a gap closes, delete its section and the matching ledger row.
