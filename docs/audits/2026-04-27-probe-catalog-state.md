---
title: Acceptance probe catalog — state audit + gap analysis
date: 2026-04-27
author: dev-2
status: read-only audit
audience: lead, host, navigator
load-bearing-question: Does the canonical probe catalog at `docs/ops/acceptance-probe-catalog.md` match the actual canary fleet on disk + in CI, and what regression class would still escape detection?
---

# Acceptance probe catalog — state audit

## Summary

**6 cataloged probes. 10 implementing scripts. 5 uncataloged CI canary workflows that meet the catalog's own admission criteria.** No documented-but-not-implemented gaps. **5 implemented-but-not-documented gaps** (one critical: DNS canary closes the exact silent-tunnel-route-drop class from the 2026-04-19 P0). Freshness across the cataloged 6 is current (last live-run dates 2026-04-20 → 2026-04-26). Catalog § "Borderline scripts" handles 3 of the 4 remaining scripts correctly; one CI workflow (`dr-drill.yml`) is intentionally excluded but worth referencing.

The most consequential finding is **PROBE-007 missing**: `dns-canary.yml` runs every 15 min on GHA, opens `dns-red` issues on failure, and is the ONLY surface that would catch the 2026-04-19 P0 outage class (DNS NXDOMAIN at the apex during a tunnel reshuffle). It's live in CI, has explicit consecutive-state alarm logic, but isn't a catalog entry. Cataloging it closes a meaningful documentation gap.

## 1. Catalog-vs-implementation matrix

| Catalog probe | Implementing script | Live? | Last validated | Notes |
|---|---|---|---|---|
| PROBE-001 (full-stack smoke) | `scripts/mcp_public_canary.py` (+ `uptime_canary.py` wrapper) | YES | 2026-04-20 | Catalog correctly notes wrapper is borderline-not-cataloged. |
| PROBE-002 (Layer-2 liveness) | `scripts/uptime_canary_layer2.py` | DESIGN-ONLY per catalog | 2026-04-19 design-only | Script exists with full exit-code table; catalog says "not yet live-run as automated probe." Verify: was Task Scheduler entry `Workflow-Canary-L2` ever wired? If yes, catalog is stale. If no, script is shelfware. |
| PROBE-003 (wiki write-roundtrip) | `scripts/wiki_canary.py` | YES (CI 5-min) | 2026-04-26 | Step in `.github/workflows/uptime-canary.yml`. Confirmed. |
| PROBE-004 (MCP tool-invocation) | `scripts/mcp_tool_canary.py` | YES | 2026-04-22 | Confirmed. |
| PROBE-005 (last-activity freshness) | `scripts/last_activity_canary.py` | YES (CI 5-min) | 2026-04-26 | Step in `.github/workflows/uptime-canary.yml`. Tests at `tests/test_last_activity_canary.py`. Confirmed. |
| PROBE-006 (revert-loop detection) | `scripts/revert_loop_canary.py` | YES (CI 5-min) | 2026-04-26 | Step in `.github/workflows/uptime-canary.yml`. Spec at `docs/design-notes/2026-04-23-revert-loop-canary-spec.md`. Confirmed. |

**(a) Documented-but-not-implemented:** none. All 6 catalogued probes have implementing scripts. PROBE-002's "design-validated only" caveat is internal to the catalog and not a contradiction — but worth re-checking whether the Task Scheduler L2 entry is still missing or has been wired since 2026-04-19.

**(b) Implemented-but-not-documented:** see §2.

**(c) Freshness:** all 6 last-validated dates are within the last 14 days, well inside the catalog's "living doc" cadence.

**(d) Gap vs 2026-04-19 P0 silent-tunnel-route-drop:** see §3.

## 2. Implemented-but-not-documented (5 findings)

These are CI workflows or live scripts that meet the catalog's own admission criteria (live-run, parseable green/red, distinct failure class) but have no PROBE-NNN entry. Two close exact gaps from the 2026-04-19 P0 postmortem.

### 2.1 PROBE-007 candidate — DNS canary (`.github/workflows/dns-canary.yml`)

- **Cadence:** every 15 min (cron `*/15 * * * *`) + manual dispatch.
- **Vantage:** GHA runner, host-independent.
- **Surface tested:** DNS resolution of `tinyassets.io` + `mcp.tinyassets.io` from out-of-band.
- **Alarm:** opens `dns-red` GH Issue on 2 consecutive reds; closes + comments RECOVERED on green.
- **Why a slot:** this is the **only** probe in the fleet that catches a CNAME deletion / NXDOMAIN at the apex — the exact 2026-04-19 P0 class. The catalog explicitly enumerates the silent-tunnel-route-drop failure mode in PROBE-001's discussion of "post-incident correction" but doesn't catalog the probe that catches it. Add PROBE-007.

