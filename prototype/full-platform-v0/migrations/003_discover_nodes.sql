-- discover_nodes RPC per #25 schema spec §3.1 — simplified for v0.
-- v0 simplifications:
--   - Caller must pre-compute the embedding (no inline extension).
--   - structural_match_score always returns NULL (no schema-compat function in v0).
--   - No similar_subscriptions_index side-effect (defer to track K).

CREATE OR REPLACE FUNCTION public.discover_nodes(
  p_intent        text,
  p_intent_embedding vector(16),
  p_input_schema  jsonb DEFAULT NULL,
  p_output_schema jsonb DEFAULT NULL,
  p_domain_hint   text  DEFAULT NULL,
  p_limit         int   DEFAULT 20,
  p_cross_domain  bool  DEFAULT true
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
STABLE
AS $$
DECLARE
  v_query_id uuid := gen_random_uuid();
  v_caller_id uuid := auth.uid();
  v_candidates jsonb;
BEGIN
  WITH ranked AS (
    SELECT
      n.node_id, n.slug, n.name, n.domain, n.status,
      n.owner_user_id = v_caller_id AS is_owner,
      (1 - (n.embedding <=> p_intent_embedding))::real AS semantic_match_score,
      n.usage_count, n.success_count, n.fail_count, n.upvote_count,
      n.fork_count, n.remix_count, n.editing_now_count, n.last_edited_at,
      n.deprecated, n.parents,
      (n.domain IS DISTINCT FROM p_domain_hint) AS cross_domain,
      CASE
        WHEN n.owner_user_id = v_caller_id THEN n.concept
        ELSE public.strip_private_fields(n.concept, n.node_id, 'node')
      END AS concept
    FROM public.nodes n
    WHERE
      (p_domain_hint IS NULL OR n.domain = p_domain_hint OR p_cross_domain)
      AND n.deprecated = false
      AND n.embedding IS NOT NULL
  ),
  scored AS (
    SELECT *,
      (semantic_match_score * 0.45
       + LEAST(usage_count::real / 100, 1) * 0.15
       + CASE WHEN success_count + fail_count > 0
              THEN success_count::real / (success_count + fail_count) ELSE 0.5 END * 0.15
       + LEAST(upvote_count::real / 50, 1) * 0.15
      ) AS rank_score
    FROM ranked
    ORDER BY rank_score DESC
    LIMIT p_limit
  )
  SELECT jsonb_build_object(
    'query_id', v_query_id,
    'candidates', COALESCE(jsonb_agg(
      jsonb_build_object(
        'node_id', s.node_id,
        'slug', s.slug,
        'name', s.name,
        'domain', s.domain,
        'status', s.status,
        'is_owner', s.is_owner,
        'semantic_match_score', s.semantic_match_score,
        'quality', jsonb_build_object(
          'usage_count', s.usage_count,
          'success_rate', CASE WHEN s.success_count + s.fail_count > 0
                               THEN s.success_count::real / (s.success_count + s.fail_count)
                               ELSE NULL END,
          'upvote_count', s.upvote_count,
          'active_collaborators', s.editing_now_count,
          'recency', EXTRACT(DAY FROM (now() - s.last_edited_at))::int,
          'fork_count', s.fork_count,
          'remix_count', s.remix_count
        ),
        'provenance', jsonb_build_object(
          'parents', s.parents,
          'children', '[]'::jsonb  -- v0: skip children lookup
        ),
        'cross_domain', s.cross_domain,
        'concept', s.concept
      )
    ), '[]'::jsonb)
  )
  INTO v_candidates
  FROM scored s;

  RETURN v_candidates;
END;
$$;

GRANT EXECUTE ON FUNCTION public.discover_nodes TO PUBLIC;
