# Remix (Track I) + Convergence (Track K) — Detail Spec

**Date:** 2026-04-18
**Author:** dev (task #53; last pre-spec filling the final two tracks)
**Status:** Pre-draft. These tracks are heavily covered by existing specs + design-note §15.3; this doc fills the gaps that separate "dev-executable" from "really-dev-executable."
**Source of truth:**
- `docs/design-notes/2026-04-18-full-platform-architecture.md` §15.3 (A/B/C convergence primitives).
- `docs/specs/2026-04-18-full-platform-schema-sketch.md` §1.2 (`nodes.parents uuid[]`, `remix_count`, `fork_count`).
- `docs/specs/2026-04-18-mcp-gateway-skeleton.md` §3.1 (`remix_node`, `converge_nodes` MCP tools).
- Memory: `project_convergent_design_commons.md` (Wikipedia-scale convergent design as the norm).

Track I ships `remix_node(draft_from[], intent, modifications)` with provenance preservation. Track K ships `converge_nodes(source_ids[], target_name, rationale)` with editor-threshold approval. Most of the work is already specified elsewhere; this doc fills in specific RPC bodies, edge cases, and UI hooks.

---

## Track I — Remix (remix-from-N)

### I.1 RPC body (building on #25 §3.1 signature)

```sql
CREATE FUNCTION public.remix_node(
  p_draft_from     uuid[],          -- N parents, N >= 1
  p_intent         text,
  p_modifications  text,
  p_new_name       text DEFAULT NULL,
  p_new_domain     text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
AS $$
DECLARE
  v_user_id       uuid := auth.uid();
  v_new_node_id   uuid := gen_random_uuid();
  v_parent        record;
  v_merged_concept jsonb := '{}'::jsonb;
  v_first_parent  record;
  v_existing_slug text;
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'auth_required';
  END IF;

  IF array_length(p_draft_from, 1) < 1 THEN
    RAISE EXCEPTION 'remix_needs_at_least_one_parent';
  END IF;

  -- Verify each parent is readable to the caller (RLS allows)
  FOR v_parent IN
    SELECT node_id, concept, domain, name, tags, input_schema, output_schema,
           structural_hash, owner_user_id, concept_visibility
    FROM public.nodes
    WHERE node_id = ANY(p_draft_from)
  LOOP
    -- RLS already filtered what caller can see; but also require parents be public
    -- or owned by caller (no remixing someone else's private material)
    IF v_parent.concept_visibility NOT IN ('public')
       AND v_parent.owner_user_id != v_user_id THEN
      RAISE EXCEPTION 'cannot_remix_private_parent: %', v_parent.node_id;
    END IF;
    -- Shallow merge: later parents override earlier fields.
    -- (Real strategy is chatbot-guided; this is the programmatic default.)
    v_merged_concept := v_merged_concept || v_parent.concept;
    IF v_first_parent IS NULL THEN
      v_first_parent := v_parent;
    END IF;
  END LOOP;

  IF array_length(p_draft_from, 1) != (
       SELECT COUNT(*) FROM public.nodes WHERE node_id = ANY(p_draft_from)
     ) THEN
    RAISE EXCEPTION 'some_parents_not_readable';
  END IF;

  -- Generate slug from name + short hash
  v_existing_slug := COALESCE(p_new_name, v_first_parent.name) || '-' ||
                     substring(v_new_node_id::text, 1, 8);

  -- Insert the remix with parents[] preserving lineage
  INSERT INTO public.nodes (
    node_id, slug, name, domain, status, owner_user_id,
    concept, concept_visibility,
    input_schema, output_schema, structural_hash,
    tags, parents, remix_count
  ) VALUES (
    v_new_node_id,
    lower(regexp_replace(v_existing_slug, '\s+', '-', 'g')),
    COALESCE(p_new_name, v_first_parent.name || ' (remix)'),
    COALESCE(p_new_domain, v_first_parent.domain),
    'draft',
    v_user_id,
    v_merged_concept || jsonb_build_object(
      '_remix_intent', p_intent,
      '_remix_modifications', p_modifications
    ),
    'public',  -- remixes default public; owner can privatize later
    v_first_parent.input_schema,
    v_first_parent.output_schema,
    v_first_parent.structural_hash,  -- shape preserved; owner updates if truly diverged
    v_first_parent.tags,
    p_draft_from,                    -- lineage
    0
  );

  -- Increment remix_count on each parent (trigger does this via node_activity,
  -- but we fire explicitly here to avoid trigger ordering surprises)
  UPDATE public.nodes
     SET remix_count = remix_count + 1
   WHERE node_id = ANY(p_draft_from);

  -- Record event
  INSERT INTO public.node_activity (node_id, actor_user_id, event_kind, payload)
  VALUES (
    v_new_node_id, v_user_id, 'remixed',
    jsonb_build_object(
      'parents', to_jsonb(p_draft_from),
      'intent', p_intent
    )
  );

  RETURN jsonb_build_object(
    'new_node_id', v_new_node_id,
    'provenance_chain', to_jsonb(p_draft_from)
  );
END;
$$;

GRANT EXECUTE ON FUNCTION public.remix_node TO authenticated;
```

### I.2 Edge cases + behaviors

- **N=1 remix** is a **fork** — structurally identical, just different name in the RPC. Chatbot uses `remix_node([parent], ...)` when forking; `fork_count` + `remix_count` both increment. Explicit; no hidden second API.
- **Circular lineage prevention.** When computing ancestry, walk `parents[]` with a visited-set. A cycle would indicate either a buggy import or a malicious write — reject at the RPC level before insert. Implementation: walk N levels deep (N=20 default); if still growing, abort.
- **Self-remix refused.** Caller can't include the artifact being created as a parent. Enforced by `gen_random_uuid()` inside the function + check loop.
- **Private-parent refuse.** A user who cannot SELECT a parent row (via RLS) also cannot remix from it. Double-checked by the `cannot_remix_private_parent` explicit test for owner-private nodes the caller happens to see (e.g. their own private node mixing with a public one).
- **Attribution preserved forever.** The `parents uuid[]` column is append-only in the sense that deletes cascade-to-superseded (not to-NULL). Wiki-orphan deletion (per `project_q10_q11_q12_resolutions.md` Q12b) anonymizes the parent's author but keeps the node itself in the lineage.
- **Concept-merge strategy is simple-default.** Shallow jsonb-merge with later parents winning. Real chatbot-guided remix chooses selectively. The RPC gives callers the programmatic default; the MCP tool's body calls this with a chatbot-built `concept` override when the chatbot did careful merging.

### I.3 MCP tool wrapper (gateway side — for cross-ref to #27 §3.1)

```python
@mcp.tool()
def remix_node(
    draft_from: list[str],
    intent: str,
    modifications: str,
    new_name: str | None = None,
    new_domain: str | None = None,
    concept_override: dict | None = None,  # chatbot-guided
    bearer_token: str = "",
) -> dict:
    """Remix N parent nodes into a new derivative.

    When concept_override is None, uses programmatic-default shallow merge.
    When concept_override is provided, the gateway passes it directly to
    a variant RPC (remix_node_with_concept) that uses the chatbot's merge.
    """
    ...
```

### I.4 Web app hook (cross-ref to #35)

- `/catalog/nodes/<slug>` page surfaces a **"Remix" button** → opens Claude.ai chat with `/remix <node_id>` prefilled (or in-browser editor if present).
- `/editor/nodes/<id>` can take `?remix_from=id1,id2,id3` query param and open pre-populated with the programmatic merge, letting user edit before committing.

### I.5 Load-test impact (cross-ref to #26)

- Add **S1b — remix contention:** 100 concurrent callers each remix the same popular parent. Verify `remix_count` updates atomic + no deadlock. Variant of S3 hot-node CAS.
- Storage growth model: remixes are full rows, not diffs. A 100-remix popular node creates 100 new rows, each ~few KB. Model: 10k nodes × avg remix_count 5 = 50k nodes at scale. Well within pgvector's 1M-row comfort zone.

### I.6 Dev-day estimate

| Work | Estimate |
|---|---|
| `remix_node` RPC + circular-lineage walker helper | 0.4 d |
| `remix_node_with_concept` variant for chatbot-merged | 0.2 d |
| MCP tool wrapper + error-envelope mapping | 0.15 d |
| Web app `/catalog/<slug>` Remix button + Claude.ai deep-link | 0.15 d |
| Web app `/editor?remix_from=...` pre-population flow | 0.25 d |
| Tests: N=1 fork / N=3 merge / circular refuse / private-parent refuse / attribution-preserved | 0.3 d |
| Load-test S1b remix-contention add | 0.1 d |
| **Total** | **~1.55 d** |

Navigator's §10 (track I + remix): 1 d. Revision +0.5 d, consistent with prior specs' under-count pattern.

---

## Track K — Converge (nodes merge back to a canonical)

### K.1 Three-phase flow

Convergence is NOT an atomic operation — it's a **proposal → ratification → merge** flow. This is the Wikipedia-merge pattern: two independent efforts agree on a canonical, with audit trail.

```
Alice owns node-A (invoice OCR, 5 weeks active)
Bob owns node-B (invoice OCR, 3 weeks active, came at it from different angle)

Phase 1 — Propose:
  Alice (or Bob, or a third party) calls propose_convergence(
    source_ids=[A, B],
    target_name="Invoice OCR (canonical)",
    rationale="Same purpose + compatible I/O; B's error-handling is
               stronger, A's prompt is clearer. Propose merged canonical."
  )
  → Creates row in converge_proposals.

Phase 2 — Ratify:
  Each source's editor(s) must approve (an "editor" = owner + anyone with
  ≥N merged edits to the node, threshold from mod_config).
  propose_convergence returns proposal_id; editors call
  ratify_convergence(proposal_id).
  When ratification_count >= required_ratifications (default: 1 per source
  for MVP; configurable): auto-advance to Phase 3.

Phase 3 — Merge:
  When ratified: converge_nodes(proposal_id) RPC executes:
    - Create canonical node (similar to remix with parents=source_ids)
    - Flip each source's status to 'superseded'
    - Set each source's superseded_by = canonical_node_id
    - Discovery surfaces canonical first; supersededs hidden from default search.
    - Audit trail preserved in converge_decisions.
```

### K.2 RPC bodies

```sql
-- Phase 1: propose
CREATE FUNCTION public.propose_convergence(
  p_source_ids  uuid[],
  p_target_name text,
  p_rationale   text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_proposal_id uuid := gen_random_uuid();
BEGIN
  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'auth_required';
  END IF;

  IF array_length(p_source_ids, 1) < 2 THEN
    RAISE EXCEPTION 'convergence_needs_at_least_two_sources';
  END IF;

  -- All sources must be readable + public + not-already-superseded
  IF EXISTS (
    SELECT 1 FROM public.nodes
    WHERE node_id = ANY(p_source_ids)
      AND (status IN ('superseded', 'deprecated')
           OR concept_visibility != 'public')
  ) THEN
    RAISE EXCEPTION 'source_not_eligible_for_convergence';
  END IF;

  INSERT INTO public.converge_proposals (
    proposal_id, source_ids, target_name, rationale,
    proposer_user_id, status, created_at
  ) VALUES (
    v_proposal_id, p_source_ids, p_target_name, p_rationale,
    v_user_id, 'pending', now()
  );

  RETURN jsonb_build_object(
    'proposal_id', v_proposal_id,
    'status', 'pending',
    'awaiting_ratifications_from', p_source_ids
  );
END;
$$;


-- Phase 2: ratify
CREATE FUNCTION public.ratify_convergence(p_proposal_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
AS $$
DECLARE
  v_user_id uuid := auth.uid();
  v_proposal record;
  v_eligible_source uuid;
  v_ratification_count int;
  v_needed int;
BEGIN
  SELECT * INTO v_proposal FROM public.converge_proposals
   WHERE proposal_id = p_proposal_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'proposal_not_found';
  END IF;
  IF v_proposal.status != 'pending' THEN
    RAISE EXCEPTION 'proposal_not_pending: status=%', v_proposal.status;
  END IF;

  -- Caller must be editor of at least one source they haven't yet ratified for
  SELECT source_id INTO v_eligible_source
  FROM unnest(v_proposal.source_ids) AS source_id
  WHERE EXISTS (
    SELECT 1 FROM public.nodes n
    WHERE n.node_id = source_id AND n.owner_user_id = v_user_id
  )
  AND NOT EXISTS (
    SELECT 1 FROM public.converge_ratifications
    WHERE proposal_id = p_proposal_id
      AND source_id = source_id
      AND ratifier_user_id = v_user_id
  )
  LIMIT 1;

  IF v_eligible_source IS NULL THEN
    RAISE EXCEPTION 'not_eligible_ratifier_for_remaining_sources';
  END IF;

  INSERT INTO public.converge_ratifications (
    proposal_id, source_id, ratifier_user_id, ratified_at
  ) VALUES (
    p_proposal_id, v_eligible_source, v_user_id, now()
  );

  -- Count ratifications so far
  SELECT COUNT(DISTINCT source_id) INTO v_ratification_count
  FROM public.converge_ratifications
  WHERE proposal_id = p_proposal_id;

  v_needed := array_length(v_proposal.source_ids, 1);

  IF v_ratification_count >= v_needed THEN
    -- Auto-advance to Phase 3 (merge)
    PERFORM public._execute_convergence(p_proposal_id);
    RETURN jsonb_build_object(
      'ratification_count', v_ratification_count,
      'status', 'merged'
    );
  END IF;

  RETURN jsonb_build_object(
    'ratification_count', v_ratification_count,
    'needed', v_needed,
    'status', 'pending'
  );
END;
$$;


-- Phase 3: execute (internal helper)
CREATE FUNCTION public._execute_convergence(p_proposal_id uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER  -- elevated to write superseded status
AS $$
DECLARE
  v_proposal record;
  v_canonical_id uuid := gen_random_uuid();
  v_merged_concept jsonb := '{}'::jsonb;
  v_source_row record;
BEGIN
  SELECT * INTO v_proposal FROM public.converge_proposals
   WHERE proposal_id = p_proposal_id;

  -- Shallow-merge concepts (same default as remix; chatbot can provide override
  -- via a converge_nodes_with_concept variant not shown here)
  FOR v_source_row IN
    SELECT * FROM public.nodes WHERE node_id = ANY(v_proposal.source_ids)
  LOOP
    v_merged_concept := v_merged_concept || v_source_row.concept;
  END LOOP;

  INSERT INTO public.nodes (
    node_id, slug, name, domain, status, owner_user_id,
    concept, concept_visibility, parents, structural_hash,
    input_schema, output_schema
  )
  SELECT
    v_canonical_id,
    lower(regexp_replace(v_proposal.target_name || '-' ||
                         substring(v_canonical_id::text, 1, 8),
                         '\s+', '-', 'g')),
    v_proposal.target_name,
    (SELECT domain FROM public.nodes WHERE node_id = v_proposal.source_ids[1]),
    'published',
    v_proposal.proposer_user_id,
    v_merged_concept,
    'public',
    v_proposal.source_ids,
    (SELECT structural_hash FROM public.nodes WHERE node_id = v_proposal.source_ids[1]),
    (SELECT input_schema FROM public.nodes WHERE node_id = v_proposal.source_ids[1]),
    (SELECT output_schema FROM public.nodes WHERE node_id = v_proposal.source_ids[1]);

  -- Flip sources to superseded
  UPDATE public.nodes
     SET status = 'superseded', superseded_by = v_canonical_id
   WHERE node_id = ANY(v_proposal.source_ids);

  UPDATE public.converge_proposals
     SET status = 'merged',
         canonical_node_id = v_canonical_id,
         merged_at = now()
   WHERE proposal_id = p_proposal_id;

  INSERT INTO public.converge_decisions (
    proposal_id, decision, decided_at
  ) VALUES (p_proposal_id, 'merged', now());
END;
$$;
```

### K.3 Data model additions

```sql
CREATE TABLE public.converge_proposals (
  proposal_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_ids         uuid[] NOT NULL,
  target_name        text NOT NULL,
  rationale          text NOT NULL,
  proposer_user_id   uuid NOT NULL REFERENCES public.users(user_id),
  status             text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'merged', 'withdrawn', 'rejected')),
  canonical_node_id  uuid NULL REFERENCES public.nodes(node_id),
  created_at         timestamptz NOT NULL DEFAULT now(),
  merged_at          timestamptz
);

CREATE TABLE public.converge_ratifications (
  proposal_id       uuid NOT NULL REFERENCES public.converge_proposals(proposal_id),
  source_id         uuid NOT NULL,
  ratifier_user_id  uuid NOT NULL REFERENCES public.users(user_id),
  ratified_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (proposal_id, source_id, ratifier_user_id)
);

CREATE TABLE public.converge_decisions (
  decision_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  proposal_id  uuid NOT NULL REFERENCES public.converge_proposals(proposal_id),
  decision     text NOT NULL CHECK (decision IN ('merged', 'withdrawn', 'rejected')),
  rationale    text,
  decided_at   timestamptz NOT NULL DEFAULT now()
);

-- Extend nodes status CHECK + add superseded_by (if not already from #25/§36)
ALTER TABLE public.nodes
  ADD COLUMN IF NOT EXISTS superseded_by uuid REFERENCES public.nodes(node_id);
```

### K.4 Edge cases

- **Hostile convergence** prevented by ratification requirement. An attacker can't propose convergence of other people's nodes and have it auto-merge.
- **Partial ratification stalemate** — proposal sits in `pending` if at least one source's editor refuses. Proposer can withdraw via `withdraw_convergence(proposal_id)`. Auto-withdraw after 30 days of inactivity.
- **Source modified during proposal** — if a source is updated after a proposal is filed, ratifiers see a warning: "source X was modified since proposal; re-read or refuse." Ratification still proceeds at caller's call.
- **Superseded node discovery** — discovery surfaces the canonical first; supersededs accessible via direct URL + show "superseded by [canonical]" banner. Provenance chain intact.
- **Cross-domain convergence** — two nodes in different domains CAN converge if their input/output schemas are compatible. The canonical inherits `domain` from source_ids[0] by convention; ratifiers should agree this is acceptable in the proposal rationale.

### K.5 Discovery integration

`discover_nodes` (per #25 §3.1) already respects `deprecated=true`; extend to also respect `status='superseded'`:

```sql
-- In the ranked CTE within discover_nodes, add:
AND n.status NOT IN ('superseded', 'deprecated')
```

When a caller explicitly requests a superseded node by ID, return it with a `superseded_by: <canonical_id>` field so the UI can redirect.

### K.6 MCP tool wrapper

```python
@mcp.tool()
def propose_convergence(
    source_ids: list[str],
    target_name: str,
    rationale: str,
    bearer_token: str = "",
) -> dict: ...

@mcp.tool()
def ratify_convergence(
    proposal_id: str,
    bearer_token: str = "",
) -> dict: ...

@mcp.tool()
def withdraw_convergence(
    proposal_id: str,
    bearer_token: str = "",
) -> dict: ...
```

### K.7 Web app hook

- **`/catalog/proposals/`** lists open converge proposals, filterable by domain, proposer, source artifacts.
- **`/catalog/proposals/<id>`** shows proposal detail + ratification status + per-source side-by-side comparison.
- **`/editor/nodes/<id>`** shows a banner if any open converge proposal includes this node: "This node is part of an open convergence proposal. Review?"

### K.8 Moderation integration (cross-ref #36)

Converge proposals themselves are subject to flagging. If a proposal is clearly hostile (user flags it as such), it enters moderation review. If upheld, proposal is force-withdrawn; source nodes stay as-is.

### K.8b Post-merge rollback

**Window:** 30 days from `converge_proposals.merged_at`. Within this window, any of the original source-node editors OR any admin-pool member can initiate rollback.

**Why 30 days:** long enough for the community to notice if a canonical is worse than its sources; short enough that downstream remixers haven't built an irreversible tree of derivatives. Cross-refs account-deletion grace window (§account spec #35 §8) for consistency.

```sql
CREATE FUNCTION public.rollback_convergence(
  p_proposal_id uuid,
  p_rationale   text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_proposal record;
  v_user_id uuid := auth.uid();
  v_is_source_editor bool;
  v_is_admin bool;
BEGIN
  SELECT * INTO v_proposal FROM public.converge_proposals
   WHERE proposal_id = p_proposal_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'proposal_not_found';
  END IF;
  IF v_proposal.status != 'merged' THEN
    RAISE EXCEPTION 'proposal_not_merged: status=%', v_proposal.status;
  END IF;
  IF v_proposal.merged_at < now() - interval '30 days' THEN
    RAISE EXCEPTION 'rollback_window_expired';
  END IF;

  -- Caller authority: must be source-node editor OR admin-pool member
  SELECT EXISTS (
    SELECT 1 FROM public.nodes
    WHERE node_id = ANY(v_proposal.source_ids) AND owner_user_id = v_user_id
  ) INTO v_is_source_editor;

  SELECT mod_role = 'host_admin' INTO v_is_admin
   FROM public.users WHERE user_id = v_user_id;

  IF NOT (v_is_source_editor OR v_is_admin) THEN
    RAISE EXCEPTION 'not_eligible_rollback_caller';
  END IF;

  -- Restore sources to 'published'; clear superseded_by
  UPDATE public.nodes
     SET status = 'published', superseded_by = NULL
   WHERE node_id = ANY(v_proposal.source_ids);

  -- Deprecate the canonical (don't delete — derivatives may already link to it)
  UPDATE public.nodes
     SET status = 'deprecated', deprecated = true
   WHERE node_id = v_proposal.canonical_node_id;

  -- Mark the proposal as rolled-back; preserve full audit history
  UPDATE public.converge_proposals
     SET status = 'rolled_back',
         rolled_back_at = now(),
         rollback_rationale = p_rationale
   WHERE proposal_id = p_proposal_id;

  INSERT INTO public.converge_decisions (
    proposal_id, decision, rationale, decided_at
  ) VALUES (p_proposal_id, 'rolled_back', p_rationale, now());

  RETURN jsonb_build_object('rolled_back', true, 'sources_restored', v_proposal.source_ids);
END;
$$;
```

**Schema additions** (extend §K.3 `converge_proposals`):

```sql
ALTER TABLE public.converge_proposals
  ADD COLUMN rolled_back_at timestamptz,
  ADD COLUMN rollback_rationale text;

ALTER TABLE public.converge_proposals
  DROP CONSTRAINT converge_proposals_status_check,
  ADD CONSTRAINT converge_proposals_status_check CHECK (
    status IN ('pending', 'merged', 'withdrawn', 'rejected', 'rolled_back')
  );

ALTER TABLE public.converge_decisions
  DROP CONSTRAINT converge_decisions_decision_check,
  ADD CONSTRAINT converge_decisions_decision_check CHECK (
    decision IN ('merged', 'withdrawn', 'rejected', 'rolled_back')
  );
```

**Why canonical → deprecated, not deleted:** remix derivatives of the canonical may exist. Hard-deleting the canonical would orphan their `parents[]` pointers. Deprecating keeps it readable (with a banner: "This node was converged, then rolled back — sources restored; this canonical is retained for lineage") without surfacing it in default discovery.

**What rollback does NOT undo:**

- `remix_count` increments on the canonical's parents (the sources) — these stayed accurate throughout.
- Public-concept fields that the community already remixed from the canonical — those remixes stay published; their `parents[]` still points at the now-deprecated canonical. The remixer sees a "parent is deprecated" banner + can optionally re-parent to one of the restored sources.
- Any chatbot-conversation memory or external tooling that cached the canonical's content.

### K.8c Rollback MCP tool

```python
@mcp.tool()
def rollback_convergence(
    proposal_id: str,
    rationale: str,
    bearer_token: str = "",
) -> dict: ...
```

Returns the standard error envelope on ineligibility (`not_eligible_rollback_caller`, `rollback_window_expired`, `proposal_not_merged`).

### K.9 Dev-day estimate

| Work | Estimate |
|---|---|
| 3 new tables (proposals, ratifications, decisions) + ALTER nodes | 0.15 d |
| `propose_convergence` RPC | 0.3 d |
| `ratify_convergence` RPC + auto-advance logic | 0.35 d |
| `_execute_convergence` helper + superseded status flip | 0.3 d |
| `withdraw_convergence` RPC + 30-day auto-withdraw cron | 0.15 d |
| `discover_nodes` extension for superseded-status filter | 0.1 d |
| 3 MCP tools + error-envelope wiring | 0.15 d |
| Web app `/catalog/proposals/` list + detail pages | 0.4 d |
| Web app `/editor` banner + redirect hooks | 0.15 d |
| Tests: propose / ratify-partial / ratify-final / withdraw / hostile-refuse / superseded-hidden / redirect | 0.4 d |
| **Total** | **~2.45 d** |

Navigator's §10 (track K): ~1 d. Revision +1.45 d.

---

## Combined totals

- **Track I revision:** 1 d → 1.55 d (+0.55).
- **Track K revision:** 1 d → 2.45 d (+1.45).
- Combined: +2 d over navigator's §10.

**Session revision tally update:** +17 (prior) + 2 (this spec) = **+19 d** across 9 specs + 2 amendments.

---

## OPEN flags

| # | Question |
|---|---|
| Q1 | **Ratifier threshold per source.** MVP: owner ratifies (1 per source). Future: if source has multiple co-editors, require majority? Recommend MVP start simple; scale if multi-editor nodes become common. |
| Q2 | **Forced convergence by host-admin pool.** Should admin pool be able to force-converge two clearly-duplicate nodes with no participation from original authors? Recommend NO at MVP — respects per-source owner authority. |
| Q3 | **Concept-merge chatbot variant.** `remix_node_with_concept` + `converge_nodes_with_concept` — are these separate RPCs or extra params on the primary? Recommend separate (cleaner RPC signatures). |
| Q4 | **Cross-domain convergence UX.** When sources differ in domain, which wins in `canonical.domain`? Recommend: ratifier's required `rationale` must explicitly state the chosen domain; RPC takes optional `target_domain` param. |
| Q5 | **Remix licensing.** CC0 means remixes don't need license compatibility check — but if future supports CC-BY-SA nodes, compatibility matters. v0 skips since all content is CC0; flag for future multi-license support. |
| Q6 | **Remix of a superseded node.** Can you remix from a superseded node? YES — its concept is still valid; it just isn't the current canonical. Flagged so the RPC doesn't accidentally refuse. |
| Q7 | **Convergence involving user's private node.** If Alice has a private node that's clearly similar to Bob's public node, can Alice propose convergence? Recommend: propose requires Alice publish her version first (status + visibility flip), THEN propose; private → public flip is already tracked by export pipeline. |

---

## Acceptance criteria

Tracks I + K complete when:

1. All 5 RPCs (`remix_node`, `propose_convergence`, `ratify_convergence`, `withdraw_convergence`, `_execute_convergence`) migrate + pass smoke tests.
2. 3 new tables create cleanly.
3. `discover_nodes` filters superseded by default; explicit fetch of a superseded node returns `superseded_by` redirect hint.
4. E2E smoke: Alice remixes from 2 public nodes → new node appears with both as parents + remix_count on each parent incremented.
5. E2E smoke: Alice + Bob converge their two similar nodes → ratification chain → canonical node appears as `published`, sources flip to `superseded_by=canonical_id`.
6. Web app `/catalog/nodes/<slug>` shows Remix button + proposal banner when applicable.
7. All 7 OPEN flags resolved or deferred.

If any of the above fails, convergence-as-norm promise from `project_convergent_design_commons.md` has a functional gap.
