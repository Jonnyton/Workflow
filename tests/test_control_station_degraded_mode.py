"""Tests for control_station degraded-mode directive (task #13).

Pattern-response to two live fabrication-on-tool-failure instances
within 24 hours:

- Devin Session 2 §6 (2026-04-18): chatbot fabricated tier-2 routing
  claims when `get_status` was absent.
- P0 uptime canary probe (2026-04-19): chatbot fabricated a 6-node
  workflow JSON + session history when MCP returned Session terminated.

Refs:
- `docs/audits/user-chat-intelligence/2026-04-19-devin-session-2.md` §6
- `docs/audits/user-chat-intelligence/2026-04-19-p0-uptime-canary-probe.md` §2.2

The directive itself lives in `workflow.universe_server` at the
`control_station` prompt. These tests catch silent removal of the
directive or accidental regression of its key phrases.
"""

from __future__ import annotations

import re

from workflow.universe_server import _CONTROL_STATION_PROMPT, control_station


def _prompt_text() -> str:
    """Canonical: prompt body as the chatbot receives it."""
    return control_station()


def test_prompt_body_matches_module_constant():
    """Sanity — the @mcp.prompt function must return the module constant."""
    assert _prompt_text() == _CONTROL_STATION_PROMPT


# ---- directive presence ---------------------------------------------------


def test_degraded_mode_directive_is_present():
    """The degraded-mode hard rule must exist as a numbered rule."""
    body = _prompt_text()
    # Hard rule 10 is the degraded-mode directive per task #13 landing.
    assert re.search(
        r"^\s*10\.\s*Degraded-mode",
        body,
        re.MULTILINE,
    ), "Hard rule 10 (degraded-mode) missing from control_station prompt"


def test_degraded_mode_directive_lives_in_hard_rules_block():
    """Directive must be inside the `## Hard Rules` section, not elsewhere."""
    body = _prompt_text()
    hard_rules_start = body.find("## Hard Rules")
    tool_catalog_start = body.find("## Tool Catalog")
    assert hard_rules_start != -1, "Hard Rules heading missing"
    assert tool_catalog_start != -1, "Tool Catalog heading missing"
    assert hard_rules_start < tool_catalog_start, "section order regressed"

    hard_rules_block = body[hard_rules_start:tool_catalog_start]
    assert "Degraded-mode" in hard_rules_block, (
        "degraded-mode directive escaped the Hard Rules block"
    )


# ---- trigger-phrase coverage ---------------------------------------------


def test_directive_names_session_terminated_trigger():
    """The directive MUST name 'Session terminated' — the P0 evidence string."""
    body = _prompt_text()
    assert "Session terminated" in body, (
        "'Session terminated' trigger phrase missing — the exact symptom "
        "the P0 probe reported must be recognized by the chatbot"
    )


def test_directive_names_multiple_failure_triggers():
    """Multiple failure-signature phrases — Session terminated is only one shape."""
    body = _prompt_text()
    # These cover the likely shapes of live tool failure the chatbot will see.
    required_triggers = ["Session terminated", "tool error", "not reachable"]
    missing = [t for t in required_triggers if t not in body]
    assert not missing, (
        f"directive trigger phrases missing: {missing}. "
        f"Each shape the chatbot might see must be named so the rule fires."
    )


def test_directive_covers_all_four_coarse_tools():
    """Directive must name the four coarse tools whose failure triggers the rule."""
    body = _prompt_text()
    # Find the rule-10 block for targeted assertion.
    rule_10_match = re.search(
        r"10\.\s*Degraded-mode.*?(?=^\s*\d+\.|^## )",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert rule_10_match, "could not locate rule 10 block"
    rule_10 = rule_10_match.group(0)
    for tool in ["universe", "extensions", "goals", "wiki"]:
        assert f"`{tool}`" in rule_10, (
            f"rule 10 doesn't name the `{tool}` tool — partial coverage risks "
            f"the chatbot applying the rule to some tools but not others"
        )


# ---- forbidden-action coverage -------------------------------------------


def test_directive_forbids_fabrication():
    """'fabricate' is the load-bearing verb — silent removal breaks the rule."""
    body = _prompt_text()
    assert "fabricate" in body.lower(), (
        "'fabricate' forbidden-action verb missing from prompt — "
        "the rule's teeth depend on this word"
    )


def test_directive_forbids_session_history_fabrication():
    """Rule must explicitly forbid claiming prior-turn session history.

    This is the Devin-S2 + P0-probe sub-finding: chatbot claimed
    'pick up from the X node you began earlier' with no prior evidence.
    """
    body = _prompt_text()
    # Either "session history" or the specific "pick up from" pattern must appear.
    assert (
        "session history" in body.lower()
        or "pick up from" in body.lower()
    ), (
        "rule must explicitly forbid session-history fabrication — "
        "the Devin-S2 + P0-probe cross-session pattern"
    )


def test_directive_requires_plain_failure_disclosure():
    """Rule must tell the chatbot to TELL THE USER the connector is degraded."""
    body = _prompt_text()
    rule_10_match = re.search(
        r"10\.\s*Degraded-mode.*?(?=^\s*\d+\.|^## )",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert rule_10_match
    rule_10 = rule_10_match.group(0).lower()
    # The honest-disclosure clause. Accept several natural phrasings.
    assert any(
        phrase in rule_10
        for phrase in ["tell the user", "degraded", "connector isn't responding", "can't reach"]
    ), "rule must instruct the chatbot to disclose the failure to the user"


# ---- rule-interaction -----------------------------------------------------


def test_directive_names_rules_it_overrides():
    """Rule 10 must explicitly override rule 2 (use tools) + rule 7 (assume).

    Without explicit override language, chatbot may resolve the rules
    in the wrong order and keep trying to fabricate through failure.
    """
    body = _prompt_text()
    rule_10_match = re.search(
        r"10\.\s*Degraded-mode.*?(?=^\s*\d+\.|^## )",
        body,
        re.MULTILINE | re.DOTALL,
    )
    assert rule_10_match
    rule_10 = rule_10_match.group(0)
    # Rule 2 is "Always use tools"; rule 7 is "Assume Workflow on plausible intent."
    # Rule 10 must call those out by number so the precedence is unambiguous.
    assert "rule 2" in rule_10.lower(), "rule 10 must override rule 2 explicitly"
    assert "rule 7" in rule_10.lower(), "rule 10 must override rule 7 explicitly"
