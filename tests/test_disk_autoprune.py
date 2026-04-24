"""Disk auto-prune tests (BUG-023 Phase 4).

Covers:
- Below threshold → no prune invocation, exit 0.
- At threshold → prune invoked, exit 0.
- Dry-run above threshold → prune NOT invoked, exit 1.
- Prune subprocess failure → exit 2.
- Missing path → exit 0 with warning (non-fatal).
"""
from __future__ import annotations

from scripts.disk_autoprune import check


class TestBelowThreshold:
    def test_no_prune_when_below(self):
        prune_calls: list[bool] = []

        def fake_prune():
            prune_calls.append(True)
            return (0, "", "")

        rc = check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 50.0,
            prune_fn=fake_prune,
        )
        assert rc == 0
        assert prune_calls == []

    def test_just_below_threshold(self):
        prune_calls: list[bool] = []

        rc = check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 84.9,
            prune_fn=lambda: (prune_calls.append(True), (0, "", ""))[1],
        )
        assert rc == 0
        assert prune_calls == []


class TestAboveThreshold:
    def test_prune_invoked_at_exact_threshold(self):
        prune_calls: list[bool] = []

        def fake_prune():
            prune_calls.append(True)
            return (0, "deleted 3 images", "")

        rc = check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 85.0,
            prune_fn=fake_prune,
        )
        assert rc == 0
        assert prune_calls == [True]

    def test_prune_invoked_well_above(self):
        prune_calls: list[bool] = []

        rc = check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 96.5,
            prune_fn=lambda: (prune_calls.append(True), (0, "", ""))[1],
        )
        assert rc == 0
        assert prune_calls == [True]


class TestDryRun:
    def test_dry_run_above_threshold_does_not_invoke_prune(self):
        prune_calls: list[bool] = []

        rc = check(
            path="/",
            threshold=85,
            dry_run=True,
            disk_fn=lambda _p: 90.0,
            prune_fn=lambda: (prune_calls.append(True), (0, "", ""))[1],
        )

        assert rc == 1  # would-prune signal
        assert prune_calls == []


class TestPruneFailureSurface:
    def test_subprocess_error_returns_2(self):
        def boom_prune():
            raise OSError("docker binary missing")

        rc = check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 90.0,
            prune_fn=boom_prune,
        )
        assert rc == 2

    def test_prune_nonzero_exit_is_logged_not_masking(self, capsys):
        """Prune returns non-zero but autoprune still exits 0 to avoid
        masking the underlying disk event with a secondary failure."""
        rc = check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 90.0,
            prune_fn=lambda: (1, "", "docker daemon not running"),
        )
        assert rc == 0

    def test_missing_path_is_non_fatal(self):
        def boom_disk(_p):
            raise FileNotFoundError("no such path")

        rc = check(
            path="/nope",
            threshold=85,
            disk_fn=boom_disk,
            prune_fn=lambda: (0, "", ""),
        )
        assert rc == 0


class TestOutputVisibility:
    def test_stdout_includes_usage_line(self, capsys):
        check(
            path="/",
            threshold=85,
            disk_fn=lambda _p: 70.0,
            prune_fn=lambda: (0, "", ""),
        )
        out = capsys.readouterr().out
        assert "70.0%" in out or "70%" in out
        assert "threshold 85" in out
