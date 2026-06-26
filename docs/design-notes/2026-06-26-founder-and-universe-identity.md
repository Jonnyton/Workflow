# Founder & Universe Identity — who a universe belongs to, and which persona a chatbot wears

- **Status:** Proposed (design). Host-ratified principles 2026-06-25/26 (surfaced during the blank-slate persona live ui-test). Not yet sliced.
- **Author:** Claude Code session (host design dialogue 2026-06-26).
- **Upstream of:** the blank-slate universe brain (`2026-06-25-blank-slate-universe-brain.md`). The persona can only "align with its founder" once a founder identity exists — this note builds that.
- **Touches:** `workflow/auth/*` (provider, middleware, wellknown), `workflow/api/engine_helpers.py` (`_current_actor`), `workflow/api/universe.py` (creation, routing), `workflow/api/status.py` (persona/founder surface), `deploy/cloudflare-worker/worker.js`.

---

## 1. The problem (from the live ui-test, 2026-06-25/26)

The blank-slate persona shipped and reads honestly curious — but `get_status`
returns `account_user: "anonymous"`, even for the host's authenticated claude.ai
session. The persona's entire premise is *"align with my founder"*; with no
founder identity flowing, there is **no founder to align with**. This is upstream
of the persona work.

## 2. What's actually true (verified in code, 2026-06-26)

- **The OAuth Bearer reaches the daemon.** `deploy/cloudflare-worker/worker.js`
  preserves the `Authorization` header to the tunnel origin (it only strips
  hop-by-hop headers, and injects CF-Access *service-token* headers to authenticate
  the Worker itself). So the user's claude.ai OAuth token rides straight through.
- **The daemon is the OAuth server.** `workflow/auth/wellknown.py` + `provider.py`
  issue the tokens during connector install, so a received Bearer is one the daemon
  can validate.
- **Gap 1 — auth gating is OFF.** `UNIVERSE_SERVER_AUTH` is unset in `deploy/`
  (default `false`). `auth_middleware` resolves the token only when the provider
  is in gated mode; otherwise `_current_actor()` falls through to env
  `UNIVERSE_SERVER_USER` = `"anonymous"`. The token arrives and is ignored.
- **Gap 2 — no universe→founder binding exists.** `universe.py` has no `founder` /
  `owner_id` / `claim`. The only `created_by=_current_actor()` is on daemons/goals
  (and anonymous anyway). A universe never records whose it is.

So: the identity plumbing is 90% there; the daemon just doesn't *use* it, and the
universe doesn't *store* a founder.

## 3. The model (host-ratified)

