# Host-Independence Runbook

Row N owner surface for bills, emergency DNS, and secrets expiry. This
runbook exists so a repo co-admin can keep the public surface alive without
the host being online or logging into vendor dashboards.

## 1. Billing Autonomy

| Vendor | Current role | Autonomous action | Proof to record |
|---|---|---|---|
| GoDaddy | Registrar for `tinyassets.io` | At next renewal window, pre-pay domain registration through 2031. | Renewal date in succession vault and this table. |
| Cloudflare | DNS, TLS, Worker route, tunnel hostname | Free tier is sufficient near-term. Re-evaluate Worker paid tier only if traffic approaches free quotas. | Billing plan and Worker request trend. |
| Hetzner | Row D self-host target | Pay 12 months in advance immediately after Row D is green. Review annually. | Paid-through date and invoice PDF in vault. |
| Supabase | Managed Postgres/project services | Switch to annual prepay at Row-D + 30 days if traffic pattern is stable. | Annual renewal date and invoice in vault. |
| Backup card | Payment continuity | Add a secondary card controlled by a co-admin with vault access. | Last four digits and vendor coverage in vault, never in repo. |

Rules:

- Do not put card numbers, recovery codes, API tokens, or invoice PDFs in git.
- If a billing action changes production reachability, run the public canary:
  `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose` (canonical apex — `mcp.tinyassets.io` is an Access-gated internal tunnel origin per host directive 2026-04-20, not a public URL).
- If a vendor dashboard has no prepay option, record the exact limitation and
  the next review date in `STATUS.md` as a concern.

## 2. Emergency DNS

Primary `/mcp` independence is the Row E Cloudflare Worker. This Row N DNS
tool covers residual cases: retiring `mcp.tinyassets.io` DNS records, future subdomains, MX,
TXT/SPF/DKIM, and emergency Worker route removal/restoration when the lead
explicitly asks for it.

Required GitHub secrets and variables:

| Name | Kind | Purpose |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | Secret | Cloudflare token with `Zone DNS Edit`; add `Workers Routes Edit` only if Worker route actions are needed. |
| `CLOUDFLARE_ZONE_ID` | Secret | Zone ID for `tinyassets.io`; avoids extra zone lookup failure paths. |
| `CLOUDFLARE_ZONE_NAME` | Repository variable | Defaults to `tinyassets.io` if unset. |

Dry-run a CNAME flip from GitHub Actions:

```powershell
gh workflow run emergency-dns.yml `
  -f action=upsert-record `
  -f record_type=CNAME `
  -f name=mcp.tinyassets.io `
  -f content=fallback.example.net `
  -f proxied=true `
  -f apply=false
```

Apply the same change:

```powershell
gh workflow run emergency-dns.yml `
  -f action=upsert-record `
  -f record_type=CNAME `
  -f name=mcp.tinyassets.io `
  -f content=fallback.example.net `
  -f proxied=true `
  -f apply=true `
  -f canary_url=https://tinyassets.io/mcp
```

The workflow runs `scripts/mcp_public_canary.py` after any applied change.
If the canary fails, revert immediately with the previous record target and
leave a `STATUS.md` concern.

Local dry-run, if GitHub Actions is down but a co-admin has the token:

```powershell
$env:CLOUDFLARE_API_TOKEN = "<from vault>"
$env:CLOUDFLARE_ZONE_ID = "<from vault>"
python scripts/emergency_dns_flip.py `
  --action upsert-record `
  --record-type CNAME `
  --name mcp.tinyassets.io `
  --content fallback.example.net `
  --proxied true
```

Local apply:

```powershell
python scripts/emergency_dns_flip.py `
  --action upsert-record `
  --record-type CNAME `
  --name mcp.tinyassets.io `
  --content fallback.example.net `
  --proxied true `
  --apply
python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp --verbose
```

Supported script actions:

