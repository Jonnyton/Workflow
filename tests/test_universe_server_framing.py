"""Tests for the workflow-builder framing + no-simulation rule.

Tasks #27, #28, #34 are text-only fixes to Universe Server prompts and
tool descriptions. The risk isn't that the text is wrong today — it's
that someone later edits the copy back to fiction-only framing or drops
the anti-simulation clause without realizing those lines are load-bearing.

These tests pin the behavioral claims. Copy can be rewritten freely as
long as the guarded intents stay present.
"""

from __future__ import annotations

import asyncio

from workflow.universe_server import mcp


def _list_tools():
    return asyncio.run(mcp.list_tools(run_middleware=False))


def _list_prompts():
    return asyncio.run(mcp.list_prompts(run_middleware=False))


def test_server_instructions_lead_with_workflow_builder_not_fiction() -> None:
    """#28: instructions must frame the server as a general workflow
    platform, not "primarily for fiction". Fantasy is a benchmark.
    """
    text = (mcp.instructions or "").lower()
    # Workflow builder framing must appear — and appear before the word
    # "fiction" (which is allowed as an example, not the lead).
    assert "workflow builder" in text
    # At least one non-fiction example domain must appear so the bot
    # knows recipe trackers / research / planners are in scope.
    example_domains = [
        "research", "recipe", "screenplay", "journalism",
        "wedding", "news summariz",
    ]
    assert any(d in text for d in example_domains), (
        "server instructions should name at least one non-fiction example"
    )
    # "NOT the exclusive use case" or similar negation of fiction-only
    # framing. We look for either the explicit clause or "not just fiction"
    # style wording.
    assert (
        "not the exclusive" in text
        or "not just fiction" in text
        or "benchmark" in text
    ), "instructions must negate fiction-only framing"


def test_server_instructions_include_no_simulation_rule() -> None:
    """#34: runtime rule must be present in the server's own instructions
    so any MCP client gets it even without invoking the control_station
    prompt.
    """
    text = mcp.instructions or ""
    lower = text.lower()
    # Core clause: must not simulate / must use the execute action.
    assert "no simulation" in lower or "must use the provided execute" in lower
    # Hard "do not" language against the fallback patterns user-sim saw.
    # Normalize hyphens so "do not web-search" / "do not web search" both match.
    normalized = lower.replace("-", " ")
    assert "do not web search" in normalized
    assert "stop" in lower, "instructions should tell the bot to STOP when runner is missing"


def test_extensions_tool_description_mentions_no_simulation() -> None:
    """#34: the extensions tool is the run surface; its own description
    must carry the rule so it's visible when the bot inspects the tool.
    """
    tool = next(t for t in _list_tools() if t.name == "extensions")
    text = (tool.description or "").lower()
    assert "no simulation" in text or "must use the `run_branch`" in text
    assert "stop" in text


def test_wiki_tool_description_is_not_a_catchall() -> None:
    """#27: wiki must explicitly refuse the "save anything" role when a
    user wants workflow structure, state, or task tracking. Route them
    to `extensions` instead.
    """
    tool = next(t for t in _list_tools() if t.name == "wiki")
    text = tool.description or ""
    lower = text.lower()
    # Scope negation — wiki is NOT for workflow structure / state.
    assert (
        "not for workflow" in lower
        or "save anything" in lower
    )
    # Explicit routing guidance to `extensions`.
    assert "extensions" in lower
    # Name at least one misuse pattern we want the bot to recognize.
    assert "build / design / create a workflow" in lower or "build a workflow" in lower


def test_universe_tool_description_frames_workflows_broadly() -> None:
    """#28: universe tool's docstring must not read like a fiction-only
    help page.
    """
    tool = next(t for t in _list_tools() if t.name == "universe")
    text = (tool.description or "").lower()
    # Multiple domain examples must appear.
    example_domains = [
        "research", "recipe", "screenplay", "news summar",
        "journalism", "wedding",
    ]
    hits = [d for d in example_domains if d in text]
    assert len(hits) >= 2, (
        f"universe tool description should name multiple workflow domains; "
        f"found: {hits}"
    )
    # Fantasy must be positioned as a benchmark / example, not the lead.
    assert "benchmark" in text or "not the exclusive" in text or "fantasy authoring is one" in text


def test_control_station_prompt_carries_the_rules() -> None:
    """#27/#28/#34: the prompt a control-station client loads must carry
    the workflow-builder framing, the routing guidance, and the
    no-simulation rule. Copy rewording is fine — the intents must stay.
    """
    from workflow.universe_server import _CONTROL_STATION_PROMPT
    text = _CONTROL_STATION_PROMPT.lower()
    # Broad framing.
    assert "workflow builder" in text or "workflow" in text
    assert "benchmark" in text or "not the exclusive" in text or "fully general" in text
    # Routing: extensions for workflow design, wiki for knowledge only.
    assert "extensions" in text
    assert "wiki" in text
    # No-simulation clause.
    assert "no simulation" in text or "fake output" in text
    assert "stop" in text


def test_extension_guide_prompt_carries_no_simulation() -> None:
    """#34: the extension guide is where node authors learn the contract;
    it must include the runtime rule so they don't build nodes that rely
    on the bot faking execution.
    """
    from workflow.universe_server import _EXTENSION_GUIDE_PROMPT
    text = _EXTENSION_GUIDE_PROMPT.lower()
    assert "no simulation" in text or "fake output" in text
    assert "run_branch" in text or "execute action" in text


