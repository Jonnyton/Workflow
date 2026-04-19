-- Core tables from #25 schema spec §1 — subset needed for v0 e2e proof.
-- Omits: host_pool, request_inbox, ledger, wallets, settlement batches.
-- Includes: users, nodes (dual-layer), artifact_field_visibility.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid

-- -----------------------------------------------------------------------
-- users (thin projection; prototype: no auth.users supabase dependency)
-- -----------------------------------------------------------------------
CREATE TABLE public.users (
  user_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  github_handle     text UNIQUE,
  display_name      text NOT NULL,
  account_age_days  int NOT NULL DEFAULT 0,  -- set manually in prototype; normally GENERATED
  interaction_count int NOT NULL DEFAULT 0,
  trust_tier        text NOT NULL DEFAULT 't1' CHECK (trust_tier IN ('t1','t2','t3')),
  version           bigint NOT NULL DEFAULT 1,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------
-- nodes — dual-layer (concept public-biased, instance owner-only)
-- -----------------------------------------------------------------------
CREATE TABLE public.nodes (
  node_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug                 text NOT NULL,
  name                 text NOT NULL,
  domain               text NOT NULL,
  status               text NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft','published','deprecated','superseded')),
  owner_user_id        uuid NOT NULL REFERENCES public.users(user_id),
  concept              jsonb NOT NULL,
  instance_ref         text NULL,
  concept_visibility   text NOT NULL DEFAULT 'public'
                         CHECK (concept_visibility IN ('public','private','network')),
  input_schema         jsonb,
  output_schema        jsonb,
  structural_hash      text NOT NULL DEFAULT '',
  embedding            vector(16),  -- v0: 16-dim stub (real: 1536). Tests generate deterministic vecs.
  tags                 text[] NOT NULL DEFAULT '{}',
  parents              uuid[] NOT NULL DEFAULT '{}',
  usage_count          int NOT NULL DEFAULT 0,
  success_count        int NOT NULL DEFAULT 0,
  fail_count           int NOT NULL DEFAULT 0,
  upvote_count         int NOT NULL DEFAULT 0,
  fork_count           int NOT NULL DEFAULT 0,
  remix_count          int NOT NULL DEFAULT 0,
  editing_now_count    int NOT NULL DEFAULT 0,
  last_edited_at       timestamptz NOT NULL DEFAULT now(),
  deprecated           bool NOT NULL DEFAULT false,
  training_excluded    bool NOT NULL DEFAULT false,
  version              bigint NOT NULL DEFAULT 1,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_user_id, slug)
);

CREATE INDEX nodes_domain_status ON public.nodes (domain, status);
CREATE INDEX nodes_owner         ON public.nodes (owner_user_id);
-- v0 skips HNSW; real build uses:
-- CREATE INDEX nodes_embedding_hnsw ON public.nodes USING hnsw (embedding vector_cosine_ops);

-- -----------------------------------------------------------------------
-- artifact_field_visibility — per-field visibility decisions (§17)
-- -----------------------------------------------------------------------
CREATE TABLE public.artifact_field_visibility (
  artifact_id       uuid NOT NULL,
  artifact_kind     text NOT NULL CHECK (artifact_kind IN ('node','goal','branch','soul','comment')),
  field_path        text NOT NULL,
  visibility        text NOT NULL CHECK (visibility IN ('public','private','network')),
  reason            text,
  decided_at        timestamptz NOT NULL DEFAULT now(),
  decided_by        text NOT NULL CHECK (decided_by IN ('chatbot','user','owner')),
  training_excluded bool NOT NULL DEFAULT false,
  PRIMARY KEY (artifact_id, artifact_kind, field_path)
);

CREATE INDEX afv_kind_id ON public.artifact_field_visibility (artifact_kind, artifact_id);
