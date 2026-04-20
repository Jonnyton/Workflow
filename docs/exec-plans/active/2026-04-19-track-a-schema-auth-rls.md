# Track A — Schema + Auth + RLS Execution Spec (Daemon-Economy First-Draft)

**Date:** 2026-04-19
**Author:** navigator
**Status:** Execution spec — references existing pre-draft + prototype migrations rather than redrafting from scratch.
**Foundation classification:** **FOUNDATION.** Per CLAUDE_LEAD_OPS.md operationalization list (storage schema + auth = foundation). Build to end-state in this commit; no phased schema rollout.
**Scope:** Daemon-economy first-draft slice of Track A — what tables ship, what auth flow ships, what RLS boundaries enforce. Out of scope for first-draft: Track A pieces that don't gate the §3 done-line transaction (per `docs/exec-plans/active/2026-04-19-daemon-economy-first-draft.md`).
**Effort:** ~2 dev-days, single contributor (per first-draft estimate). Most of the heavy lifting is already in `docs/specs/2026-04-18-full-platform-schema-sketch.md` + `prototype/full-platform-v0/migrations/`.

---

## 1. Pre-existing reference material

Three artifacts already cover most of Track A's design surface:

| Path | What's there | Usage |
|---|---|---|
| `docs/specs/2026-04-18-full-platform-schema-sketch.md` | Full SQL sketch — `users`, `nodes`, `host_pool`, `requests`, `bids`, `ledger`, `domains`, RLS policies, OPEN-flag gaps. | **Direct lift.** This spec carries the full schema; first-draft uses a subset. |
| `prototype/full-platform-v0/migrations/001_core_tables.sql` | Postgres-DDL for core tables. | **Direct lift.** First-draft inherits, possibly with subset commentary. |
| `prototype/full-platform-v0/migrations/002_rls.sql` | RLS policies. | **Direct lift.** First-draft uses subset matching the in-scope tables. |
| `prototype/full-platform-v0/migrations/003_discover_nodes.sql` | `discover_nodes` view + ranking. | **Partial.** First-draft uses minimal slice (per Track H minimal scope in daemon-economy first-draft §2). |

**Implication:** This exec-spec doesn't redraft schema. It maps the existing sketch + prototype migrations to the daemon-economy first-draft scope, calls out which subset is in vs out, and surfaces any gaps.

---

## 2. Tables in scope for daemon-economy first-draft

Per the §2.0a Foundation/Feature classification in `2026-04-19-daemon-economy-first-draft.md`, every table here is **foundation**. Schema shape locks at this commit; future iteration is additive (alter table + add column), never re-shape.

| Table | Source | First-draft role |
|---|---|---|
| **`public.users`** | sketch §1.1 | Auth identity projection. Required for every other table's FK + RLS `auth.uid()` check. |
| **`public.host_pool`** | full-platform note §5.4 + sketch (verify) | Daemon registrations: heartbeat, declared capabilities, visibility (self/network/paid), price floor. Foundation primitive #1 in daemon-economy §2.0a. |
| **`public.capabilities`** | sketch (verify) | `(node_type, llm_model)` registry. Foundation primitive #4 (capability-resolution protocol). Referenced by `host_pool.capability_id` + `requests.capability_id`. |
| **`public.requests`** | sketch §1.x (paid-market) | User-posted work requests. State machine: `pending` → `bidding` → `claimed` → `running` → `completed` / `failed` / `flagged`. Foundation primitive #2 (bid-routing core). |
| **`public.bids`** | sketch §1.x | Daemon bids on requests. Claim semantics via `SELECT FOR UPDATE SKIP LOCKED`. Foundation primitive #2. |
| **`public.ledger`** | sketch §1.7 | Settlement records — write-once, immutable. `settlement_mode enum('immediate','batched')` per §11 Q4-follow. Foundation primitive #3. |
| **`public.settlements`** | full-platform note §18.6 | Per-bid settlement events tied to ledger. v1 schema must outlive token-launch migration byte-for-byte. Foundation primitive #3. |
| **`public.nodes`** | sketch §1.2 | Required so requesters can name a node to bid on. **First-draft uses minimal slice:** `node_id`, `slug`, `name`, `domain`, `status`, `owner_user_id`, `node_type`. Defer `concept`/`instance_ref` jsonb dual-layer to post-first-draft (per Track L OUT). |
| **`public.flags`** *(NEW for first-draft)* | This spec §3.4 | Moderation entry point. `(target_id, target_kind, flagger_id, reason, state)`. Per `2026-04-19-daemon-economy-first-draft.md` §2.1 — minimal hook-point only; full moderation surface ships post-first-draft. Foundation primitive #6. |