### 2.2 PROBE-008 candidate — LLM binding canary (`.github/workflows/llm-binding-canary.yml`)

- **Cadence:** every 6h.
- **Surface tested:** live `get_status.evidence.llm_endpoint_bound != "unset"`.
- **Alarm:** `llm-binding-red` GH Issue on 2 consecutive reds.
- **Distinct failure class:** "MCP green, tools call cleanly, but no LLM is bound" — node execution would mock-fall-back or fail loudly per hard rule #8. PROBE-002 (in design) has overlap on the `llm_endpoint_bound` field, but PROBE-002 routes via the chatbot UI; this one calls the daemon directly from GHA. Different vantage, different cadence, different failure mode (subscription drift, codex CLI version regression, docker restart). Earns a slot.

### 2.3 Tier-3 OSS clone nightly (`.github/workflows/tier3-oss-clone-nightly.yml`)

- **Cadence:** nightly.
- **Surface tested:** fresh `git clone` → `pip install -e .` → smoke pytest.
- **Alarm:** GH Issue + commit-status fail.
- **Why:** explicitly named in the 2026-04-20 postmortem §6 ("Highest-priority post-canary addition: tier-3 OSS clone nightly probe") + AGENTS.md Forever Rule. Not in the catalog.
- **Catalog admission test:** does it have one green baseline + one red baseline? Yes (it commit-statuses every nightly run). Does it have parseable green/red? Yes (exit code + commit-status). Earns a slot — propose PROBE-009.

### 2.4 P0 outage auto-triage (`.github/workflows/p0-outage-triage.yml`)

- **Trigger:** workflow_dispatch + auto-fired by uptime-canary on CRITICAL.
- **Function:** action, not probe — runs forensics + opens issue. Belongs in catalog §"Borderline" alongside `uptime_alarm.py`. No new slot needed but worth listing under Borderline so future audits don't keep re-finding it.

### 2.5 DR drill (`.github/workflows/dr-drill.yml`)

- **Trigger:** workflow_dispatch only — quarterly recovery rehearsal per STATUS Work row.
- **Function:** acceptance-test-as-CI, not a probe. Same as `selfhost_smoke.py` (already correctly cataloged as Borderline). Catalog should list it under Borderline for completeness.

## 3. Gap vs 2026-04-19 P0 silent-tunnel-route-drop class

Postmortem `docs/audits/2026-04-20-public-mcp-outage-postmortem.md` §3 named three monitoring gaps. State today:

| Gap | Postmortem state | Today's state |
|---|---|---|
| Weekly probe cadence too coarse | OPEN | **CLOSED** — `uptime-canary.yml` 5-min + `dns-canary.yml` 15-min. |
| Apex root probe doesn't probe `/mcp` path | OPEN | **CLOSED** — PROBE-001/002/004 all probe `/mcp`. |
| No connector-layer probe | OPEN | **PARTIAL** — PROBE-002 designed; live-run status unconfirmed in catalog. |

Postmortem §6 enumerated other unmonitored surfaces. State today:

| Surface | Postmortem rec | Today's state |
|---|---|---|
| Tier-1 chatbot MCP | Layer-1 + Layer-2 canary | CLOSED via PROBE-001/004; PROBE-002 uncertain live status |
| Tier-3 OSS clone | Add nightly GHA | **CLOSED but uncatalogued** — `tier3-oss-clone-nightly.yml` exists; not in catalog (§2.3 above) |
| Tier-2 fresh-install rehearsal | Quarterly runbook | UNKNOWN — runbook status not surfaced in catalog |
| Node discovery / remix / converge | Once shipped | NOT-YET-SHIPPED |
| Paid-market inbox | Once shipped | NOT-YET-SHIPPED |
| Moderation | Skip | SKIP (correct) |
| Landing page root `tinyassets.io/` | Add to Layer-1 | NOT-DONE — no probe of apex root vs `/mcp` differential. The 2026-04-19 P0 specifically distinguished "apex serves W+M 200, /mcp returns 404" — a probe of the apex root in addition to /mcp would catch the inverse failure (W+M down, tunnel up). LOW-MEDIUM priority per postmortem §6. Worth filing as next-step probe. |

