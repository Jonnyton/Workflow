"""Agentic retrieval router -- decomposes compound queries and routes.

The LLM decides what kind of question is being asked and decomposes
compound queries into sub-queries routed to HippoRAG (entity/relationship),
RAPTOR (thematic/global), or LanceDB vectors (tone/similarity).
"""

from __future__ import annotations

import json
import re
from typing import Callable

import numpy as np

from workflow.knowledge.hipporag import HippoRAG
from workflow.knowledge.knowledge_graph import KnowledgeGraph
from workflow.knowledge.models import (
    FactWithContext,
    QueryType,
    RetrievalResult,
    SubQuery,
)
from workflow.knowledge.raptor import RaptorTree, query_raptor_tree
from workflow.retrieval.phase_context import should_use_backend
from workflow.retrieval.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Query decomposition
# ---------------------------------------------------------------------------

DECOMPOSITION_SYSTEM = (
    "You are a query decomposition engine. Given a compound query about "
    "a fantasy narrative, break it into sub-queries. Each sub-query should "
    "be routed to the right retrieval backend.\n\n"
    "Backend types:\n"
    "- entity_relationship: for character/faction relationships, who-knows-what\n"
    "- thematic_global: for big-picture questions spanning chapters/books\n"
    "- tone_similarity: for finding similar prose, voice matching, mood\n\n"
    "Output valid JSON: a list of objects with 'text', 'query_type', 'entity_hints'."
)

DECOMPOSITION_PROMPT = """Decompose this query into sub-queries.

Query: {query}
Phase: {phase}
Context: Retrieving for a {phase} node in a fantasy writing system.

Return JSON list. Example:
[
  {{"text": "Ryn's relationships with Ashwater",
    "query_type": "entity_relationship",
    "entity_hints": ["ryn", "ashwater"]}},
  {{"text": "winter atmosphere in the northern pass",
    "query_type": "tone_similarity", "entity_hints": []}}
]"""


