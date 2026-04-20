# Tier-3 OSS Clone Nightly GHA — Spec

**Date:** 2026-04-19
**Author:** navigator
**Status:** Design spec. Follow-up from `docs/audits/2026-04-20-public-mcp-outage-postmortem.md` §6 — "highest-priority post-canary addition." Not coded; ready for dev pickup after canary Layer 1 lands.
**Lens:** 3-layer chain. Tier-3 is a public surface (OSS contributor clones the repo). The canary lens applies identically: if `git clone` → install → smoke-test fails silently on `main`, contributors bounce without telling us. Same silent-outage shape as the 2026-04-19 MCP break, different surface.

---

## 1. Why this matters

Per AGENTS.md Forever Rule: *"tier-3 OSS contributors `git clone` and run cleanly"* is one of six uptime surfaces with equal severity. Current state:

- **Zero monitoring** of whether `main` is installable + testable on a clean machine.
- Pre-commit hooks exercise the **developer's already-set-up** environment. They do not catch "fresh clone fails."
- Recent near-misses: `stale pycache fakes regressions` (per user memory) demonstrates how local state can mask real regressions. A nightly fresh-clone run has no local state to mask anything.
- One bad commit (missing dep in `pyproject.toml`, import added without export, test-file accidentally gitignored) = silent tier-3 outage until a contributor tries on a real fresh machine.

The canary closes the tier-1 chatbot surface. This GHA closes the tier-3 OSS surface. Both are equally P0 per the forever rule; both have the same shape (out-of-band probe, alarm-on-red).

---

## 2. File layout

| Path | Purpose |
|---|---|
| `.github/workflows/tier3-oss-clone-nightly.yml` | GHA definition. Nightly + manual-dispatch. |
| `scripts/tier3_smoke.py` | Smoke test the GHA runs after install. Stdlib-only Python. Importable locally too. |
| `tests/smoke/` | Minimal pytest collection the GHA runs. ~5 tests; each <1 s. |
| `docs/design-notes/2026-04-19-tier3-oss-clone-nightly-gha.md` | This spec. |

---

## 3. Success gate (what the GHA asserts)

Six sequential checks. Failing any = alarm. All must pass for green:

| # | Check | Failure means |
|---|---|---|
| 1 | `git clone` from `main` into a scratch dir succeeds within 60 s | Repo too large, submodule breakage, LFS misconfig |
| 2 | `python -m venv` succeeds on a GHA-provisioned Python 3.11 runner | Python-version drift (Hard Rule 7) |
| 3 | `pip install -e .` succeeds within 5 min | Missing dep, broken `pyproject.toml`, unpinnable transitive |
| 4 | `python -c "import workflow"` succeeds | Top-level import regression |
| 5 | `python scripts/tier3_smoke.py` passes | Structural smoke: key modules import, key classes exist |
| 6 | `pytest tests/smoke/ -x --no-header -q` passes within 2 min | Smoke tests catch load-bearing regressions |

**Total runner budget:** ~10 min wall. GHA free-tier cost: ~300 min/month at 30 runs + retries; well within the 2000 free minutes.

---

## 4. GHA workflow file (stub — dev refines at implementation time)

```yaml
name: tier3-oss-clone-nightly

on:
  schedule:
    - cron: '17 7 * * *'  # 07:17 UTC daily — avoid top-of-hour contention
  workflow_dispatch:

permissions:
  contents: read

jobs:
  fresh-clone-smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Fresh clone (separate step from actions/checkout to simulate OSS contributor path)
        run: |
          git clone --depth 1 https://github.com/${{ github.repository }} /tmp/workflow-fresh
          cd /tmp/workflow-fresh
          git rev-parse HEAD

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Create venv
        working-directory: /tmp/workflow-fresh
        run: python -m venv .venv

      - name: pip install -e .
        working-directory: /tmp/workflow-fresh
        run: |
          source .venv/bin/activate
          python -m pip install --upgrade pip
          pip install -e .

      - name: Import smoke
        working-directory: /tmp/workflow-fresh
        run: |
          source .venv/bin/activate
          python -c "import workflow; print(workflow.__file__)"

      - name: Structural smoke
        working-directory: /tmp/workflow-fresh
        run: |
          source .venv/bin/activate
          python scripts/tier3_smoke.py

      - name: Smoke pytest
        working-directory: /tmp/workflow-fresh
        run: |
          source .venv/bin/activate
          pip install pytest
          pytest tests/smoke/ -x --no-header -q

      - name: Alarm on failure
        if: failure()
        run: |
          echo "Tier-3 OSS clone smoke FAILED on commit $(cd /tmp/workflow-fresh && git rev-parse HEAD)"
          # Future: POST to a webhook or open a GitHub issue automatically
          exit 1
```

**Dev refinement latitude:** exact Python version matrix (single 3.11 first-draft; add 3.12 + 3.13 post-MVP when CI budget allows); whether to use `uv` instead of `pip` (skip for first-draft — fewer moving parts); whether to run on Windows runner too (eventually yes — host is on Windows; skip first-draft).

---

## 5. Structural smoke (`scripts/tier3_smoke.py`) — spec

Checks to include:

