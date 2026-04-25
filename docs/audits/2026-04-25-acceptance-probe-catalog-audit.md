# Acceptance Probe Catalog Audit

**Date:** 2026-04-25
**Author:** dev-2
**Source catalog:** `docs/ops/acceptance-probe-catalog.md` (rev 2026-04-20)
**Scope:** verify every named probe (path, invocation, canonical endpoint) and surface coverage gaps
**Mode:** read-only audit — no code changes.

---

## Summary

Two named probes (PROBE-001, PROBE-002) are documented in the catalog. Both target the canonical `https://tinyassets.io/mcp` endpoint correctly at the catalog level. **One stale-endpoint defect** exists in the underlying script `scripts/mcp_public_canary.py` (default URL still `mcp.tinyassets.io/mcp`). At least **eight additional probe scripts** exist in the repo that test uptime surfaces but are NOT registered in the catalog — coverage gap or simple under-documentation, depending on intent.

The catalog itself is well-structured (validated date, source audit, prompt verbatim, green/red criteria, baseline evidence). It just hasn't kept pace with the proliferation of canary scripts since the 2026-04-20 selfhost cutover.

---

## Per-probe table

| Name | Doc'd path | Doc'd invocation | Status | Notes |
|---|---|---|---|---|
| PROBE-001 | `scripts/mcp_public_canary.py` (implied via Hard Rule #10) | Catalog: paste-prompt against `tinyassets.io/mcp`. Hard Rule #10: `python scripts/mcp_public_canary.py --url https://tinyassets.io/mcp` | **YELLOW** — script exists, catalog target URL correct, but the script's DEFAULT_URL is stale (`mcp.tinyassets.io/mcp`). Operators MUST pass `--url` explicitly to be Hard-Rule-#10-compliant. | See Defect 1 below. |
| PROBE-002 | `scripts/uptime_canary_layer2.py` (implied — catalog says "once `scripts/uptime_canary.py` Layer-2 path is implemented", but the Layer-2 path is now its own file) | Manual prompt via Claude.ai persona; designed-but-not-live | **GREEN-design** | Catalog correctly notes "design-validated (not yet live-run)". Consistent with catalog's own admission criteria. |

---

## Defect 1: `mcp_public_canary.py` default URL is stale

**File:** `scripts/mcp_public_canary.py`
**Line 41:** `DEFAULT_URL = "https://mcp.tinyassets.io/mcp"`
**Line 23 (docstring example):** `python scripts/mcp_public_canary.py --url https://mcp.tinyassets.io/mcp`
**`--help` output confirms:** `--url URL  MCP endpoint URL (default https://mcp.tinyassets.io/mcp)`

**Why this matters.** AGENTS.md Hard Rule #10 is explicit:

> Canonical public endpoint is `https://tinyassets.io/mcp` only. `mcp.tinyassets.io` is an Access-gated internal tunnel origin (host directive 2026-04-20) — it exists in DNS but is not user-facing; direct requests without the Worker's CF Access service-token headers return 401/403. Do not document or share `mcp.tinyassets.io` in user-facing contexts.

The canary script itself, by virtue of its `--help` output and docstring, currently violates "do not document or share `mcp.tinyassets.io` in user-facing contexts." A bare `python scripts/mcp_public_canary.py` invocation will probe the gated origin and red-canary on 401/403 — falsely indicating an outage when the canonical endpoint is fine.

**Evidence in `.agents/uptime.log`:**
```
2026-04-19T17:42:32-07:00 GREEN layer=1 url=https://mcp.tinyassets.io/mcp rtt_ms=230
2026-04-23T23:39:08-07:00 GREEN layer=1 url=https://tinyassets.io/mcp rtt_ms=223
```
Pre-cutover entries (2026-04-19) hit the deprecated host. Post-cutover (2026-04-23) hit canonical via the wrapper `uptime_canary.py` which has the correct `DEFAULT_URL = "https://tinyassets.io/mcp"`. The wrapper masks the bug; direct calls do not.

**Recommendation.** Three lines change:
- Line 23 docstring example: switch the deprecated URL to canonical.
- Line 41: `DEFAULT_URL = "https://tinyassets.io/mcp"`.
- Optionally add a sentence to the docstring explaining `mcp.tinyassets.io/mcp` was the historical origin and is no longer user-facing.

---

## Coverage gap: probes not in the catalog

The catalog says "Named, validated probes for testing the full System → Chatbot → User chain." Since the 2026-04-20 cutover, eight additional canary scripts have been added that probe uptime surfaces. None are catalogued.

| Script | Surface tested | Currently registered? | Catalog admission status |
|---|---|---|---|
| `scripts/mcp_public_canary.py` | MCP `initialize` handshake | implicitly via PROBE-001 | covered (just stale default — see Defect 1) |
| `scripts/uptime_canary.py` | Layer-1 wrapper around `mcp_public_canary` w/ logging | not separately listed | borderline — wrapper, not a unique surface |
| `scripts/uptime_canary_layer2.py` | Claude.ai connector liveness via persona | implicitly PROBE-002 | covered |
| `scripts/mcp_tool_canary.py` | end-to-end MCP `tools/list` + `universe action=inspect` | not catalogued | **GAP** — tests "handshake green, tool handler crashed" failure class explicitly named in script docstring (task #6) |
| `scripts/wiki_canary.py` | wiki write+read roundtrip (P0 — Forever Rule auto-heal pipeline) | not catalogued | **GAP** — explicit P0 surface per script docstring; closes BUG-028 silent-bug class |
| `scripts/last_activity_canary.py` | activity log freshness | not catalogued | **GAP** — exists with its own test file `tests/test_last_activity_canary.py` |
| `scripts/revert_loop_canary.py` | guards against revert-loop pathology (cf. STATUS Concern 2026-04-23 P0) | not catalogued | **GAP** — has spec at `docs/design-notes/2026-04-23-revert-loop-canary-spec.md` |
| `scripts/uptime_alarm.py` | escalation/Pushover paging | not catalogued | maybe-not-a-probe (it's the alarm action, not a probe per se) |
| `scripts/selfhost_smoke.py` | parity between canonical + tunnel during 48h offline acceptance | not catalogued | borderline — explicitly time-bounded (Row F acceptance) |

The `wiki_canary.py` and `mcp_tool_canary.py` gaps are the most urgent because:
1. Both target Forever-Rule uptime surfaces (wiki write = auto-heal pipeline; tool-invocation = "tier-1 chatbot users create / browse / collaborate" path).
2. Both have green-criteria parseable without human judgment (catalog admission criterion #3).
3. Both have validated invocations — `--help` works; signature matches the catalog's expected pattern.

The `revert_loop_canary.py` gap is interesting because the P0 revert-loop concern is currently the top-of-STATUS Concern. A catalogued reference probe for it would close the loop between Concern → Probe → green-baseline.

---

## Coverage gap: PROBE-002 implementation drift

The catalog (line 118) says:

> Automated hourly Layer-2 canary (once `scripts/uptime_canary.py` Layer-2 path is implemented).

This is now stale — the Layer-2 canary lives at `scripts/uptime_canary_layer2.py` (its own file, not a path inside `uptime_canary.py`). PROBE-002's "When to use" section needs an update to point at the actual script. The probe's logic itself is correctly implemented; only the catalog's pointer is wrong.

---

## Coverage gap: post-fix clean-use evidence is not a probe

AGENTS.md Quality Gates section names "Post-fix clean-use evidence" as a verification primitive — checking that real users have used the affected feature cleanly since a fix landed. The catalog has no probe for this. Per the catalog's admission criteria this might not qualify (it's evidence-gathering, not a parseable probe), but it's worth flagging because it's a verification primitive that has no automation hook today.

---

## Verifying the catalog itself

Catalog file lives at `docs/ops/acceptance-probe-catalog.md`. Last modified 2026-04-20. All section headings and the validated/source/persona/connector-URL fields match the documented structure. No dead links found in the audit-source paths it references. Catalog text correctly states `tinyassets.io/mcp` is canonical and notes the single-URL architecture amendment.

---

## Recommendations (no code changes in this audit)

Lead routes any follow-up tasks separately. Suggestions, in priority order:

1. **Fix Defect 1** (3-line edit to `mcp_public_canary.py`): retire stale `DEFAULT_URL`. Trivial dev task; can ship in any docs/test bundle.
2. **Add `wiki_canary` and `mcp_tool_canary` as PROBE-003 / PROBE-004** in the catalog. Both meet the admission criteria; both target Forever-Rule surfaces.
3. **Update PROBE-002 implementation pointer** from `scripts/uptime_canary.py` to `scripts/uptime_canary_layer2.py`.
4. **Decide: catalog `revert_loop_canary` or leave it as a Concern-side artifact?** Either is defensible; the choice depends on whether the revert-loop class is a permanent uptime invariant or a transient post-mortem-driven check.
5. **Optional:** add a "post-fix clean-use evidence" section noting it's a verification primitive without a current probe automation hook, so future engineers know this is intentional vs accidental.

---

## What this audit does NOT cover

- Whether the probes' **green criteria** would actually catch all real-world failure modes. (The 2026-04-19 P0 outage's class — "no commit touched the broken surface" — is by design only catchable by out-of-band probes; PROBE-001 catches that class, but other classes may exist.)
- Live-run validation of any probe. This audit is paper-only — script existence + signature + endpoint check. To certify any probe green requires actually running it against the production endpoint with the canary's own exit codes.
- Probe-runner orchestration (Task Scheduler entries, GHA workflow `uptime-canary.yml`). The catalog assumes infrastructure exists; this audit doesn't verify that side.
