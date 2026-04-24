"""Provider bridge for graph nodes.

Routes all LLM calls through the real ``ProviderRouter`` using its
synchronous ``call_sync`` method.  Falls back to deterministic mock
output when ``_FORCE_MOCK`` is True (tests) or when all providers are
exhausted.

This module lives in ``nodes/`` (graph-core's directory) to respect
file ownership boundaries.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Set to True to skip real provider calls and use mock responses.
# Tests should set this before importing nodes.
_FORCE_MOCK = False

# ---------------------------------------------------------------------------
# Import the real provider router
# ---------------------------------------------------------------------------

_real_router = None

# Tracks which provider was used for the most recent call.
# Used by reflect/worldbuild to enforce model quality tiers.
last_provider: str = ""

try:
    from workflow.providers.router import ProviderRouter as _RealRouter

    _real_router = _RealRouter()

    # Register available providers so the router works without the daemon.
    # The daemon's DaemonController.start() overwrites _real_router with its
    # own fully-configured instance, so these registrations are only the
    # fallback for standalone / script usage.

    try:
        from workflow.providers.claude_provider import ClaudeProvider
        _real_router.register(ClaudeProvider())
        logger.info("Registered ClaudeProvider")
    except Exception:
        logger.debug("ClaudeProvider not available")

    try:
        from workflow.providers.codex_provider import CodexProvider
        _real_router.register(CodexProvider())
        logger.info("Registered CodexProvider")
    except Exception:
        logger.debug("CodexProvider not available")

    try:
        from workflow.providers.ollama_provider import OllamaProvider
        _real_router.register(OllamaProvider())
        logger.info("Registered OllamaProvider")
    except Exception:
        logger.debug("OllamaProvider not available")

    try:
        from workflow.providers.gemini_provider import GeminiProvider
        _real_router.register(GeminiProvider())
        logger.info("Registered GeminiProvider")
    except Exception:
        logger.debug("GeminiProvider not available")

    try:
        from workflow.providers.groq_provider import GroqProvider
        _real_router.register(GroqProvider())
        logger.info("Registered GroqProvider")
    except Exception:
        logger.debug("GroqProvider not available")

    try:
        from workflow.providers.grok_provider import GrokProvider
        _real_router.register(GrokProvider())
        logger.info("Registered GrokProvider")
    except Exception:
        logger.debug("GrokProvider not available")

    logger.info(
        "ProviderRouter ready with providers: %s",
        _real_router.available_providers,
    )
except ImportError:
    logger.info("Real ProviderRouter not available; using stub provider")


# ---------------------------------------------------------------------------
# Mock provider responses
# ---------------------------------------------------------------------------


def _format_retrieved_context(retrieved: dict[str, Any]) -> str:
    """Format retrieval router results into prompt sections.

    Extracts facts, relationships, prose chunks, and community summaries
    from the RetrievalRouter's output. Returns empty string if no
    useful content.
    """
    if not retrieved:
        return ""

    parts: list[str] = []

    # Facts from KG
    facts = retrieved.get("facts", [])
    if facts:
        fact_lines = []
        for f in facts[:15]:
            if isinstance(f, dict):
                text = f.get("text", f.get("content", ""))
                if text:
                    fact_lines.append(f"- {text}")
        if fact_lines:
            parts.append("## Known Facts\n\n" + "\n".join(fact_lines))

    # Relationships from KG
    rels = retrieved.get("relationships", [])
    if rels:
        rel_lines = []
        for r in rels[:10]:
            if isinstance(r, dict):
                src = r.get("source", "")
                tgt = r.get("target", "")
                rtype = r.get("relation_type", "related to")
                if src and tgt:
                    rel_lines.append(f"- {src} {rtype} {tgt}")
        if rel_lines:
            parts.append("## Relationships\n\n" + "\n".join(rel_lines))

    # Prose chunks from vector search
    chunks = retrieved.get("prose_chunks", [])
    if chunks:
        chunk_texts = []
        for c in chunks[:3]:
            if isinstance(c, dict):
                text = c.get("text", "")
                if text:
                    chunk_texts.append(text[:500])
            elif isinstance(c, str):
                chunk_texts.append(c[:500])
        if chunk_texts:
            parts.append(
                "## Relevant Passages\n\n"
                + "\n\n---\n\n".join(chunk_texts)
            )

    # Community summaries from RAPTOR
    summaries = retrieved.get("community_summaries", [])
    if summaries:
        summary_lines = [s[:300] for s in summaries[:3] if isinstance(s, str)]
        if summary_lines:
            parts.append(
                "## World Summaries\n\n" + "\n\n".join(summary_lines)
            )

    if not parts:
        return ""

    return "# Retrieved Context\n\n" + "\n\n".join(parts) + "\n\n"


def _format_memory_context(memory_ctx: dict[str, Any]) -> str:
    """Format memory context fields into prompt sections.

    Extracts useful fields (characters, facts, style rules, recent
    summaries) and formats them as markdown for prompt injection.
    Returns empty string if no useful content is available.
    """
    if not memory_ctx:
        return ""

    parts: list[str] = []

    # Active characters
    chars = memory_ctx.get("active_characters", {})
    if chars and isinstance(chars, dict):
        char_list = []
        for name, info in list(chars.items())[:10]:
            if isinstance(info, dict):
                desc = info.get("description", info.get("role", ""))
                char_list.append(f"- **{name}**: {desc}" if desc else f"- **{name}**")
            elif isinstance(info, str):
                char_list.append(f"- **{name}**: {info}")
        if char_list:
            parts.append("## Characters\n\n" + "\n".join(char_list))

    # Recent scene summaries
    summaries = memory_ctx.get("recent_summaries", [])
    if summaries:
        summary_lines = []
        for s in summaries[:5]:
            if isinstance(s, dict):
                ch = s.get("ch", "?")
                sc = s.get("sc", "?")
                text = s.get("summary", "")
                if text:
                    summary_lines.append(f"- Ch{ch} Sc{sc}: {text}")
        if summary_lines:
            parts.append("## Recent Events\n\n" + "\n".join(summary_lines))

    # Key facts
    facts = memory_ctx.get("facts", [])
    if facts:
        fact_lines = []
        for f in facts[:10]:
            if isinstance(f, dict):
                text = f.get("content", f.get("text", f.get("fact", "")))
                if text:
                    fact_lines.append(f"- {text}")
            elif isinstance(f, str):
                fact_lines.append(f"- {f}")
        if fact_lines:
            parts.append("## Key Facts\n\n" + "\n".join(fact_lines))

    # Style rules
    rules = memory_ctx.get("style_rules", [])
    if rules:
        rule_lines = []
        for r in rules[:5]:
            if isinstance(r, dict):
                text = r.get("rule", r.get("text", ""))
                if text:
                    rule_lines.append(f"- {text}")
            elif isinstance(r, str):
                rule_lines.append(f"- {r}")
        if rule_lines:
            parts.append("## Style Notes\n\n" + "\n".join(rule_lines))

    if not parts:
        return ""

    return "# Story Memory\n\n" + "\n\n".join(parts) + "\n\n"


def _mock_plan_response(orient_result: dict[str, Any]) -> str:
    """Generate a deterministic mock plan response.

    Returns a JSON string with beat alternatives.
    """
    warnings = orient_result.get("overdue_promises", [])

    warn_ids = (
        [w.get("id", "") for w in warnings[:1]] if warnings else []
    )
    beats = [
        {
            "beat_number": 1,
            "description": (
                "Opening -- establish setting and POV character."
            ),
            "tension": 0.3,
            "addresses_warnings": [],
        },
        {
            "beat_number": 2,
            "description": (
                "Rising -- character encounters a complication."
            ),
            "tension": 0.6,
            "addresses_warnings": warn_ids,
        },
        {
            "beat_number": 3,
            "description": (
                "Climax -- scene turning point, character acts."
            ),
            "tension": 0.9,
            "addresses_warnings": [],
        },
        {
            "beat_number": 4,
            "description": (
                "Resolution -- consequences; transition to next."
            ),
            "tension": 0.5,
            "addresses_warnings": [],
        },
    ]

    alternatives = [
        {
            "alternative_id": 0,
            "beats": beats,
            "done_when": "The character has faced the scene conflict and made a choice.",
            "promise_resolutions": [],
            "estimated_word_count": 1200,
        },
    ]

    return json.dumps({"alternatives": alternatives})


def _mock_draft_response(plan_output: dict[str, Any]) -> str:
    """Generate deterministic mock prose from a beat sheet."""
    beats = plan_output.get("beats", [])

    paragraphs = []
    for beat in beats:
        desc = beat.get("description", "A scene unfolds.")
        paragraphs.append(
            f"The moment stretched taut as wire. {desc} "
            f"Ryn felt the weight of every choice she had ever made pressing "
            f"down on her shoulders. The Northern Gate loomed ahead, ancient "
            f"stones rising from the mist like the bones of a forgotten giant. "
            f"She drew a slow breath of cold mountain air and pressed forward."
        )

    prose = "\n\n".join(paragraphs)
    return prose


def _mock_extraction_response(prose: str) -> str:
    """Generate deterministic mock fact extraction response."""
    facts = []

    # Extract simple character names
    import re

    names = set(re.findall(r"\b([A-Z][a-z]{2,})\b", prose))
    # Filter common non-name words
    stopwords = {"The", "She", "Her", "His", "They", "This", "That", "But", "And", "Not"}
    names -= stopwords

    for i, name in enumerate(sorted(names)[:5]):
        facts.append({
            "text": f"{name} is present in the scene.",
            "source_type": "narrator_claim",
            "language_type": "literal",
            "narrative_function": "world_fact",
            "importance": 0.4,
            "confidence": 0.6,
            "access_tier": 0,
        })

    return json.dumps(facts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _call_router_with_retry(role: str, prompt: str, system: str) -> str:
    """Call the real router with tenacity retry on transient exhaustion.

    Retries up to 3 times with exponential backoff (2s, 4s, 8s) when
    all providers are temporarily exhausted. This handles the common case
    where rate-limit cooldowns expire between attempts.
    """
    from workflow.exceptions import AllProvidersExhaustedError

    @retry(
        retry=retry_if_exception_type(AllProvidersExhaustedError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    def _attempt() -> str:
        global last_provider
        result = _real_router.call_sync(role, prompt, system)
        last_provider = result.provider
        return result.text

    return _attempt()


def call_provider(
    prompt: str,
    system: str = "",
    *,
    role: str = "writer",
    fallback_response: str | None = None,
) -> str:
    """Call an LLM provider with automatic fallback.

    Uses the real ProviderRouter's ``call_sync`` method which runs the
    async fallback chain in a dedicated thread.  Falls back to mock
    output only when all providers are exhausted.

    On transient exhaustion (all providers in cooldown), retries up to 3
    times with exponential backoff before giving up.

    Parameters
    ----------
    prompt : str
        The user prompt.
    system : str
        System prompt.
    role : str
        The role for routing (writer, judge, extract).
    fallback_response : str or None
        If all providers fail, return this string.  If None, returns
        a generic placeholder.

    Returns
    -------
    str
        The provider's response text.
    """
    if _FORCE_MOCK:
        if fallback_response is not None:
            return fallback_response
        return "[Mock response -- _FORCE_MOCK is True]"

    # Use the real router's synchronous entry point with retry
    if _real_router is not None:
        try:
            return _call_router_with_retry(role, prompt, system)
        except Exception as e:
            logger.error(
                "All providers exhausted for role=%s after retries: %s", role, e,
            )

    # Fallback: only use mock content if an explicit fallback was provided.
    # In production (no _FORCE_MOCK), callers should pass fallback_response=None
    # so that provider exhaustion surfaces as an empty string, not fake prose.
    if fallback_response is not None:
        logger.warning(
            "Using fallback response for role=%s (%d chars)",
            role, len(fallback_response),
        )
        return fallback_response
    return ""


def call_for_plan(
    orient_result: dict[str, Any],
    *,
    writer_context: str = "",
) -> str:
    """Call provider to generate a scene plan.

    Falls back to deterministic mock if no provider is available.
    """
    system = (
        "You are a fiction planning assistant. Generate a beat sheet for a scene. "
        "Return a JSON object with an 'alternatives' array. Each alternative has: "
        "beats (array of {beat_number, description, tension}), done_when (string), "
        "promise_resolutions (array), estimated_word_count (int). "
        "Generate 3-5 alternative beat sheets."
    )

    warnings_text = ""
    overdue = orient_result.get("overdue_promises", [])
    if overdue:
        warnings_text = "\n\nWarnings to address:\n" + "\n".join(
            f"- {p.get('text', str(p))}" for p in overdue
        )

    pacing = orient_result.get("pacing_flags", [])
    if pacing:
        warnings_text += "\n\nPacing notes:\n" + "\n".join(
            f"- {f.get('text', str(f))}" for f in pacing
        )

    context_section = writer_context
    if not context_section:
        # Backwards-compatible fallback for direct callers that still pass
        # pre-assembled prompt context through orient_result.
        canon_context = orient_result.get("canon_context", "")
        canon_section = ""
        if canon_context:
            canon_section = f"\n\n# World Context\n\n{canon_context}\n"

        memory_section = _format_memory_context(orient_result.get("memory_context", {}))
        retrieved_section = _format_retrieved_context(orient_result.get("retrieved_context", {}))

        constraints_section = ""
        forcing = orient_result.get("forcing_constraints", [])
        if forcing:
            constraint_lines = "\n".join(f"- {c}" for c in forcing[:10])
            constraints_section = (
                f"\n\n# World Constraints\n\n{constraint_lines}\n"
            )
        context_section = (
            f"{canon_section}"
            f"{retrieved_section}"
            f"{memory_section}"
            f"{constraints_section}"
        )

    prompt = (
        f"Scene context: {orient_result.get('scene_id', 'unknown')}\n"
        f"Arc position: {orient_result.get('arc_position', 'rising_action')}\n"
        f"{context_section}"
        f"{warnings_text}\n\n"
        "Generate 3-5 alternative beat sheets for this scene."
    )

    fallback = _mock_plan_response(orient_result) if _FORCE_MOCK else None
    result = call_provider(
        prompt,
        system,
        role="writer",
        fallback_response=fallback,
    )
    return result


def call_for_draft(
    plan_output: dict[str, Any],
    orient_result: dict[str, Any],
    recent_prose: str = "",
    revision_feedback: dict[str, Any] | None = None,
    *,
    writer_context: str = "",
) -> str:
    """Call provider to generate prose from a beat sheet.

    Falls back to deterministic mock if no provider is available.
    """
    system = (
        "You are a skilled fantasy author. Write vivid, immersive prose for the "
        "following scene beats. Use third-person limited POV, past tense. "
        "Target 800-1500 words. Include sensory details, character interiority, "
        "and natural dialogue where appropriate."
    )

    beats_text = "\n".join(
        f"Beat {b.get('beat_number', i+1)}: {b.get('description', '')}"
        for i, b in enumerate(plan_output.get("beats", []))
    )

    prompt = f"Beat sheet:\n{beats_text}\n\n"

    if plan_output.get("done_when"):
        prompt += f"Scene is complete when: {plan_output['done_when']}\n\n"

    if writer_context:
        prompt += writer_context
        prompt += "Write the scene prose now."
        fallback = _mock_draft_response(plan_output) if _FORCE_MOCK else None
        result = call_provider(
            prompt,
            system,
            role="writer",
            fallback_response=fallback,
        )
        return result

    # Include canon context so prose is grounded in the universe
    canon_context = orient_result.get("canon_context", "")
    if canon_context:
        prompt += f"# World Context\n\n{canon_context}\n\n"

    # Include memory context (voice refs, style rules)
    memory_section = _format_memory_context(orient_result.get("memory_context", {}))
    if memory_section:
        prompt += memory_section

    # Include retrieved context (KG facts, relationships, vector matches)
    retrieved_section = _format_retrieved_context(orient_result.get("retrieved_context", {}))
    if retrieved_section:
        prompt += retrieved_section

    if recent_prose:
        # Include last 2000 chars for continuity (roughly a full scene)
        prompt += f"Previous prose (for continuity):\n...{recent_prose[-2000:]}\n\n"

    if revision_feedback:
        prompt += "REVISION REQUESTED. Previous draft had these issues:\n"

        # Structural issues
        warnings = revision_feedback.get("warnings", [])
        if warnings:
            prompt += "Structural problems:\n"
            for w in warnings[:5]:
                prompt += f"- {w}\n"
            prompt += "\n"

        # Editorial feedback
        editorial = revision_feedback.get("editorial_notes")
        if editorial and isinstance(editorial, dict):
            concerns = editorial.get("concerns", [])
            if concerns:
                prompt += "Editorial concerns:\n"
                for c in concerns:
                    if isinstance(c, dict):
                        label = "ERROR" if c.get("clearly_wrong") else "concern"
                        prompt += f"- [{label}] {c.get('text', '')}"
                        quote = c.get("quoted_passage", "")
                        if quote:
                            prompt += f' — "{quote}"'
                        prompt += "\n"
                prompt += "\n"
            protects = editorial.get("protect", [])
            if protects:
                prompt += "Keep these strengths:\n"
                for p in protects:
                    prompt += f"- {p}\n"
                prompt += "\n"

        # Style observations
        style_obs = revision_feedback.get("style_observations", [])
        if style_obs:
            prompt += "Style feedback:\n"
            for obs in style_obs[:5]:
                if isinstance(obs, dict):
                    dim = obs.get("dimension", "")
                    note = obs.get("observation", "")
                    prompt += f"- {dim}: {note}\n" if dim else f"- {note}\n"
                elif isinstance(obs, str):
                    prompt += f"- {obs}\n"
            prompt += "\n"

        prompt += "Address these issues in your revision.\n\n"

    prompt += "Write the scene prose now."

    fallback = _mock_draft_response(plan_output) if _FORCE_MOCK else None
    result = call_provider(
        prompt,
        system,
        role="writer",
        fallback_response=fallback,
    )
    return result


def call_for_extraction(prose: str, pov_character: str | None = None) -> str:
    """Call provider to extract facts from prose.

    Falls back to deterministic mock if no provider is available.
    """
    from domains.fantasy_daemon.phases.fact_extraction import (
        FACT_EXTRACTION_SYSTEM,
        build_extraction_prompt,
    )

    prompt = build_extraction_prompt(prose, pov_character)

    fallback = _mock_extraction_response(prose) if _FORCE_MOCK else None
    result = call_provider(
        prompt,
        FACT_EXTRACTION_SYSTEM,
        role="extract",
        fallback_response=fallback,
    )
    return result