### 3.1 Capability model — anonymous reads, OAuth writes
- **Anonymous = read-only.** Can browse/read the commons; cannot create or write.
- **OAuth = write/create powers**, including creating a universe.
- This is a **permission model, not a hard gate** (don't reject anonymous outright).
  The substrate is partway there: `Identity.can(capability)` + `require_action_scope`
  exist. Write actions (`create_universe`, `write_graph`, `set_premise`,
  `add_canon`, daemon control, …) require the OAuth capability; reads stay open.
- The exact read/write line is refined as we go; the principle is fixed.

### 3.2 Founder by construction — no claim flow
- **Creating a universe requires OAuth.** Therefore **every universe has a founder
  the instant it exists** — the founder is simply *the creator's OAuth user_id,
  recorded at creation*. No separate binding step, no claim action.
- A universe exists only because (a) a user's **first OAuth connect auto-created
  their main universe**, or (b) they **used their OAuth to create another**.
- **Long-term there are no anonymous universes.** The "who is my founder" problem
  doesn't get solved — it's structurally impossible to have a founderless universe.

### 3.3 Universe ID = immutable serial; identity is learned
- **`universe_id` = an opaque creation SERIAL, immutable forever** — never a
  descriptive slug. `"patch-loop-live"` is a legacy hangover. The id is just a
  stable address; it carries no meaning.
- Everything meaningful — **persona name, purpose, body** — is **learned in the
  self-model** and mutable; it changes as the universe gets to know itself.
- **Serial format (open fork):** short monotonic serial (`u-000142`, human-skimmable)
  vs. opaque UUID (no count leak). Lean monotonic unless hiding the universe count
  matters.

### 3.4 Per-request persona routing (the multi-user crux)
At scale (say 50 universes, each with its own OAuth founder), **which persona a
chatbot wears is resolved per request** from `(identity, prompt)` — NOT a global
single active-universe marker. Resolution order:

1. **Prompt names a specific universe/persona** → that universe's persona. Anyone
   may *read* it (read-only for non-founders / anonymous); only its founder may
   *write* to it.
2. **Otherwise (unspecified / ambiguous)** → the caller's **main universe**:
   - **Recognized OAuth** → their main universe's persona by default.
   - **New OAuth** (never seen) → **auto-create** their main universe (serial id,
     founder bound, blank self-model) and route to it.
   - **Anonymous** → has no main universe; routes purely by prompt (read-only). With
     no target and no main universe, the connector asks them to name one / offers the
     public commons rather than guessing.
3. **Any confusion over which persona is meant → default to the caller's main
   universe** (for OAuth).

This replaces the current single-operator model (`.active_universe` marker /
`UNIVERSE_SERVER_DEFAULT_UNIVERSE`) with per-identity main-universe + per-prompt
routing.

## 4. What changes in code (audit, not yet built)

| Area | Today | Direction |
|---|---|---|
| `workflow/auth` | gating off; provider resolves nothing | Gated capability mode: resolve OAuth token → real `user_id`; anonymous = read caps only |
| Write actions (`universe.py`, `write_graph`, …) | run as anonymous | `require_action_scope`/`Identity.can` gate: OAuth-only |
| Universe creation | caller-supplied descriptive `universe_id`; no founder | Assign serial id; record `founder = current OAuth user_id`; seed blank self-model; require OAuth |
| Active universe | global `.active_universe` / default env | Per-request resolution from (identity → main universe, prompt → override) |
| `get_status` | `account_user` from env; no founder | Surface resolved `universe_id` (serial), `founder`, and `is_founder` (caller==founder) so the persona aligns |
| Legacy anon universes | `patch-loop-live`, test ones | NOT user-claimable; host deletes / substrate-claims / controlled fake-OAuth for testing |

## 5. Rollout caution

- **Turning gating on is production-impacting.** It changes who can write on the
  live MCP. Stage it: ship the capability model behind verification, confirm the
  claude.ai OAuth token resolves to a stable `user_id` end-to-end (the one piece
  still to prove live — provider.resolve_token against a real claude.ai token),
  then enable. Don't flip `UNIVERSE_SERVER_AUTH` blind.
- **Per-request routing is a real shift** from the single-active-universe daemon —
  it's the biggest piece and should land incrementally (resolve identity first;
  main-universe default next; prompt-override last).

## 6. Open questions

1. Serial-ID format (§3.3) — monotonic vs UUID.
2. The exact read/write capability split (which reads stay open to anonymous;
   which writes are OAuth-only) — refined as we go.
3. Live proof that a claude.ai OAuth Bearer resolves to a stable `user_id` via
   `provider.resolve_token` (the daemon is the issuer, so expected — but unproven live).
4. Multi-universe-per-daemon: does one daemon serve many universes' personas
   concurrently (per-request routing implies yes), and how does that interact with
   the current single-universe-at-startup loop?

## 7. Proposed slices (draft)

1. **Founder at creation (additive).** `create_universe` (OAuth-gated) assigns a
   **serial id** + records `founder = OAuth user_id`. New universes only.
2. **Surface founder.** `get_status` exposes resolved `universe_id`, `founder`,
   `is_founder`. Persona can say "you're my founder" / "you're a visitor".
3. **Capability gate on writes.** Anonymous → read-only; OAuth → write. Behind a
   flag; verify claude.ai token resolution live first.
4. **Per-request routing.** Identity → main universe default; then prompt-override.
   Retire the global active-universe singleton.
5. **Legacy cleanup.** Delete / substrate-claim / fake-OAuth the pre-OAuth universes.

Each slice: TDD, opposite-provider (Codex) review, live `ui-test` via the CDP route.