**Net:** the documented monitoring gaps from the 2026-04-19 P0 are largely closed in implementation but not all reflected in the catalog. The catalog is undersold relative to the actual fleet.

## 4. Concrete next-step probes worth adding

### 4.1 (Catalog only) Add PROBE-007 (DNS canary)

No new code. Add a §PROBE-007 entry to `docs/ops/acceptance-probe-catalog.md` mirroring the existing PROBE-NNN structure. ~15 min navigator/dev-2 task.

### 4.2 (Catalog only) Add PROBE-008 (LLM binding canary)

Same as 4.1 — catalog the existing `llm-binding-canary.yml`. ~10 min.

### 4.3 (Catalog only) Add PROBE-009 (Tier-3 OSS clone nightly)

Same — catalog `tier3-oss-clone-nightly.yml`. ~10 min.

### 4.4 (Catalog only) Extend Borderline §

Add `p0-outage-triage.yml` (action, not probe) and `dr-drill.yml` (quarterly rehearsal, not steady-state) to the Borderline section so future audits don't keep re-discovering them. ~5 min.

### 4.5 (New probe) Apex root vs /mcp differential

**The one genuinely missing probe.** Postmortem §6 row "Landing page root (`tinyassets.io/`)" recommends adding apex-root coverage to Layer-1. Today no canary distinguishes:

- Apex root (`tinyassets.io/`) — should serve GoDaddy W+M landing or static landing HTML
- `/mcp` path — should serve MCP daemon

The 2026-04-19 outage was "apex 200, /mcp 404" — caught by `/mcp` probe. The inverse "apex 5xx, /mcp green" would currently be UNDETECTED (cosmetic — landing page broken — but a Forever Rule surface per AGENTS.md "tier-1 chatbot users create / browse / collaborate via Claude.ai" — and the project's onboarding story routes new users through the landing page).

**Shape:** ~30 LOC stdlib script `scripts/landing_page_canary.py` doing GET on `https://tinyassets.io/` + asserting HTTP 200 + content-length > 0 + (optional) string match for a known landing-page sentinel. CI step in `.github/workflows/uptime-canary.yml`. Catalog as PROBE-010.

**Priority:** LOW-MEDIUM per postmortem §6. File but not urgent.

### 4.6 (Verify, don't add) PROBE-002 live-run status

Catalog says PROBE-002 (Layer-2 liveness) is "design-validated (not yet live-run as automated probe)." Script `uptime_canary_layer2.py` is fully implemented with exit-code table + Windows Task Scheduler reference (`Workflow-Canary-L2`). Either:

- The Task Scheduler entry was wired and the catalog is stale → update catalog with live-run date.
- The Task Scheduler entry was never wired → either wire it or move PROBE-002 to a "Designed but not live" appendix so the catalog's admission criterion ("run live, not just designed") stays true.

Either way, the inconsistency is small and low-risk — but worth resolving. ~30 min to investigate + decide.

## 5. What this audit does NOT cover

- Whether the existing 6 cataloged probes' alarm thresholds (e.g. PROBE-006's `N=3 in 10 min` warn / `N=5 in 20 min` crit) are well-tuned — that's a separate operational tuning audit.
- Whether the GHA cron `*/5 * * * *` cadence meets the postmortem's implicit ~5-min RTO — assumed yes per `uptime-canary.yml` design.
- Pager / Pushover routing — `pushover-test.yml` exists; out of scope.
- Wiki / supabase / GitHub-native monitoring — postmortem §6 already calls these out as "no action."

## 6. Cross-references

- `docs/ops/acceptance-probe-catalog.md` — canonical catalog this audit measures against.
- `docs/audits/2026-04-20-public-mcp-outage-postmortem.md` — 2026-04-19 P0; §3 + §6 named the gaps this audit re-measures.
- `.github/workflows/uptime-canary.yml` — main 5-min canary; runs PROBE-001/003/004/005/006 steps.
- `.github/workflows/dns-canary.yml` — PROBE-007 candidate (§2.1).
- `.github/workflows/llm-binding-canary.yml` — PROBE-008 candidate (§2.2).
- `.github/workflows/tier3-oss-clone-nightly.yml` — PROBE-009 candidate (§2.3).
- `.github/workflows/p0-outage-triage.yml` — Borderline addition (§2.4).
- `.github/workflows/dr-drill.yml` — Borderline addition (§2.5).
- `scripts/uptime_canary.py`, `scripts/uptime_canary_layer2.py`, `scripts/uptime_alarm.py`, `scripts/selfhost_smoke.py` — already correctly handled by catalog § "Borderline."
