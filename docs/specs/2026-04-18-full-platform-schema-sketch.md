---
status: active
---

# Full-Platform Schema + RLS + `discover_nodes` — Pre-Draft

**Date:** 2026-04-18
**Author:** dev (task #24 pre-draft; unblocks track A/H when host answers §11 Q1 yes)
**Status:** Pre-draft spec. No code yet. Intended for direct execution on track A the moment Q1 is approved.
**Source of truth:** `docs/design-notes/2026-04-18-full-platform-architecture.md` §2 / §5 / §14 / §15 / §16 / §17.
**Assumes:** Postgres 15+ via Supabase. pgvector extension. Supabase Auth schema (`auth.users`, `auth.uid()`). Supabase Realtime for push. Supabase Storage for instance blobs.

This doc is a working SQL sketch — another dev + verifier should be able to open `track A` and start coding without design re-research. Ambiguities carry `OPEN:` flags; do not invent answers.

---

## 1. Core tables

All writable rows carry `version bigint NOT NULL DEFAULT 1` for §14.3 optimistic CAS. All timestamps `timestamptz` UTC. All IDs `uuid` unless noted.

### 1.1 `users` (thin projection over `auth.users`)

```sql
CREATE TABLE public.users (
  user_id           uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  github_handle     text UNIQUE,              -- null if native-account signup
  display_name      text NOT NULL,
  account_age_days  int GENERATED ALWAYS AS (
    EXTRACT(DAY FROM (now() - created_at))::int
  ) STORED,                                   -- §14.7 backstop gate
  interaction_count int NOT NULL DEFAULT 0,   -- trigger-maintained on writes
  trust_tier        text NOT NULL DEFAULT 't1' CHECK (trust_tier IN ('t1','t2','t3')),
  version           bigint NOT NULL DEFAULT 1,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
```

**Scale primitive:** `account_age_days` + `interaction_count` feed §14.7 upvote/request gates. Stored generated column for `account_age_days` to avoid per-read compute.

### 1.2 `nodes` (dual-layer: concept public-biased, instance owner-only)

```sql
CREATE TABLE public.nodes (
  node_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                 text NOT NULL,
  name                 text NOT NULL,
  domain               text NOT NULL,
  status               text NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft','published','deprecated','superseded')),
  owner_user_id        uuid NOT NULL REFERENCES public.users(user_id),

  -- §17 dual-layer
  concept              jsonb NOT NULL,        -- public-biased; enforced by RLS + field-visibility table
  instance_ref         text NULL,             -- pointer to private Supabase Storage blob OR host-local path
  concept_visibility   text NOT NULL DEFAULT 'public'
                         CHECK (concept_visibility IN ('public','private','network')),

  -- §15 discovery primitives
  input_schema         jsonb,
  output_schema        jsonb,
  structural_hash      text NOT NULL,         -- canonicalized graph-shape hash; btree-indexed
  embedding            vector(1536),          -- pgvector; intent + description + tags concat
  tags                 text[] NOT NULL DEFAULT '{}',
  parents              uuid[] NOT NULL DEFAULT '{}',   -- §15.3 remix-from-N lineage

  -- §15.2 first-class quality/activity columns (trigger-maintained)
  usage_count          int NOT NULL DEFAULT 0,
  success_count        int NOT NULL DEFAULT 0,
  fail_count           int NOT NULL DEFAULT 0,
  upvote_count         int NOT NULL DEFAULT 0,
  fork_count           int NOT NULL DEFAULT 0,
  remix_count          int NOT NULL DEFAULT 0,
  editing_now_count    int NOT NULL DEFAULT 0,   -- Presence aggregator; §14.5
  last_edited_at       timestamptz NOT NULL DEFAULT now(),
  deprecated           bool NOT NULL DEFAULT false,
  superseded_by        uuid NULL REFERENCES public.nodes(node_id),
  improvement_cycle_id uuid NULL,              -- OPEN: table definition deferred — belongs with §15.3 converge proposals

  -- §17 training-data exclusion
  training_excluded    bool NOT NULL DEFAULT false,  -- owner-private concept fields default true; see §17.4

  version              bigint NOT NULL DEFAULT 1,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),

  UNIQUE (owner_user_id, slug)
);

CREATE INDEX nodes_embedding_hnsw ON public.nodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX nodes_tags_gin       ON public.nodes USING gin  (tags);
CREATE INDEX nodes_parents_gin    ON public.nodes USING gin  (parents);
CREATE INDEX nodes_struct_btree   ON public.nodes (structural_hash);
CREATE INDEX nodes_domain_status  ON public.nodes (domain, status);
CREATE INDEX nodes_owner          ON public.nodes (owner_user_id);
```

**Why `concept` + `instance_ref` as columns, not separate tables:** read-heavy bias (§15). Every discovery hit loads concept; instance is a pointer followed only for owner callers. Joining a separate instance table on every concept read would be needless work for the 99%+ case where the caller isn't the owner.

**Scale primitives:** HNSW on embedding (§15.2 O(log N) cosine search); GIN on tags + parents; first-class quality columns avoid side-table joins in the hot discovery path.

### 1.3 `artifact_field_visibility` (per-field visibility decisions, §17.2)

```sql
CREATE TABLE public.artifact_field_visibility (
  artifact_id       uuid NOT NULL,
  artifact_kind     text NOT NULL CHECK (artifact_kind IN ('node','goal','branch','soul','comment')),
  field_path        text NOT NULL,                -- JSON-pointer into the artifact's concept blob
  visibility        text NOT NULL CHECK (visibility IN ('public','private','network')),
  reason            text,                          -- chatbot's rationale
  decided_at        timestamptz NOT NULL DEFAULT now(),
  decided_by        text NOT NULL CHECK (decided_by IN ('chatbot','user','owner')),
  training_excluded bool NOT NULL DEFAULT false,   -- mirrors visibility='private' by default
  PRIMARY KEY (artifact_id, artifact_kind, field_path)
);

CREATE INDEX afv_kind_id ON public.artifact_field_visibility (artifact_kind, artifact_id);
```

**Scale primitive:** composite PK is (artifact_id, artifact_kind, field_path) — single point-lookup per field at read time. Discovery view joins this to mask private fields server-side (§17.4 guarantee 1).

**OPEN Q1:** when `visibility='network'` on a field, what's the allowlist mechanism? Per-node ACL table, or per-user "trusted peers" list? Defer until §5.1 network-visibility allowlist is spec'd more concretely.

### 1.4 `node_activity` (append-only event log for trigger-maintained counters)

```sql
CREATE TABLE public.node_activity (
  activity_id    bigserial PRIMARY KEY,
  node_id        uuid NOT NULL REFERENCES public.nodes(node_id) ON DELETE CASCADE,
  actor_user_id  uuid NOT NULL REFERENCES public.users(user_id),
  event_kind     text NOT NULL CHECK (event_kind IN (
                   'created','edited','forked','remixed','upvoted','downvoted',
                   'used_in_run','run_succeeded','run_failed','deprecated','converged')),
  payload        jsonb,
  at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX node_activity_node_at ON public.node_activity (node_id, at DESC);
CREATE INDEX node_activity_actor   ON public.node_activity (actor_user_id, at DESC);
```

**Scale primitive:** append-only (no updates). Counter maintenance on `nodes.*_count` happens via AFTER-INSERT triggers; the activity log is the audit trail.

### 1.5 `host_pool` (§14.5 — durable only, NO `last_heartbeat` column)

```sql
CREATE TABLE public.host_pool (
  host_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id    uuid NOT NULL REFERENCES public.users(user_id),
  provider         text NOT NULL CHECK (provider IN ('local','claude','codex','gemini')),
  -- OPEN Q2: provider enum above vs open-ended text for future providers. Deferred; likely text with app-side CHECK.
  capability_id    text NOT NULL,               -- (node_type, llm_model) composite key, see §1.5b
  visibility       text NOT NULL DEFAULT 'self'
                     CHECK (visibility IN ('self','network','paid')),
  price_floor      numeric(18,6) NULL,           -- null for self/network
  max_concurrent   int NOT NULL DEFAULT 1,
  always_active    bool NOT NULL DEFAULT false,  -- §5.2 cascade toggle
  version          bigint NOT NULL DEFAULT 1,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX host_pool_owner        ON public.host_pool (owner_user_id);
CREATE INDEX host_pool_cap_vis      ON public.host_pool (capability_id, visibility);
```

**Explicitly omitted:** `last_heartbeat timestamptz`. Per §14.5, online status is derived from Supabase Presence (server-side, 90s TTL) at dispatch time — control plane joins `host_pool` against Presence rather than writing a heartbeat column every 60s per host. Avoids ~167 writes/sec at 10k hosts.

### 1.5b `capabilities` (reference table for `capability_id`)

```sql
CREATE TABLE public.capabilities (
  capability_id text PRIMARY KEY,                 -- e.g. 'goal_planner×claude-4-opus'
  node_type     text NOT NULL,
  llm_model     text NOT NULL,
  description   text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (node_type, llm_model)
);
```

### 1.6 `request_inbox` (§14.1 — claim-RPC, not poll-all)

```sql
CREATE TABLE public.request_inbox (
  request_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  requester_user_id  uuid NOT NULL REFERENCES public.users(user_id),
  capability_id      text NOT NULL REFERENCES public.capabilities(capability_id),
  visibility         text NOT NULL CHECK (visibility IN ('self','network','paid','public')),
  bid_price          numeric(18,6) NULL,           -- null for non-paid
  deadline           timestamptz NULL,
  state              text NOT NULL DEFAULT 'pending'
                       CHECK (state IN ('pending','claimed','running','completed','failed','cancelled')),
  claimed_by_host    uuid NULL REFERENCES public.host_pool(host_id),
  claimed_at         timestamptz NULL,
  inputs             jsonb NOT NULL,
  inputs_visibility  text NOT NULL DEFAULT 'owner-only'
                       CHECK (inputs_visibility IN ('owner-only','public')),  -- §17: private instance data biases owner-only
  -- §5.2 step-3 signal columns
  upvote_count       int NOT NULL DEFAULT 0,
  dependency_refs    uuid[] NOT NULL DEFAULT '{}',
  improvement_cycle_id uuid NULL,
  version            bigint NOT NULL DEFAULT 1,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX req_state_cap       ON public.request_inbox (state, capability_id)
  WHERE state = 'pending';    -- partial index — hot path is pending-only
CREATE INDEX req_requester       ON public.request_inbox (requester_user_id);
CREATE INDEX req_claimed_by_host ON public.request_inbox (claimed_by_host);
```

**Claim RPC (§14.1 — see §3 below):** daemons do NOT `SELECT FOR UPDATE SKIP LOCKED` on every cascade cycle. They subscribe to per-capability Realtime channels; when a matching request posts, only interested daemons call `claim_request(request_id)`, which internally does the narrow row-lock.

### 1.7 `ledger` (economic truth)

```sql
CREATE TABLE public.ledger (
  entry_id         bigserial PRIMARY KEY,
  user_id          uuid NOT NULL REFERENCES public.users(user_id),
  entry_kind       text NOT NULL CHECK (entry_kind IN (
                     'reserve','release','debit','credit','refund','bonus','adjustment')),
  amount           numeric(18,6) NOT NULL,         -- signed: positive = credit, negative = debit
  currency         text NOT NULL DEFAULT 'workflow_credit',
  related_request  uuid NULL REFERENCES public.request_inbox(request_id),
  reason           text,
  at               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ledger_user_at    ON public.ledger (user_id, at DESC);
CREATE INDEX ledger_by_request ON public.ledger (related_request) WHERE related_request IS NOT NULL;
```

**Scale primitive:** append-only. Balance derived via `SUM(amount)` or a materialized view if read-hot.

### 1.8 `provider_plan_tiers` (§5.3 — tray payment-tier estimate lookup)

```sql
CREATE TABLE public.provider_plan_tiers (
  provider                     text NOT NULL,
  plan_name                    text NOT NULL,
  monthly_cost_usd             numeric(10,2) NOT NULL,
  approx_requests_per_min_cap  int NOT NULL,
  notes                        text,
  PRIMARY KEY (provider, plan_name)
);
```

Seeded at deploy; updatable via admin UI without tray-binary redeploy.

### 1.9 `public_demand_ranked` (materialized view, §14.4)

```sql
CREATE MATERIALIZED VIEW public.public_demand_ranked AS
SELECT
  r.request_id,
  r.capability_id,
  r.visibility,
  r.bid_price,
  r.upvote_count,
  array_length(r.dependency_refs, 1) AS dependency_count,
  EXTRACT(EPOCH FROM (now() - r.created_at))::int AS age_seconds,
  r.improvement_cycle_id,
  -- default composite score; daemons may override (§5.2 latitude)
  (
    COALESCE(r.bid_price, 0) * 1.0
    + r.upvote_count * 0.5
    + COALESCE(array_length(r.dependency_refs,1), 0) * 0.3
    + LEAST(EXTRACT(EPOCH FROM (now() - r.created_at)) / 3600.0, 24) * 0.2  -- staleness cap at 24h
  ) AS default_score
FROM public.request_inbox r
WHERE r.state = 'pending'
  AND r.visibility IN ('paid','public');

CREATE UNIQUE INDEX pdr_rid ON public.public_demand_ranked (request_id);
CREATE INDEX pdr_cap_score ON public.public_demand_ranked (capability_id, default_score DESC);
-- Refresh via pg_cron every 30-60s:
-- SELECT cron.schedule('public_demand_refresh', '30 seconds',
--   'REFRESH MATERIALIZED VIEW CONCURRENTLY public.public_demand_ranked');
```

**Shared with §15:** `nodes_hot` (precomputed top-500 by composite score per domain, refreshed 60s) uses the same refresh mechanism but different sources. Spec deferred to track K — `public_demand_ranked` is the track-A deliverable.

---

## 2. RLS policies (§17.4 enforcement = structural)

RLS is enabled on every user-data table. The tuple `(auth.uid(), owner_user_id, visibility)` is the decision surface.

### 2.1 `nodes`

```sql
ALTER TABLE public.nodes ENABLE ROW LEVEL SECURITY;

-- SELECT: owners see everything; non-owners see public-concept-visibility rows only
CREATE POLICY nodes_select_owner ON public.nodes
  FOR SELECT TO authenticated
  USING (auth.uid() = owner_user_id);

CREATE POLICY nodes_select_public ON public.nodes
  FOR SELECT TO authenticated
  USING (concept_visibility = 'public');

-- OPEN Q3: 'network' visibility rows — needs allowlist table lookup.
-- Placeholder policy (ties into unresolved §1.3 OPEN Q1):
CREATE POLICY nodes_select_network ON public.nodes
  FOR SELECT TO authenticated
  USING (
    concept_visibility = 'network'
    AND EXISTS (  -- TODO: replace with real network-allowlist table
      SELECT 1 FROM public.users u
      WHERE u.user_id = auth.uid()
      -- AND user is in nodes.owner's network allowlist
    )
  );

-- INSERT: owner must match caller
CREATE POLICY nodes_insert_owner ON public.nodes
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = owner_user_id);

-- UPDATE: owner-only
CREATE POLICY nodes_update_owner ON public.nodes
  FOR UPDATE TO authenticated
  USING (auth.uid() = owner_user_id);

-- DELETE: owner-only (soft-delete via status='deprecated' preferred)
CREATE POLICY nodes_delete_owner ON public.nodes
  FOR DELETE TO authenticated
  USING (auth.uid() = owner_user_id);
```

**Instance-field stripping (§17.4 guarantee 1):** RLS alone cannot mask individual JSON keys inside `concept`. A discovery VIEW applies field-level masking:

```sql
CREATE VIEW public.nodes_public_concept AS
SELECT
  n.node_id, n.slug, n.name, n.domain, n.status,
  n.owner_user_id,
  -- Strip private fields based on artifact_field_visibility
  public.strip_private_fields(n.concept, n.node_id, 'node') AS concept,
  -- instance_ref NEVER exposed to non-owners — omitted entirely
  NULL::text AS instance_ref,
  n.input_schema, n.output_schema, n.structural_hash,
  n.tags, n.parents,
  n.usage_count, n.success_count, n.fail_count, n.upvote_count,
  n.fork_count, n.remix_count, n.editing_now_count,
  n.last_edited_at, n.deprecated, n.superseded_by,
  n.version, n.created_at, n.updated_at
FROM public.nodes n
WHERE n.concept_visibility IN ('public','network');
```

`strip_private_fields(concept jsonb, artifact_id uuid, artifact_kind text)` is a PL/pgSQL function (see §3.2) that removes every JSON-pointer path marked `visibility='private'` in `artifact_field_visibility`. Called on every discovery read for non-owners.

### 2.2 `artifact_field_visibility`

```sql
ALTER TABLE public.artifact_field_visibility ENABLE ROW LEVEL SECURITY;

-- Only the artifact owner can write/read visibility decisions
CREATE POLICY afv_owner_only ON public.artifact_field_visibility
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.nodes n
      WHERE n.node_id = artifact_id
        AND artifact_kind = 'node'
        AND n.owner_user_id = auth.uid()
    )
    -- OPEN Q4: repeat the EXISTS for each artifact_kind ('goal','branch','soul','comment').
    -- Each target table needs parallel policy. Consider a dispatcher function.
  );
```

### 2.3 `host_pool`

```sql
ALTER TABLE public.host_pool ENABLE ROW LEVEL SECURITY;

-- SELECT: self rows hidden from others; paid rows globally visible; network via allowlist
CREATE POLICY host_self ON public.host_pool FOR SELECT TO authenticated
  USING (visibility = 'self' AND owner_user_id = auth.uid());
CREATE POLICY host_paid ON public.host_pool FOR SELECT TO authenticated
  USING (visibility = 'paid');
CREATE POLICY host_network ON public.host_pool FOR SELECT TO authenticated
  USING (visibility = 'network' /* TODO network-allowlist check */);

-- Owner writes
CREATE POLICY host_owner_write ON public.host_pool
  FOR INSERT TO authenticated WITH CHECK (auth.uid() = owner_user_id);
CREATE POLICY host_owner_update ON public.host_pool
  FOR UPDATE TO authenticated USING (auth.uid() = owner_user_id);
```

### 2.4 `request_inbox`

```sql
ALTER TABLE public.request_inbox ENABLE ROW LEVEL SECURITY;

-- Requesters see their own requests
CREATE POLICY req_own_requests ON public.request_inbox FOR SELECT TO authenticated
  USING (auth.uid() = requester_user_id);

-- Paid/public requests visible to all authenticated (for bid discovery)
CREATE POLICY req_paid_visible ON public.request_inbox FOR SELECT TO authenticated
  USING (visibility IN ('paid','public'));

-- Claimer (via claim_request RPC) sees claimed requests
CREATE POLICY req_claimer ON public.request_inbox FOR SELECT TO authenticated
  USING (
    claimed_by_host IN (SELECT host_id FROM public.host_pool WHERE owner_user_id = auth.uid())
  );

-- Requester inserts
CREATE POLICY req_insert ON public.request_inbox FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = requester_user_id);

-- Updates restricted — the claim/complete state transitions go through RPCs (§3), not direct UPDATE
-- No direct UPDATE policy for authenticated role; service_role only
```

**`inputs` field privacy:** when `inputs_visibility = 'owner-only'` (default for §17 private instance data), the `inputs` jsonb is stripped from SELECT results for non-requester/non-claimer rows. Enforced via a view `request_inbox_public` that aliases `inputs` to NULL when caller isn't requester/claimer. Analogous to §2.1 concept stripping.

### 2.5 `ledger`

```sql
ALTER TABLE public.ledger ENABLE ROW LEVEL SECURITY;

-- Users see their own ledger entries only
CREATE POLICY ledger_own ON public.ledger FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

-- Inserts via settlement RPC only (service_role)
-- No direct INSERT/UPDATE policy for authenticated role
```

### 2.6 Training-data exclusion role (§17.4 guarantee 3, Q14(a))

```sql
-- Dedicated Postgres role for analytics/ML workloads.
-- CANNOT SELECT fields/rows marked training_excluded=true.
CREATE ROLE workflow_analytics NOINHERIT;
GRANT USAGE ON SCHEMA public TO workflow_analytics;

-- Column-level grant: analytics role cannot see private fields
-- Implement via separate view:
CREATE VIEW public.nodes_training_safe AS
SELECT
  node_id, slug, name, domain, status,
  -- concept stripped of training_excluded fields
  public.strip_training_excluded_fields(concept, node_id, 'node') AS concept,
  input_schema, output_schema, structural_hash, tags,
  usage_count, success_count, fail_count, upvote_count,
  fork_count, remix_count, last_edited_at, deprecated,
  created_at, updated_at
FROM public.nodes
WHERE training_excluded = false;

GRANT SELECT ON public.nodes_training_safe TO workflow_analytics;
REVOKE SELECT ON public.nodes FROM workflow_analytics;
-- Attempting to query public.nodes directly as workflow_analytics = permission error.
```

**Structural guarantee:** any pipeline running as `workflow_analytics` (via pgpass or Supabase API key scoped to this role) cannot bypass training exclusion by forgetting a `WHERE` clause. Hard structural enforcement per Q14(a).

---

## 3. `discover_nodes` RPC (§15.1)

### 3.1 Signature

```sql
CREATE FUNCTION public.discover_nodes(
  p_intent        text,
  p_input_schema  jsonb DEFAULT NULL,
  p_output_schema jsonb DEFAULT NULL,
  p_domain_hint   text  DEFAULT NULL,
  p_limit         int   DEFAULT 20,
  p_cross_domain  bool  DEFAULT true,
  p_include_wip   bool  DEFAULT true
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER   -- runs with caller's role; RLS applies
STABLE
AS $$
DECLARE
  v_query_id      uuid := gen_random_uuid();
  v_embedding     vector(1536);
  v_candidates    jsonb;
  v_caller_id     uuid := auth.uid();
BEGIN
  -- 1. Compute embedding for p_intent.
  -- OPEN Q5: embedding compute — inline via pg extension (pgai / pg_vector_remote) OR
  --          Supabase Edge Function → OpenAI/local model OR pre-embed in app code.
  --          Default assumption: Edge Function pre-call populates p_intent_embedding.
  --          For v1, callers pass embedding pre-computed. Revise signature:
  --          add p_intent_embedding vector(1536) NOT NULL parameter.
  v_embedding := public.compute_intent_embedding(p_intent);  -- placeholder

  -- 2. Rank candidates: semantic + structural + quality, respecting RLS.
  WITH ranked AS (
    SELECT
      n.node_id, n.slug, n.name, n.domain, n.status,
      n.owner_user_id = v_caller_id AS is_owner,
      (1 - (n.embedding <=> v_embedding))::real AS semantic_match_score,
      CASE
        WHEN p_input_schema IS NOT NULL AND n.input_schema IS NOT NULL
          THEN public.schema_compat_score(n.input_schema, p_input_schema, n.output_schema, p_output_schema)
        ELSE NULL
      END AS structural_match_score,
      n.usage_count, n.success_count, n.fail_count, n.upvote_count,
      n.fork_count, n.remix_count, n.editing_now_count, n.last_edited_at,
      n.deprecated, n.parents,
      (n.domain IS DISTINCT FROM p_domain_hint) AS cross_domain,
      -- Field stripping: use the public-concept view for non-owners
      CASE
        WHEN n.owner_user_id = v_caller_id THEN n.concept
        ELSE public.strip_private_fields(n.concept, n.node_id, 'node')
      END AS concept
    FROM public.nodes n
    WHERE
      -- RLS handles visibility; WHERE is for discovery filters only
      (p_domain_hint IS NULL OR n.domain = p_domain_hint OR p_cross_domain)
      AND (p_include_wip OR n.status != 'draft')
      AND n.deprecated = false
  ),
  scored AS (
    SELECT *,
      -- Composite rank: semantic + structural (if present) + quality signals
      (semantic_match_score * 0.45
       + COALESCE(structural_match_score, 0) * 0.25
       + LEAST(usage_count::real / 100, 1) * 0.10
       + CASE WHEN success_count + fail_count > 0
              THEN success_count::real / (success_count + fail_count) ELSE 0.5 END * 0.10
       + LEAST(upvote_count::real / 50, 1) * 0.10
      ) AS rank_score
    FROM ranked
    ORDER BY rank_score DESC
    LIMIT p_limit
  )
  SELECT jsonb_build_object(
    'query_id', v_query_id,
    'candidates', jsonb_agg(
      jsonb_build_object(
        'node_id', s.node_id,
        'slug', s.slug,
        'name', s.name,
        'domain', s.domain,
        'status', s.status,
        'is_owner', s.is_owner,
        'semantic_match_score', s.semantic_match_score,
        'structural_match_score', s.structural_match_score,
        'quality', jsonb_build_object(
          'usage_count', s.usage_count,
          'success_rate', CASE WHEN s.success_count + s.fail_count > 0
                               THEN s.success_count::real / (s.success_count + s.fail_count)
                               ELSE NULL END,
          'upvote_count', s.upvote_count,
          'active_collaborators', s.editing_now_count,   -- §15.1 field alias
          'recency', EXTRACT(DAY FROM (now() - s.last_edited_at))::int,
          'fork_count', s.fork_count,
          'remix_count', s.remix_count
        ),
        'provenance', jsonb_build_object(
          'parents', s.parents,
          'children', (
            SELECT COALESCE(jsonb_agg(c.node_id), '[]'::jsonb)
            FROM public.nodes c
            WHERE s.node_id = ANY(c.parents)
            LIMIT 10
          )
        ),
        'active_work', jsonb_build_object(
          'editing_now', s.editing_now_count,
          'pending_requests', (
            SELECT count(*) FROM public.request_inbox r
            WHERE s.node_id = ANY(r.dependency_refs) AND r.state = 'pending'
          ),
          'in_flight_improvement_cycle_id', NULL  -- OPEN Q6: wire once improvement_cycle table spec'd
        ),
        'negative_signals', jsonb_build_object(
          'deprecated', s.deprecated,
          'known_failure_modes', '[]'::jsonb,   -- OPEN Q7: source table deferred
          'contradictory_goal_ids', '[]'::jsonb
        ),
        'cross_domain', s.cross_domain,
        'concept', s.concept   -- already field-stripped for non-owners
      )
    )
  )
  INTO v_candidates
  FROM scored s;

  -- 3. Persist query_id for §15.3(A) "similar-in-progress" subscription hook.
  INSERT INTO public.similar_subscriptions_index (query_id, embedding, similarity_floor, subscriber_user_id)
  VALUES (v_query_id, v_embedding, 0.80, v_caller_id);

  RETURN v_candidates;
END;
$$;

GRANT EXECUTE ON FUNCTION public.discover_nodes TO authenticated;
```

**Concept-only for non-owners** is enforced by the `CASE WHEN n.owner_user_id = v_caller_id THEN n.concept ELSE strip_private_fields(...) END` branch. RLS handles row-level hiding; the CASE handles field-level stripping.

### 3.2 Helper functions

```sql
-- Strip JSON fields whose path is marked 'private' for the given artifact.
CREATE FUNCTION public.strip_private_fields(
  p_concept     jsonb,
  p_artifact_id uuid,
  p_kind        text
) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_out jsonb := p_concept;
  v_path text;
BEGIN
  FOR v_path IN
    SELECT field_path
    FROM public.artifact_field_visibility
    WHERE artifact_id = p_artifact_id
      AND artifact_kind = p_kind
      AND visibility = 'private'
  LOOP
    -- jsonb_set with null / #- operator to remove the path
    v_out := v_out #- string_to_array(trim(leading '/' from v_path), '/');
  END LOOP;
  RETURN v_out;
END;
$$;

-- Similar for training-excluded fields
CREATE FUNCTION public.strip_training_excluded_fields(
  p_concept     jsonb,
  p_artifact_id uuid,
  p_kind        text
) RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_out jsonb := p_concept;
  v_path text;
BEGIN
  FOR v_path IN
    SELECT field_path FROM public.artifact_field_visibility
    WHERE artifact_id = p_artifact_id
      AND artifact_kind = p_kind
      AND training_excluded = true
  LOOP
    v_out := v_out #- string_to_array(trim(leading '/' from v_path), '/');
  END LOOP;
  RETURN v_out;
END;
$$;

-- Structural compatibility score between two schemas.
-- OPEN Q8: implementation deferred. Placeholder returns 0.5 for now.
CREATE FUNCTION public.schema_compat_score(
  a_in jsonb, a_out jsonb, b_in jsonb, b_out jsonb
) RETURNS real LANGUAGE sql IMMUTABLE AS $$
  SELECT 0.5::real;
$$;

-- Embedding computation stub; actual impl lives in Edge Function or pre-call.
CREATE FUNCTION public.compute_intent_embedding(p_text text)
RETURNS vector(1536) LANGUAGE plpgsql STABLE AS $$
BEGIN
  RAISE EXCEPTION 'embedding must be precomputed by caller; see OPEN Q5';
END;
$$;
```

### 3.3 `claim_request` RPC (§14.1 — narrow claim, not poll-all)

```sql
CREATE FUNCTION public.claim_request(p_request_id uuid, p_host_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE
  v_claimed record;
BEGIN
  -- Host must be owned by caller
  IF NOT EXISTS (
    SELECT 1 FROM public.host_pool
    WHERE host_id = p_host_id AND owner_user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'host_not_owned';
  END IF;

  -- Narrow SELECT FOR UPDATE SKIP LOCKED — only this row, only this caller
  SELECT * INTO v_claimed
  FROM public.request_inbox
  WHERE request_id = p_request_id AND state = 'pending'
  FOR UPDATE SKIP LOCKED;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('claimed', false, 'reason', 'already_claimed_or_missing');
  END IF;

  UPDATE public.request_inbox
  SET state = 'claimed', claimed_by_host = p_host_id, claimed_at = now(),
      version = version + 1, updated_at = now()
  WHERE request_id = p_request_id;

  RETURN jsonb_build_object('claimed', true, 'request_id', p_request_id);
END;
$$;
```

---

## 4. Concept/instance boundary — domain examples

Per §17.1 + `project_privacy_per_piece_chatbot_judged.md`.

### 4.1 Invoice-capture node

- **`concept`** (public): purpose ("extract invoice number"), step sequence (OCR → regex → validate), input schema (`{"file": "pdf"}`), output schema (`{"invoice_number": "string"}`), OCR prompt template (generic).
- **`instance_ref`** (private): pointer to `supabase-storage://invoices-private/<user_id>/<batch>/*.pdf` where the user's actual invoices live. Never copied to Postgres; URL-signed for owner-only access.
- **Field-visibility examples:**
  - `/concept/prompt_template` — `public` (generic)
  - `/concept/example_company_name` — `private` (leaks employer)
  - `/concept/file_path_hint` — `private` (leaks host filesystem layout)

### 4.2 Research-paper writeup node

- **`concept`** (public): structural pattern (Hypothesis → Method → Experiment → Discussion), prompt scaffolds, citation formatting rules.
- **`instance_ref`** (private): link to the user's actual draft manuscript on their host.
- **Field-visibility:** `/concept/citation_style` public; `/concept/paper_title_draft` private.

### 4.3 Open fantasy-universe scene node

- **`concept`** (public): scene-drafting patterns, character-consistency checks, prose-style guidelines. Fully public — the whole commons point.
- **`instance_ref`** (null): the universe's canonical canon IS the shared artifact. No private instance layer.
- **Field-visibility:** everything public. Except:
- **OPEN Q9:** confidential fantasy universes (host-set `sensitivity_tier` per the superseded privacy note §17.7 residual). These still exist for whole-universe opt-out. Interaction of the two granularities needs one more pass.

**Three-example takeaway:** the concept/instance split is clean when there's user data (invoice, research paper); the split is degenerate when the artifact IS the commons (fantasy universe). Schema must support both — `instance_ref` nullable + `artifact_field_visibility` defaulting public is sufficient.

---

## 5. Scale primitives per table (§14 cross-ref)

| Table | Scale primitive | §14 ref |
|---|---|---|
| `nodes` | HNSW + GIN + first-class quality columns; no side-table joins | §14.3 + §15.2 |
| `request_inbox` | Partial index on `state='pending'`; dispatch via Realtime channels per capability | §14.1 |
| `host_pool` | No `last_heartbeat` column; Presence derives online state | §14.5 |
| `ledger` | Append-only; materialized balance view if read-hot | §14.9 (ledger consistency) |
| `artifact_field_visibility` | Composite PK point-lookup; joined in concept-stripping VIEW | §17.4 |
| `public_demand_ranked` | Materialized view, 30–60s refresh via pg_cron | §14.4 |
| `nodes_hot` | Materialized view (track K), top-500-per-domain, 60s refresh | §15.4 |
| `similar_subscriptions_index` | KV (Supabase unlogged table or Upstash Redis); Edge Function worker filters | §15.3(A) |

---

## 6. OPEN flags summary (do not invent)

| # | Location | Question |
|---|---|---|
| Q1 | §1.3 | `visibility='network'` allowlist mechanism — per-node ACL or per-user trusted-peers list? |
| Q2 | §1.5 | `host_pool.provider` — hard enum vs open text? |
| Q3 | §2.1 | Network-visibility RLS policy needs Q1's allowlist table first |
| Q4 | §2.2 | `artifact_field_visibility` RLS dispatcher across 5 artifact_kinds (node/goal/branch/soul/comment) |
| Q5 | §3.1 | Embedding compute — inline SQL extension, Edge Function, or pre-computed by caller? v1 default: caller pre-computes. |
| Q6 | §3.1 | `improvement_cycle` table spec deferred to §15.3 converge work |
| Q7 | §3.1 | `known_failure_modes` / `contradictory_goal_ids` source tables not yet defined |
| Q8 | §3.2 | `schema_compat_score` algorithm — structural similarity on JSONSchema shapes |
| Q9 | §4 | Whole-universe `sensitivity_tier` vs per-field visibility — interaction rules |

These are genuinely ambiguous and should not be answered by dev without host/navigator sign-off. Flagged here so track-A coding surfaces them before shipping.

---

## 7. Acceptance criteria

Track A is done when, on a fresh Supabase project:

1. All §1 tables create cleanly; all §1 indexes build; all §2 RLS policies load.
2. `discover_nodes` RPC executes with zero rows in `nodes` (returns empty candidates + query_id).
3. RLS smoke test: `SELECT * FROM nodes` as user A returns zero rows owned by user B with `concept_visibility='private'`, and returns public-concept-layer (stripped) rows for public nodes owned by B.
4. `claim_request` RPC: concurrent 10-caller test against 1 row returns exactly one `claimed=true` and nine `claimed=false` (§14.1 validation).
5. Training-safe role test: `SET ROLE workflow_analytics; SELECT concept FROM nodes;` errors with permission-denied (§17.4 structural enforcement).
6. All 9 OPEN Qs above are either resolved OR explicitly deferred to a named follow-up task.