def _parse_decomposition(raw: str) -> list[SubQuery]:
    """Parse LLM decomposition response into SubQuery objects."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: treat entire query as a single entity_relationship query
        return [SubQuery(text=raw, query_type=QueryType.ENTITY_RELATIONSHIP)]

    return [
        SubQuery(
            text=item.get("text", ""),
            query_type=QueryType(item.get("query_type", "entity_relationship")),
            entity_hints=item.get("entity_hints", []),
        )
        for item in items
    ]


def _simple_decompose(query: str) -> list[SubQuery]:
    """Rule-based fallback decomposition (no LLM needed).

    Useful for testing or when the LLM is unavailable.
    """
    query_lower = query.lower()

    # Detect query type from keywords
    if any(kw in query_lower for kw in ["relationship", "knows", "alliance", "faction", "who"]):
        return [SubQuery(text=query, query_type=QueryType.ENTITY_RELATIONSHIP)]
    elif any(kw in query_lower for kw in ["theme", "arc", "overall", "summary", "global"]):
        return [SubQuery(text=query, query_type=QueryType.THEMATIC_GLOBAL)]
    elif any(kw in query_lower for kw in ["tone", "voice", "mood", "atmosphere", "prose", "style"]):
        return [SubQuery(text=query, query_type=QueryType.TONE_SIMILARITY)]
    else:
        return [SubQuery(text=query, query_type=QueryType.ENTITY_RELATIONSHIP)]


# ---------------------------------------------------------------------------
# Phase-aware retrieval methods
# ---------------------------------------------------------------------------

# Map retrieval source names to backend query types
_SOURCE_TO_BACKEND: dict[str, str] = {
    "kg_relationships": "hipporag",
    "active_promises": "kg",
    "world_state": "kg",
    "episodic_recent": "kg",
    "outline_position": "raptor",
    "orient_warnings": "state",
    "style_rules": "kg",
    "craft_cards": "raptor",
    "genre_conventions": "raptor",
    "voice_examples": "vector",
    "dialogue_patterns": "vector",
    "sensory_details": "vector",
    "character_voice_profiles": "vector",
    "recent_prose": "vector",
    "canon_facts": "kg",
    "world_rules": "kg",
    "knowledge_boundaries": "kg",
    "world_state_timeline": "kg",
    "location_checks": "kg",
}


# ---------------------------------------------------------------------------
# RetrievalRouter
# ---------------------------------------------------------------------------


class RetrievalRouter:
    """Agentic retrieval router with phase-aware context assembly.

    This is the primary interface consumed by the graph-core orient node:
        ``router.query(query, phase, access_tier) -> RetrievalResult``

    Parameters
    ----------
    kg
        KnowledgeGraph instance.
    vector_store
        LanceDB VectorStore instance.
    raptor_tree
        Built RAPTOR tree (can be None if not yet constructed).
    provider_call
        Async callable for LLM query decomposition.
        ``provider_call(prompt, system, role) -> str``
    embed_fn
        Callable that converts text to embedding vector.
        ``embed_fn(text) -> numpy array``
    """

    def __init__(
        self,
        kg: KnowledgeGraph,
        vector_store: VectorStore | None = None,
        raptor_tree: RaptorTree | None = None,
        provider_call: Callable | None = None,
        embed_fn: Callable | None = None,
    ) -> None:
        self._kg = kg
        self._hipporag = HippoRAG(kg)
        self._vector_store = vector_store
        self._raptor_tree = raptor_tree
        self._provider_call = provider_call
        self._embed_fn = embed_fn

    async def query(
        self,
        query: str,
        phase: str,
        access_tier: int = 0,
        pov_character: str | None = None,
        chapter_number: int | None = None,
        token_budget: int = 4000,
    ) -> RetrievalResult:
        """Route a query to the appropriate retrieval backends.

        Parameters
        ----------
        query
            The natural-language query.
        phase
            Current graph phase: orient|plan|draft|evaluate.
        access_tier
            Maximum access tier for epistemic filtering.
        pov_character
            POV character for epistemic filtering.
        chapter_number
            Current chapter for temporal filtering.
        token_budget
            Maximum tokens for the assembled context.

        Returns
        -------
        RetrievalResult
            Merged results from all relevant backends.
        """
        # Decompose query into sub-queries
        sub_queries = await self._decompose(query, phase)

        # Route each sub-query based on phase config
        result = RetrievalResult()

        for sq in sub_queries:
            if sq.query_type == QueryType.ENTITY_RELATIONSHIP:
                if not should_use_backend(phase, "kg_relationships"):
                    continue
                self._route_to_hipporag(
                    sq, result, chapter_number, access_tier, pov_character
                )
                result.sources.append("hipporag")

            elif sq.query_type == QueryType.THEMATIC_GLOBAL:
                if not should_use_backend(phase, "outline_position"):
                    continue
                self._route_to_raptor(sq, result)
                result.sources.append("raptor")

            elif sq.query_type == QueryType.TONE_SIMILARITY:
                if not should_use_backend(phase, "voice_examples"):
                    continue
                self._route_to_vector(sq, result)
                result.sources.append("vector")

        # Cluster similar results to reduce redundancy
        result = self._cluster_results(result)

        # Estimate token count
        result.token_count = self._estimate_tokens(result)

        return result

    async def _decompose(self, query: str, phase: str) -> list[SubQuery]:
        """Decompose a query into sub-queries using LLM or fallback."""
        if self._provider_call is not None:
            prompt = DECOMPOSITION_PROMPT.format(query=query, phase=phase)
            try:
                raw = await self._provider_call(
                    prompt, DECOMPOSITION_SYSTEM, "extract"
                )
                return _parse_decomposition(raw)
            except Exception:
                pass
        return _simple_decompose(query)

    def _route_to_hipporag(
        self,
        sq: SubQuery,
        result: RetrievalResult,
        chapter_number: int | None,
        access_tier: int,
        pov_character: str | None,
    ) -> None:
        """Route an entity/relationship query to HippoRAG."""
        hippo_result = self._hipporag.query(
            entity_mentions=sq.entity_hints if sq.entity_hints else [sq.text],
            chapter_number=chapter_number,
            access_tier=access_tier,
            pov_character=pov_character,
        )
        result.facts.extend(hippo_result.get("related_facts", []))
        result.relationships.extend(hippo_result.get("related_edges", []))

    def _route_to_raptor(self, sq: SubQuery, result: RetrievalResult) -> None:
        """Route a thematic/global query to RAPTOR."""
        if self._raptor_tree is None:
            return
        if self._embed_fn is None:
            # Can't query without embeddings -- return top-level summaries
            result.community_summaries.extend(
                self._raptor_tree.query_top_level()
            )
            return

        query_emb = self._embed_fn(sq.text)
        summaries = query_raptor_tree(
            self._raptor_tree, query_emb, top_k=3
        )
        result.community_summaries.extend(summaries)

    def _route_to_vector(self, sq: SubQuery, result: RetrievalResult) -> None:
        """Route a tone/similarity query to LanceDB vectors."""
        if self._vector_store is None or self._embed_fn is None:
            return

        query_emb = self._embed_fn(sq.text)
        if isinstance(query_emb, np.ndarray):
            query_emb = query_emb.tolist()

        matches = self._vector_store.search(query_emb, limit=5)
        for match in matches:
            result.prose_chunks.append(match.get("text", ""))

    def _cluster_results(self, result: RetrievalResult) -> RetrievalResult:
        """Cluster semantically similar retrieval results.

        Groups facts and prose chunks that are near-duplicates, keeping
        the highest-importance representative from each cluster.  Uses
        embedding cosine similarity when an embed_fn is available,
        otherwise falls back to text overlap ratio.
        """
        if len(result.facts) > 1:
            result.facts = _cluster_facts(result.facts, self._embed_fn)
        if len(result.prose_chunks) > 1:
            result.prose_chunks = _cluster_texts(
                result.prose_chunks, self._embed_fn
            )
        if len(result.community_summaries) > 1:
            result.community_summaries = _cluster_texts(
                result.community_summaries, self._embed_fn
            )
        return result

    def _estimate_tokens(self, result: RetrievalResult) -> int:
        """Rough token count estimate (4 chars per token)."""
        total_chars = 0
        for f in result.facts:
            total_chars += len(f.text)
        for r in result.relationships:
            total_chars += 50  # Approximate per relationship
        for chunk in result.prose_chunks:
            total_chars += len(chunk)
        for summary in result.community_summaries:
            total_chars += len(summary)
        return total_chars // 4


# ---------------------------------------------------------------------------
# Semantic result clustering
# ---------------------------------------------------------------------------

# Cosine similarity threshold for embedding-based clustering.
_EMBED_SIMILARITY_THRESHOLD = 0.85

# Jaccard overlap threshold for text-based fallback clustering.
# Lower than embedding threshold because Jaccard is stricter on prose.
_TEXT_SIMILARITY_THRESHOLD = 0.70


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _text_overlap(a: str, b: str) -> float:
    """Word-level Jaccard overlap as a fallback similarity measure."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _greedy_cluster(
    texts: list[str],
    embed_fn: Callable | None,
    threshold: float | None = None,
) -> list[list[int]]:
    """Greedy single-pass clustering by pairwise similarity.

    Returns a list of clusters, each containing indices into *texts*.
    The first item in each cluster is the representative.

    When *threshold* is None, the threshold is chosen automatically:
    ``_EMBED_SIMILARITY_THRESHOLD`` when embeddings are available,
    ``_TEXT_SIMILARITY_THRESHOLD`` for text-overlap fallback.
    """
    n = len(texts)
    if n <= 1:
        return [[i] for i in range(n)]

    # Build similarity function.
    # Safety valve: skip embedding calls for large result sets to avoid
    # O(n) sequential API round-trips.  Text-overlap fallback is adequate
    # for dedup at this scale.
    _EMBED_CAP = 100
    embeddings: list[np.ndarray] | None = None
    if embed_fn is not None and n <= _EMBED_CAP:
        try:
            embeddings = [np.asarray(embed_fn(t)) for t in texts]
        except Exception:
            embeddings = None

    if threshold is None:
        threshold = (
            _EMBED_SIMILARITY_THRESHOLD if embeddings is not None
            else _TEXT_SIMILARITY_THRESHOLD
        )

    def similarity(i: int, j: int) -> float:
        if embeddings is not None:
            return _cosine_similarity(embeddings[i], embeddings[j])
        return _text_overlap(texts[i], texts[j])

    assigned = [False] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if similarity(i, j) >= threshold:
                cluster.append(j)
                assigned[j] = True
        clusters.append(cluster)

    return clusters


def _cluster_facts(
    facts: list[FactWithContext],
    embed_fn: Callable | None,
) -> list[FactWithContext]:
    """Cluster near-duplicate facts, keeping the highest-importance one."""
    if len(facts) <= 1:
        return facts

    texts = [f.text for f in facts]
    clusters = _greedy_cluster(texts, embed_fn)

    result: list[FactWithContext] = []
    for cluster in clusters:
        # Pick the fact with highest importance as representative
        best_idx = max(cluster, key=lambda i: facts[i].importance)
        result.append(facts[best_idx])
    return result


def _cluster_texts(
    texts: list[str],
    embed_fn: Callable | None,
) -> list[str]:
    """Cluster near-duplicate text strings, keeping the longest representative."""
    if len(texts) <= 1:
        return texts

    clusters = _greedy_cluster(texts, embed_fn)

    result: list[str] = []
    for cluster in clusters:
        # Pick the longest text as representative
        best_idx = max(cluster, key=lambda i: len(texts[i]))
        result.append(texts[best_idx])
    return result
