"""Real-world outcome evaluator adapters.

Each class satisfies the `workflow.evaluation.Evaluator` protocol via structural
subtyping — no inheritance required. All implement:
    evaluate(state: dict[str, Any]) -> EvalResult

State keys consumed per evaluator:
  PublishedPaperEvaluator: state["doi"]          → str or None
  MergedPREvaluator:       state["pr_url"]        → str or None
  DeployedAppEvaluator:    state["app_url"]       → str or None

All evaluators are probe-free by default. To avoid real network calls in tests,
callers inject a `prober` callable: `prober(url: str) -> bool`.
When no prober is injected, `_default_prober` is used (always returns False
to avoid network calls during import/test collection).
"""

from __future__ import annotations

from typing import Any, Callable

from workflow.evaluation import EvalResult

# Default prober: never fires real network requests; override at call-site.
_ProberFn = Callable[[str], bool]


def _no_network_prober(url: str) -> bool:  # noqa: ARG001
    """Default prober — network-free, always returns False."""
    return False


class PublishedPaperEvaluator:
    """Checks whether a DOI resolves to a published paper.

    state keys:
      doi (str | None): DOI identifier, e.g. "10.1234/example".
    """

    label = "published_paper"

    def __init__(self, prober: _ProberFn = _no_network_prober) -> None:
        self._prober = prober

    def evaluate(self, state: dict[str, Any]) -> EvalResult:
        doi = state.get("doi")
        if not doi:
            return EvalResult(
                score=-1.0,
                verdict="skip",
                kind="custom",
                label=self.label,
                details={"reason": "no doi in state"},
            )
        doi_url = f"https://doi.org/{doi}"
        resolved = self._prober(doi_url)
        return EvalResult(
            score=1.0 if resolved else 0.0,
            verdict="pass" if resolved else "fail",
            kind="custom",
            label=self.label,
            details={"doi": doi, "doi_url": doi_url, "resolved": resolved},
        )


class MergedPREvaluator:
    """Checks whether a GitHub PR URL reports a merged state.

    state keys:
      pr_url (str | None): GitHub PR URL, e.g. "https://github.com/org/repo/pull/42".
    """

    label = "merged_pr"

    def __init__(self, prober: _ProberFn = _no_network_prober) -> None:
        self._prober = prober

    def evaluate(self, state: dict[str, Any]) -> EvalResult:
        pr_url = state.get("pr_url")
        if not pr_url:
            return EvalResult(
                score=-1.0,
                verdict="skip",
                kind="custom",
                label=self.label,
                details={"reason": "no pr_url in state"},
            )
        merged = self._prober(pr_url)
        return EvalResult(
            score=1.0 if merged else 0.0,
            verdict="pass" if merged else "fail",
            kind="custom",
            label=self.label,
            details={"pr_url": pr_url, "merged": merged},
        )


class DeployedAppEvaluator:
    """Checks whether an application URL is live (HTTP 2xx).

    state keys:
      app_url (str | None): URL to probe, e.g. "https://myapp.example.com".
    """

    label = "deployed_app"

    def __init__(self, prober: _ProberFn = _no_network_prober) -> None:
        self._prober = prober

    def evaluate(self, state: dict[str, Any]) -> EvalResult:
        app_url = state.get("app_url")
        if not app_url:
            return EvalResult(
                score=-1.0,
                verdict="skip",
                kind="custom",
                label=self.label,
                details={"reason": "no app_url in state"},
            )
        live = self._prober(app_url)
        return EvalResult(
            score=1.0 if live else 0.0,
            verdict="pass" if live else "fail",
            kind="custom",
            label=self.label,
            details={"app_url": app_url, "live": live},
        )
