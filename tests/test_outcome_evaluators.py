"""Tests for workflow.outcomes evaluators — protocol conformance, EvalResult shape."""

from __future__ import annotations

import pytest

from workflow.evaluation import EvalResult, Evaluator
from workflow.outcomes import (
    DeployedAppEvaluator,
    MergedPREvaluator,
    PublishedPaperEvaluator,
)

# ── Protocol conformance ───────────────────────────────────────────────────────

class TestProtocolConformance:
    def test_published_paper_is_evaluator(self):
        assert isinstance(PublishedPaperEvaluator(), Evaluator)

    def test_merged_pr_is_evaluator(self):
        assert isinstance(MergedPREvaluator(), Evaluator)

    def test_deployed_app_is_evaluator(self):
        assert isinstance(DeployedAppEvaluator(), Evaluator)

    def test_result_is_eval_result(self):
        ev = PublishedPaperEvaluator()
        result = ev.evaluate({"doi": "10.1234/test"})
        assert isinstance(result, EvalResult)


# ── PublishedPaperEvaluator ───────────────────────────────────────────────────

class TestPublishedPaperEvaluator:
    def test_no_doi_returns_skip(self):
        ev = PublishedPaperEvaluator()
        result = ev.evaluate({})
        assert result.verdict == "skip"
        assert result.score == pytest.approx(-1.0)
        assert result.label == "published_paper"

    def test_none_doi_returns_skip(self):
        ev = PublishedPaperEvaluator()
        result = ev.evaluate({"doi": None})
        assert result.verdict == "skip"

    def test_resolved_doi_returns_pass(self):
        ev = PublishedPaperEvaluator(prober=lambda url: True)
        result = ev.evaluate({"doi": "10.1234/example"})
        assert result.verdict == "pass"
        assert result.score == pytest.approx(1.0)
        assert result.details["resolved"] is True
        assert "doi.org/10.1234/example" in result.details["doi_url"]

    def test_unresolved_doi_returns_fail(self):
        ev = PublishedPaperEvaluator(prober=lambda url: False)
        result = ev.evaluate({"doi": "10.9999/nonexistent"})
        assert result.verdict == "fail"
        assert result.score == pytest.approx(0.0)
        assert result.details["resolved"] is False

    def test_kind_is_custom(self):
        ev = PublishedPaperEvaluator()
        result = ev.evaluate({})
        assert result.kind == "custom"

    def test_score_in_valid_range(self):
        for prober_result in (True, False):
            ev = PublishedPaperEvaluator(prober=lambda url, r=prober_result: r)
            result = ev.evaluate({"doi": "10.1234/x"})
            assert -1.0 <= result.score <= 1.0

    def test_default_prober_does_not_raise(self):
        ev = PublishedPaperEvaluator()
        result = ev.evaluate({"doi": "10.1234/example"})
        assert result.verdict == "fail"


# ── MergedPREvaluator ─────────────────────────────────────────────────────────

class TestMergedPREvaluator:
    def test_no_pr_url_returns_skip(self):
        ev = MergedPREvaluator()
        result = ev.evaluate({})
        assert result.verdict == "skip"
        assert result.score == pytest.approx(-1.0)
        assert result.label == "merged_pr"

    def test_merged_pr_returns_pass(self):
        ev = MergedPREvaluator(prober=lambda url: True)
        result = ev.evaluate({"pr_url": "https://github.com/org/repo/pull/42"})
        assert result.verdict == "pass"
        assert result.score == pytest.approx(1.0)
        assert result.details["merged"] is True

    def test_unmerged_pr_returns_fail(self):
        ev = MergedPREvaluator(prober=lambda url: False)
        result = ev.evaluate({"pr_url": "https://github.com/org/repo/pull/42"})
        assert result.verdict == "fail"
        assert result.score == pytest.approx(0.0)

    def test_details_contain_pr_url(self):
        url = "https://github.com/org/repo/pull/42"
        ev = MergedPREvaluator(prober=lambda u: True)
        result = ev.evaluate({"pr_url": url})
        assert result.details["pr_url"] == url

    def test_score_in_valid_range(self):
        for prober_result in (True, False):
            ev = MergedPREvaluator(prober=lambda url, r=prober_result: r)
            result = ev.evaluate({"pr_url": "https://github.com/x/y/pull/1"})
            assert -1.0 <= result.score <= 1.0


# ── DeployedAppEvaluator ──────────────────────────────────────────────────────

class TestDeployedAppEvaluator:
    def test_no_app_url_returns_skip(self):
        ev = DeployedAppEvaluator()
        result = ev.evaluate({})
        assert result.verdict == "skip"
        assert result.score == pytest.approx(-1.0)
        assert result.label == "deployed_app"

    def test_live_app_returns_pass(self):
        ev = DeployedAppEvaluator(prober=lambda url: True)
        result = ev.evaluate({"app_url": "https://myapp.example.com"})
        assert result.verdict == "pass"
        assert result.score == pytest.approx(1.0)
        assert result.details["live"] is True

    def test_dead_app_returns_fail(self):
        ev = DeployedAppEvaluator(prober=lambda url: False)
        result = ev.evaluate({"app_url": "https://myapp.example.com"})
        assert result.verdict == "fail"
        assert result.score == pytest.approx(0.0)

    def test_details_contain_app_url(self):
        url = "https://myapp.example.com"
        ev = DeployedAppEvaluator(prober=lambda u: False)
        result = ev.evaluate({"app_url": url})
        assert result.details["app_url"] == url

    def test_score_in_valid_range(self):
        for prober_result in (True, False):
            ev = DeployedAppEvaluator(prober=lambda url, r=prober_result: r)
            result = ev.evaluate({"app_url": "https://x.example.com"})
            assert -1.0 <= result.score <= 1.0

    def test_default_prober_does_not_raise(self):
        ev = DeployedAppEvaluator()
        result = ev.evaluate({"app_url": "https://example.com"})
        assert result.verdict == "fail"


# ── EvalResult shape invariants ───────────────────────────────────────────────

class TestEvalResultShape:
    def test_all_evaluators_return_valid_kind(self):
        evaluators = [
            PublishedPaperEvaluator(),
            MergedPREvaluator(),
            DeployedAppEvaluator(),
        ]
        valid_kinds = {"structural", "editorial", "process", "numeric", "custom"}
        for ev in evaluators:
            result = ev.evaluate({})
            assert result.kind in valid_kinds

    def test_all_evaluators_return_valid_verdict(self):
        evaluators = [
            PublishedPaperEvaluator(),
            MergedPREvaluator(),
            DeployedAppEvaluator(),
        ]
        valid_verdicts = {"pass", "fail", "skip", "error"}
        for ev in evaluators:
            result = ev.evaluate({})
            assert result.verdict in valid_verdicts

    def test_all_evaluators_score_in_range(self):
        evaluators = [
            PublishedPaperEvaluator(prober=lambda url: True),
            MergedPREvaluator(prober=lambda url: True),
            DeployedAppEvaluator(prober=lambda url: True),
        ]
        for ev in evaluators:
            result = ev.evaluate({"doi": "x", "pr_url": "y", "app_url": "z"})
            assert -1.0 <= result.score <= 1.0
