"""Tests for `provider_exhaustion` triage class (BUG-023 Lane 4b).

Guards the auto-triage classification + priority ordering between
provider_exhaustion and the pre-existing classes (disk_full, oom, etc.).
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import triage_classify as tc  # noqa: E402


class TestProviderExhaustionRecognition:
    def test_all_providers_exhausted_literal(self):
        diag = (
            "Apr 23 20:45:10 droplet workflow-daemon[123]: "
            "All providers exhausted for role=writer\n"
        )
        result = tc.classify(diag)
        assert result["class"] == tc.TriageClass.PROVIDER_EXHAUSTION
        assert result["auto_repairable"] is True
        assert result["manual_only"] is False

    def test_exception_name_form(self):
        diag = (
            "Traceback (most recent call last):\n"
            "  File \"workflow/providers/router.py\", line 92, in call_sync\n"
            "  raise AllProvidersExhaustedError('all cooling')\n"
        )
        result = tc.classify(diag)
        assert result["class"] == tc.TriageClass.PROVIDER_EXHAUSTION

    def test_score_zero_revert_verdict(self):
        diag = (
            "2026-04-23T20:30:00Z [commit] score 0.00 -- REVERT\n"
            "2026-04-23T20:31:00Z [commit] score 0.00 -- REVERT\n"
        )
        result = tc.classify(diag)
        assert result["class"] == tc.TriageClass.PROVIDER_EXHAUSTION

    def test_draft_failed_pattern(self):
        diag = (
            "2026-04-23T20:30:00Z [worker] Draft: FAILED — provider cooldown\n"
        )
        result = tc.classify(diag)
        assert result["class"] == tc.TriageClass.PROVIDER_EXHAUSTION


class TestProviderExhaustionPriority:
    """Env/tunnel/oom/disk classes beat provider_exhaustion when they
    co-occur — those are root causes and their repairs run first.
    provider_exhaustion is last-resort active-but-broken detection.
    """

    def test_env_unreadable_wins(self):
        diag = (
            "ENV-UNREADABLE: /etc/workflow/env not readable\n"
            "later: Draft: FAILED — cascaded from env issue\n"
        )
        assert (
            tc.classify(diag)["class"] == tc.TriageClass.ENV_UNREADABLE
        )

    def test_tunnel_token_wins(self):
        diag = (
            "cloudflared: Failed to get tunnel: Unauthorized\n"
            "later: All providers exhausted for role=writer\n"
        )
        assert tc.classify(diag)["class"] == tc.TriageClass.TUNNEL_TOKEN

    def test_disk_full_wins_even_with_revert_signature(self):
        """disk_full regex = '9X% /'; revert regex doesn't overlap, but
        disk_full appears earlier in priority order."""
        diag = (
            "/dev/vda1        25G   24G  0.5G  97% /\n"
            "later: score 0.00 -- REVERT\n"
        )
        assert tc.classify(diag)["class"] == tc.TriageClass.DISK_FULL

    def test_oom_wins(self):
        diag = (
            "kernel: Out of memory: Killed process 123 (python)\n"
            "later: Draft: FAILED\n"
        )
        assert tc.classify(diag)["class"] == tc.TriageClass.OOM

    def test_provider_exhaustion_wins_over_unknown(self):
        """When no higher-priority class matches, provider_exhaustion
        still beats the generic-restart `unknown` fallback."""
        diag = "2026-04-23T20:30:00Z [worker] Draft: FAILED\n" * 3
        result = tc.classify(diag)
        assert result["class"] == tc.TriageClass.PROVIDER_EXHAUSTION
        # Not auto-repairable=False (that's tunnel_token's shape) —
        # provider_exhaustion IS auto-repairable via pause+page.
        assert result["auto_repairable"] is True


class TestProviderExhaustionContractShape:
    def test_evidence_excerpt_contains_match(self):
        diag = (
            "some noise\n"
            "2026-04-23T20:30:00Z [provider] All providers exhausted\n"
            "more noise\n"
        )
        result = tc.classify(diag)
        assert "All providers exhausted" in result["evidence"]

    def test_description_names_the_repair(self):
        diag = "All providers exhausted\n"
        result = tc.classify(diag)
        # The repair-shape summary should mention both pause AND page —
        # consumer of the classifier uses this in the triage-summary footer.
        assert "pause" in result["description"].lower()
        assert (
            "host" in result["description"].lower()
            or "page" in result["description"].lower()
        )


class TestSanityUnchanged:
    """Pre-existing classes still classify correctly after the new entry."""

    def test_oom_still_wins_over_draft_failed(self):
        diag = (
            "oom-killer invoked\n"
            "Draft: FAILED later\n"
        )
        assert tc.classify(diag)["class"] == tc.TriageClass.OOM

    def test_unknown_still_fires_when_nothing_matches(self):
        diag = "totally benign log with no recognized markers\n"
        result = tc.classify(diag)
        assert result["class"] == tc.TriageClass.UNKNOWN