| Action | Use |
|---|---|
| `upsert-record` | Create a missing DNS record or patch a single exact match. |
| `delete-record` | Delete a single exact DNS record match; no-op if absent. |
| `upsert-worker-route` | Create or update an exact Worker route pattern. |
| `delete-worker-route` | Delete an exact Worker route pattern. |

Safety behavior:

- The script is dry-run by default; `--apply` is required for mutation.
- Duplicate exact matches fail closed instead of guessing which record to edit.
- Tokens are read from environment variables and are never printed.
- TTL must be `1` for Cloudflare automatic TTL or a value from 60 to 86400.

## 3. Secrets Expiry

Monthly workflow: `.github/workflows/secrets-expiry-check.yml`.

The workflow opens a GitHub issue titled `SECRET EXPIRY: <name> in <N> days`
when a known secret expires inside the threshold. It uses `issues: write` on
`GITHUB_TOKEN` and dedupes against existing open issues with the same prefix.

Machine-readable metadata is stored as a repository variable named
`SECRETS_EXPIRY_METADATA_JSON`. This contains names and expiry dates only,
never secret values.

Example metadata:

```json
[
  {
    "name": "HETZNER_API_TOKEN",
    "provider": "hetzner",
    "expires_on": "2027-04-20",
    "runbook": "docs/ops/host-independence-runbook.md#hetzner-api-token"
  },
  {
    "name": "SUPABASE_SERVICE_ROLE_KEY",
    "provider": "supabase",
    "expires_on": "2027-04-20",
    "runbook": "docs/ops/host-independence-runbook.md#supabase-service-role-key"
  }
]
```

Manual dry-run with a known-expiring test item:

```powershell
gh workflow run secrets-expiry-check.yml `
  -f threshold_days=30 `
  -f dry_run=true `
  -f metadata_json='[{"name":"TEST_SECRET","provider":"test","expires_on":"2026-04-25","runbook":"docs/ops/host-independence-runbook.md"}]'
```

Manual issue-open test:

```powershell
gh workflow run secrets-expiry-check.yml `
  -f threshold_days=30 `
  -f dry_run=false `
  -f metadata_json='[{"name":"TEST_SECRET","provider":"test","expires_on":"2026-04-25","runbook":"docs/ops/host-independence-runbook.md"}]'
```

Known secret metadata table:

| Name | Provider | Expiry source | Rotation notes |
|---|---|---|---|
| `CLOUDFLARE_API_TOKEN` | Cloudflare | API verify endpoint when token exposes `expires_on`; otherwise metadata JSON. | Replace in GitHub secrets and succession vault. |
| `CLOUDFLARE_ZONE_ID` | Cloudflare | Non-secret identifier; no expiry. | Rotate only if zone is recreated. |
| `HETZNER_API_TOKEN` | Hetzner | Metadata JSON. | Create replacement token, update GitHub secret, revoke old token after green deploy check. |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Metadata JSON. | Rotate during low traffic; verify app can connect before revoking old key. |
| `GITHUB_OAUTH_CLIENT_SECRET` | GitHub | Metadata JSON. | Create new client secret, update consumers, then delete old secret. |

## 4. Acceptance Checks

Row N is complete when these checks pass:

1. `scripts/emergency_dns_flip.py` unit tests pass without network.
2. `emergency-dns.yml` dry-run completes from GitHub Actions with a test payload.
3. An applied DNS change is followed by a green public MCP canary, then reverted.
4. `secrets-expiry-check.yml` dry-run reports a known-expiring test secret.
5. `secrets-expiry-check.yml` non-dry-run opens one test issue and dedupes on rerun.
6. Billing prepay dates are recorded in the vault and reflected in section 1.

## 5. Watchdog Restart Signals

`scripts/watchdog.py` fires every 30 s via `workflow-watchdog.timer`. When 3 consecutive probes fail, it:

1. Issues `sudo systemctl restart workflow-daemon.service`.
2. Appends a `WATCHDOG_RESTART` line to `.agents/uptime_alarms.log`.
3. Opens a GitHub issue (label `watchdog`) if `GH_TOKEN` is set.