**Total: 9 tables** (8 from existing sketch + 1 new `flags`).

---

## 3. Tables NOT in first-draft

Per daemon-economy §2 OUT classifications:

| Sketch table | Defer because | Re-introduce when |
|---|---|---|
| `public.domains` | Permissionless domains (Q14-host RESOLVED) — full domain registry is feature, not first-draft critical-path. | Track K (convergent commons) ships, OR when first user-sim mission needs cross-domain discovery. |
| `public.artifact_field_visibility` | Per-piece privacy is Track L (OUT for first-draft). | Track L ships post-first-draft. |
| `public.comments` | Track F (realtime presence) is OUT. | Track F ships post-first-draft. |
| `public.uploads` | S3-compatible storage is Track A scope but doesn't gate the done-line transaction. | When canon-upload UX surfaces in user-sim missions. |
| `public.branches` | Track K convergent commons. | Track K ships. |
| `public.goals` | Goal as first-class above branch — full goals primitive is post-first-draft. | When tier-1 user wants to organize requests around a goal. |
| `public.gate_claims` | Real-world outcome gates per §24. | Post-first-draft. |
| `public.training_data_excluded_role` | Training-exclusion enforcement (§17 Q14 separate-role) — privacy track. | Track L ships. |

**Discipline:** the existing sketch enumerates many tables; first-draft ships only the 9 above. **DO NOT pre-create the others** — defer schema until the work that consumes them ships, per Foundation/Feature rule (foundation locks shape; deferring tables avoids locking shapes prematurely).

---

## 4. Auth flow shape

### 4.1 GitHub OAuth at the edge (per §11 Q4 ratified)

- **Supabase Auth + GitHub OAuth provider** — single identity primitive for all four migration paths (T1↔T2↔T3, per §2.5 of full-platform note).
- **OAuth 2.1 + PKCE** at the MCP edge for tier-1 chatbot users connecting via Claude.ai (`api.tinyassets.io/mcp`).
- **`auth.users` is Supabase-managed**, `public.users` is the thin projection (sketch §1.1).
- **Session tokens** scoped per user; daemon-side tray reuses the same Supabase session (no separate auth flow per §2.5 T1→T2 path).

### 4.2 Capability-grant model (deferred from first-draft)

The full sketch carries `capability_grants` for fine-grained per-action permissions. **Defer for first-draft.** First-draft has only two capability grants in practice:
- "User can place paid requests" — implicit for any authenticated user.
- "User can host a daemon" — implicit when tray installs + binds.

When abuse appears OR when richer permission-shaping is needed, re-introduce `capability_grants` table from the sketch. Per Foundation/Feature: grants table shape would be foundation, but the *mechanism* of grants is currently un-needed — defer the table.

---

## 5. RLS boundaries

Per `prototype/full-platform-v0/migrations/002_rls.sql`. First-draft RLS subset:

| Table | Read policy | Write policy |
|---|---|---|
| `users` | Self-readable + minimal-public-projection (display_name, github_handle for attribution) | Self-only writes |
| `host_pool` | Public-readable for `visibility=paid` rows; self-only for `self`/`network` | `owner_user_id = auth.uid()` |
| `capabilities` | Public-readable (registry of available capability keys) | Admin-only writes (host inserts at first-draft) |
| `requests` | Self-readable (own requests) + capability-matched daemons readable for `visibility=paid` | `requester_user_id = auth.uid()` |
| `bids` | Requester-readable (bids on own requests) + bidder-readable (own bids) | `bidder_user_id = auth.uid()` |
| `ledger` | Self-readable (own ledger entries) | Service-role-only writes (control plane writes; clients can't write) |
| `settlements` | Both parties readable (requester + bidder) | Service-role-only (immutable from client side) |
| `nodes` | Public-readable for `status='published'`; self-only for `draft`/`deprecated` | `owner_user_id = auth.uid()` |
| `flags` | Service-role + flagger-self readable; flagged-target-owner readable for own resources | `flagger_id = auth.uid()` write |

**Foundation invariant:** RLS policies enforce visibility at the DB layer, not at the application layer. Per §11 Q14 ratified (a) separate-role enforcement principle — silent-leak failure mode is unacceptable. Even though Q14 was specifically about training-data exclusion, the underlying principle (DB-layer enforcement, not application-layer trust) applies here too.

**Role scope — PUBLIC vs `authenticated`:** first-draft RLS policies use the PUBLIC role (matching `prototype/full-platform-v0/migrations/002_rls.sql`). The sketch in `docs/specs/2026-04-18-full-platform-schema-sketch.md` §2 targets `authenticated` (Supabase's role name for JWT-authenticated callers). Both are correct depending on deploy target — PUBLIC covers the v0 test harness which sets `app.current_user_id` via `SET LOCAL`; `authenticated` covers Supabase production where JWT claims populate `auth.uid()` at the gateway. At Supabase deploy time, the migration is patched to `TO authenticated` via a one-line sed pass; no schema change. Resolves verifier ambiguity flag.

---

## 6. Migration ordering for the commit

Per the existing prototype migrations + new additions:

1. **`001_core_tables.sql` (existing)** — `users`, `host_pool`, `capabilities`, `requests`, `bids`, `ledger`, `settlements`, `nodes`. Lift from prototype, prune to first-draft tables only.
2. **`002_flags.sql` (NEW)** — `flags` table per §3.4 + minimal moderation state-gate (control-plane reads `state='flagged'` and pauses routing).
3. **`003_rls.sql` (existing, subset)** — RLS policies for the 9 in-scope tables only.
4. **`004_indexes.sql` (lift from existing or NEW)** — indexes on hot paths: `requests(state, capability_id)`, `bids(request_id, state)`, `host_pool(visibility, capability_id)`, `ledger(user_id, ts)`.
5. **`005_seed.sql` (NEW)** — minimal seed: insert known capability rows for the in-tree node-type taxonomy (per `docs/catalogs/node-type-taxonomy.md` if present, otherwise seed empty + populate from first daemon registration).

**Discipline:** ALL migrations are forward-only + idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`). No rollback path expected — first-draft is a fresh deploy, not a migration from existing prod.

---

## 7. Gaps + OPEN-flag resolutions

The pre-draft sketch carries OPEN-flag gaps. First-draft resolutions:

| Gap | First-draft resolution |
|---|---|
| **OPEN: settlement-mode threshold value** (sketch §1.7) | Per §11 Q4-follow RESOLVED: `$1` equivalent. Hardcode in first-draft as constant; make config-driven post-first-draft. |
| **OPEN: capability-key shape — string vs composite** | Composite `(node_type, llm_model)` per §5.4 of full-platform note. Compound primary key on `capabilities` table. |
| **OPEN: how to seed first capability rows** | Empty seed; first daemon registration auto-inserts capability rows it declares. Capability registry grows organically. |
| **OPEN: bid claim deadline for unfulfilled bids** | First-draft default: 1h timeout, automatic refund. Per Q-econ-3 (deferred to v5 digest); this default is foundation. |
| **OPEN: `state='flagged'` propagation** | Control plane reads `requests.state='flagged'` and `bids.state='flagged'` at the broadcast layer; flagged rows excluded from broadcast. Manual host-admin SQL resolves to non-flagged states. |

---

## 8. Test coverage

First-draft Track A ships with these test invariants (use Supabase test fixture or local Postgres):

1. **Schema compiles cleanly + RLS policies load.** Smoke test on fresh DB.
2. **RLS enforcement at DB layer.** Each in-scope table: prove that a non-owner role cannot SELECT/INSERT/UPDATE/DELETE rows owned by another user.
3. **`SELECT FOR UPDATE SKIP LOCKED` claim semantics.** Two concurrent claims on same request: exactly-one wins.
4. **Settlement immutability.** Second `INSERT` to `settlements` with same `bid_id` raises Postgres `UniqueViolation` (enforced via `UNIQUE(bid_id)` — one settlement per bid; stricter than the original `(bid_id, daemon_id)` shape because a single bid is awarded to exactly one daemon, so `daemon_id` is redundant in the uniqueness key).
5. **Flagged-state routing pause.** Insert flagged request; verify control-plane broadcast skips it.
6. **Auth flow end-to-end.** Sign in via GitHub OAuth → row appears in `public.users` → `auth.uid()` returns the right ID in subsequent queries.

These are the load-bearing tests. Additional coverage (volumetric, scale) is Track J pre-launch (per §11 Q10 / v3 Q2 ratified).

---

## 9. Sequencing within first-draft Wave 1

Per daemon-economy first-draft §2.0a Wave 1 = Foundation. Track A ships **first** within Wave 1 because all other Wave 1 work depends on the schema. Specifically:

- Track A (this spec) → ships standalone.
- Track D (daemon host changes) requires `host_pool` + `capabilities` from Track A.
- Track E (paid-market flow) requires `requests` + `bids` + `ledger` from Track A.
- Track M (testnet ledger primitive) requires `ledger` + `settlements` from Track A.
- Capability-resolution protocol (foundation) requires `capabilities` from Track A.
- Moderation hook-point requires `flags` from Track A.

**~2 dev-days for Track A alone.** After Track A lands, Wave 1 remainder (Tracks D + E + M + capability-resolution + moderation-hook) can parallelize across 2 devs at ~3-4 calendar days.

---

## 10. What this spec does NOT decide

- **Specific Postgres RLS-policy text.** Lift from `prototype/full-platform-v0/migrations/002_rls.sql` for the in-scope tables; dev iterates if RLS pass surfaces issues during test gate.
- **Exact pgvector + index strategy for `nodes`.** First-draft uses minimal node columns + standard btree indexes; vector indexes (for semantic search) are Track H expansion post-first-draft.
- **Supabase-vs-self-hosted decision.** Per §11 Q2 ratified: Supabase. Configuration lives in `prototype/full-platform-v0/config.py` already.
- **Connection pooling + service-role separation.** Standard Supabase pattern; not a foundation decision.

---

## 11. Summary for dispatcher

- **Effort:** ~2 dev-days, single contributor.
- **Source:** lift from `docs/specs/2026-04-18-full-platform-schema-sketch.md` + `prototype/full-platform-v0/migrations/`.
- **In-scope: 9 tables** (8 from existing sketch + 1 new `flags`).
- **Out-of-scope: 8 tables from sketch** explicitly deferred per first-draft scope.
- **Auth: GitHub OAuth via Supabase Auth.** Capability-grants table deferred.
- **RLS: 9 tables, DB-layer enforcement.**
- **5 OPEN-flag gaps resolved.**
- **6 load-bearing test invariants** for Track A's gate.
- **Ships first within Wave 1.** Tracks D + E + M + capability-resolution + moderation-hook all depend on it.
- **Foundation classification:** schema shape locks at this commit; future iteration is additive only.

When dev claims Track A (post-R7 storage split), this spec is the entry point. Existing sketch + prototype migrations carry most of the implementation.