def test_list_branches_description_prompts_listing_first() -> None:
    """#42: when a user asks about existing workflows from a past chat,
    the bot must call `list_branches` first. The description must make
    that obvious — not leave the bot exploring blindly for multiple
    turns before landing on list.
    """
    tool = next(t for t in _list_tools() if t.name == "extensions")
    text = (tool.description or "").lower()

    # "USE THIS FIRST" guidance for list_branches.
    assert "use this first" in text, (
        "list_branches description must signal when to call it first"
    )
    # Cue phrases users actually say. We require at least three to keep
    # the hint multi-dimensional — a one-cue change from lead mustn't
    # slip past.
    user_phrases = [
        "what do i have",
        "pull up my workflow",
        "show me my workflows",
        "what branches exist",
        "did i already build",
        "previous chat",
    ]
    hits = [p for p in user_phrases if p in text]
    assert len(hits) >= 3, (
        f"list_branches should enumerate user phrases that mean 'list "
        f"my existing workflows'; found only: {hits}"
    )


def test_describe_branch_description_targets_phone_legibility() -> None:
    """#42: describe_branch is the conversational rendering; its
    description must flag phone-legibility so the bot picks it over
    get_branch for chat replies.
    """
    tool = next(t for t in _list_tools() if t.name == "extensions")
    text = (tool.description or "").lower()
    assert "use this when" in text
    assert "plain-english" in text or "phone" in text


def test_get_branch_description_targets_detail_queries() -> None:
    """#42: get_branch is the full-JSON path; the description must tell
    the bot to pick it only when the full topology is actually needed,
    not as the default path over describe_branch.
    """
    tool = next(t for t in _list_tools() if t.name == "extensions")
    text = (tool.description or "").lower()
    assert "full topology" in text or "full branchdefinition" in text
    assert "prefer `describe_branch`" in text or "prefer describe_branch" in text


def test_extensions_register_requires_affirmative_consent() -> None:
    """#46: `register` must refuse on query-intent phrases. Writing state
    when the user only asked "what do i have" is the worst UX failure
    mode — pin the affirmative-consent language in the description.
    """
    tool = next(t for t in _list_tools() if t.name == "extensions")
    text = (tool.description or "").lower()
    # Locate the register action block.
    assert "register —" in text or "register -" in text
    # Core rule text must be present somewhere in the description.
    assert "affirmative consent" in text
    assert "explicitly" in text
    # At least one query-intent cue the bot must NOT treat as register.
    query_cues = [
        "what do i have", "show me", "list my", "find my", "pull up",
    ]
    hits = [c for c in query_cues if c in text]
    assert len(hits) >= 3, (
        f"register description must enumerate query-intent phrases that "
        f"should NOT trigger a write; found: {hits}"
    )
    # Explicit "do not write" / "ask" fallback must appear.
    assert "do not write state" in text or "ask them" in text or "ask the user" in text


def test_build_branch_requires_affirmative_consent() -> None:
    """#46: `build_branch` is the composite create path — same rule as
    `register`. Query-intent phrases route to `list_branches`, not build.
    """
    tool = next(t for t in _list_tools() if t.name == "extensions")
    text = (tool.description or "").lower()
    assert "build_branch" in text
    assert "affirmative consent" in text
    # Must cite list_branches as the query-intent alternative.
    assert "list_branches" in text
    # "Never build speculatively" or equivalent refusal language.
    assert "never build speculatively" in text or "do not write state" in text


def test_universe_tool_docstring_carries_cross_universe_rule() -> None:
    """#15: the universe tool docstring must reinforce the cross-universe
    transfer rule. Not just the server-level instructions; the per-tool
    docstring is what a client reads when inspecting the tool directly.
    """
    tool = next(t for t in _list_tools() if t.name == "universe")
    text = (tool.description or "").lower()
    # Core rule text must be present.
    assert "never transfer" in text or "do not transfer" in text
    # Mention of the Universe: <id> header shape so the bot knows the
    # contract, not just the prohibition.
    assert "universe:" in text or "universe_id" in text
    # Re-grounding guidance.
    assert "inspect" in text and "re-ground" in text


def test_control_station_prompt_has_cross_universe_section() -> None:
    """#15: control_station must teach the bot NOT to transfer facts
    across universes. Named section so a future reword can't silently
    drop the whole block.
    """
    from workflow.universe_server import _CONTROL_STATION_PROMPT
    text = _CONTROL_STATION_PROMPT.lower()
    # Named section header.
    assert "cross-universe" in text
    # The load-bearing header shape the bot must recognize.
    assert "universe: <id>" in text or "universe:" in text
    # Transfer prohibition.
    assert "never carry facts" in text or "never transfer" in text
    # Ground-truth guidance — tool output over chat memory.
    assert "ground truth" in text


def test_control_station_prompt_has_intent_disambiguation() -> None:
    """#46: control_station must teach the bot to classify intent BEFORE
    picking a tool. Query / Build / Run must each have a clear routing
    rule, and ambiguity must route to ASK, not write.
    """
    from workflow.universe_server import _CONTROL_STATION_PROMPT
    text = _CONTROL_STATION_PROMPT.lower()
    assert "intent disambiguation" in text
    # Each intent class must be present with at least one cue phrase.
    assert "query" in text and "list_branches" in text
    assert "build" in text and ("build_branch" in text or "register" in text)
    assert "run" in text and "run_branch" in text
    # Ambiguity → ASK, not write.
    assert "ask" in text
    assert "never write state on ambiguous intent" in text or "do not write state" in text
    # At least three query-intent cue phrases so a single reword can't
    # erase the routing contract.
    query_cues = ["what do i have", "show me", "list", "find my", "pull up"]
    hits = [c for c in query_cues if c in text]
    assert len(hits) >= 3, (
        f"control_station must enumerate query-intent cues; found: {hits}"
    )