### Reading watchdog signals

```bash
# On the Droplet — live watchdog logs
journalctl -u workflow-watchdog -f

# Alarm log (also readable locally after sync)
tail -f /opt/workflow/.agents/uptime_alarms.log | grep WATCHDOG_RESTART

# GitHub issues opened by the watchdog
gh issue list --label watchdog --repo Jonnyton/Workflow
```

### Suppressing restarts during maintenance

```bash
# Stop the timer without disabling it permanently
systemctl stop workflow-watchdog.timer

# Resume when done
systemctl start workflow-watchdog.timer
```

### DRY_RUN mode

```bash
# Probe without restarting or emitting alarms — safe for smoke-testing the watchdog itself
DRY_RUN=1 python /opt/workflow/scripts/watchdog.py
# or
python /opt/workflow/scripts/watchdog.py --dry-run
```

---

## 6. P0 Auto-Triage

When `uptime-canary.yml` opens a `p0-outage` issue, `.github/workflows/p0-outage-triage.yml`
fires automatically:

1. SSHs into the Droplet using `DO_SSH_KEY` / `DO_DROPLET_HOST` / `DO_SSH_USER` secrets.
2. Captures pre-restart diagnostics (`docker ps`, compose status, journalctl tail).
3. Runs `docker compose up -d --force-recreate daemon` (non-destructive; data volume untouched).
4. Waits 30s, re-probes `https://tinyassets.io/mcp`.
5. **Green**: comments auto-recovered + closes the issue.
6. **Still red**: comments diag output + adds `needs-human` label. GHA run marked failed.

Required secrets (same set as `deploy-prod.yml`): `DO_SSH_KEY`, `DO_DROPLET_HOST`, `DO_SSH_USER`.

If secrets are missing, the workflow comments and exits 1 — the `p0-outage` issue stays open
for manual response.

---

## 7. LLM Binding Canary

`.github/workflows/llm-binding-canary.yml` runs every 6 hours via GHA schedule.
It calls `scripts/verify_llm_binding.py --url https://tinyassets.io/mcp` and
checks that `llm_endpoint_bound` in `get_status` is not `"unset"`.

**Consecutive-fail logic (threshold = 2):**
- First red: logs to step summary, no issue opened.
- Second consecutive red: opens `llm-binding-red` GH issue with probe output.
- Recovery (green after open issue): comments RECOVERED + closes issue.

**Likely causes when it fires:**
- `OPENAI_API_KEY` rotated or expired in `/etc/workflow/env`
- `codex` CLI missing from the container image (image rebuild needed)
- Container restarted without env file (`docker compose down` + manual restart)
- `OLLAMA_HOST` or `ANTHROPIC_BASE_URL` unset after host reconfiguration

**Manual re-check:**
```bash
python scripts/verify_llm_binding.py --url https://tinyassets.io/mcp
```
Exit 0 = bound. Exit 3 = unset. See `scripts/verify_llm_binding.py` for full
exit code table.

No extra secrets required — uses only `GITHUB_TOKEN` (built-in).

---

## 8. References

- Cloudflare DNS Records API: <https://developers.cloudflare.com/api/resources/dns/>
  lists create, patch, and delete endpoints under `/zones/{zone_id}/dns_records`.
- Cloudflare Workers Routes API:
  <https://developers.cloudflare.com/api/resources/workers/subresources/routes/methods/list/>
  documents route list/create/update/delete under `/zones/{zone_id}/workers/routes`.
- Cloudflare API token verify endpoint:
  <https://developers.cloudflare.com/fundamentals/api/get-started/create-token/>
  documents `/user/tokens/verify`.
- GitHub Actions `GITHUB_TOKEN` docs:
  <https://docs.github.com/en/actions/tutorials/authenticate-with-github_token>
  show `issues: write` for automated issue creation.