1. `from workflow import daemon_server` (the core public entry point) — succeeds.
2. `from workflow.universe_server import mcp` — MCP object exists.
3. MCP object's registered tools set is non-empty (`len(mcp._tools) > 0` or equivalent public accessor).
4. `from workflow.bid import ...` imports the canonical bid surface (verifies R2 end-state didn't regress).
5. `from workflow.catalog import ...` imports the catalog surface (verifies R7a end-state didn't regress).
6. Domain skill discovery: `workflow.domains` enumerates at least `fantasy_daemon`.

Stdlib-only. Each assertion fails loudly with a clear message (Hard Rule 8 — fail loudly). ~50 LOC.

**Discipline:** structural smoke is NOT a test-suite replacement. Its job is "fresh install is not broken" not "all features work." If structural smoke passes but `pytest` finds real bugs, the GHA correctly reports green on the install-and-import surface and we ship a different monitor for the feature-correctness surface.

---

## 6. Smoke pytest (`tests/smoke/`) — spec

~5 tests, each <1 s wall. Examples:

- `test_mcp_tools_list_non_empty.py` — instantiate the MCP, call `tools/list`, assert ≥1 tool.
- `test_get_status_callable.py` — invoke `get_status` with no-args; assert it returns JSON-parseable string.
- `test_sqlite_saver_importable.py` — `from langgraph.checkpoint.sqlite import SqliteSaver` (Hard Rule 1).
- `test_plan_md_exists.py` — `Path("PLAN.md").exists()` — prevents accidental deletion of load-bearing doc.
- `test_domains_fantasy_daemon_registered.py` — fantasy_daemon domain registers cleanly.

**Keep smoke tests distinct from `tests/test_*.py`** (the main suite). Smoke is "does the project boot at all"; main suite is "does it work correctly." Different bugs, different fixes.

---

## 7. Alarm shape

First-draft: GHA `failure()` step prints a clear error + exits non-zero. GitHub sends host the standard failure email via repo settings.

**Deferred (follow-up commits):**
- Open a GitHub issue automatically on failure with commit SHA + failed step + last 20 log lines.
- POST to a Slack/Discord webhook.
- Write to `.agents/uptime.log` via a separate cross-repo automation (GHA can't write directly to the main repo without a PAT; punt).

For MVP, email alarm is enough — host checks GitHub email daily; the test cadence (nightly) matches that response time.

---

## 8. Failure-mode coverage

Compare to what breaks today without this GHA:

| Failure mode | Caught by this GHA? |
|---|---|
| Missing dep added to code but not `pyproject.toml` | YES — step 3 (pip install -e) fails on next import |
| `pyproject.toml` accidentally removes a required dep | YES — step 4 import fails |
| Test file accidentally gitignored | YES — step 6 smoke pytest count regresses below expected |
| Python 3.11 vs 3.12 incompatibility introduced | PARTIAL — 3.11-only matrix catches 3.12 compat bugs only if we add a 3.12 job (deferred) |
| Entry-point (`[project.scripts]`) regression | YES — would break step 3 or step 4 |
| LFS file reference broken | YES — step 1 clone fails |
| Submodule breakage | YES — step 1 clone fails |
| Import cycle introduced | YES — step 4 or step 5 raises |
| Rename regression (e.g., `workflow.author_server` → `workflow.daemon_server`) | YES — step 5 structural smoke asserts canonical import succeeds |
| Ruff/formatting regression | NO — by design; that's pre-commit-hook scope |
| Feature-correctness bug | NO — by design; that's main test suite scope |
| Runtime MCP outage (today's P0) | NO — different surface; covered by uptime canary |

The GHA covers **install + import + structural-integrity** surface. Ruff, feature tests, and runtime uptime are deliberately out of scope.

---

## 9. Cost + ship-date estimate

- **Dev time:** ~0.5 dev-day (GHA yml, structural smoke script, 5 smoke tests, README line in `docs/`).
- **CI time:** ~300 GHA min/month (30 runs × 10 min). Free tier has 2000 min/month for public repos (unlimited for public). Zero marginal cost.
- **Maintenance:** low — smoke surface is stable. Only revisit when major structural changes land (new package, new domain).
- **Ship trigger:** after canary Layer 1 lands in-repo (same dev, sequential task).

---

## 10. Interaction with existing monitoring

| Monitor | Covers | Ships |
|---|---|---|
| `SUCCESSION.md` §165 weekly cron | Domain WHOIS + `tinyassets.io` root | Exists (not load-bearing for P0) |
| Canary Layer 1 (2-min) | Public MCP endpoint routing | In-flight |
| Canary Layer 2 (hourly) | Claude.ai connector behavior | In-flight |
| **This GHA (nightly)** | **Tier-3 OSS install + import** | **This spec** |
| Main pytest (pre-commit + CI) | Feature correctness | Exists |
| Pre-commit hooks (ruff, mirror, mojibake) | Commit-local invariants | Exists |

Non-overlapping. Each covers a different failure mode. Together they cover the four uptime surfaces from AGENTS.md Forever Rule plus developer-workflow correctness.

---

## 11. Summary for dispatcher

- **Add after canary Layer 1 lands** (~0.5 dev-day follow-on).
- **Stub files named in §2.** Exact YAML in §4.
- **Six-step success gate** in §3. All must pass; any fail = alarm.
- **Non-overlapping with existing monitors.** Closes the highest-priority still-unmonitored surface.
- **Deferred polish:** auto-open-issue, Slack webhook, Windows matrix, `uv` migration — queue as follow-ups when team bandwidth allows.
