from __future__ import annotations

import datetime as dt

from scripts import community_loop_watch as watch


def test_workflow_stage_ignores_neutral_skipped_runs(monkeypatch):
    now = dt.datetime(2026, 5, 1, 5, 10, tzinfo=dt.timezone.utc)

    def fake_gh_get(*_args, **_kwargs):
        return {
            "workflow_runs": [
                {
                    "id": 2,
                    "status": "completed",
                    "conclusion": "skipped",
                    "created_at": "2026-05-01T05:09:00Z",
                    "updated_at": "2026-05-01T05:09:01Z",
                    "event": "workflow_run",
                    "html_url": "https://example.test/skipped",
                },
                {
                    "id": 1,
                    "status": "completed",
                    "conclusion": "success",
                    "created_at": "2026-05-01T05:04:00Z",
                    "updated_at": "2026-05-01T05:05:00Z",
                    "event": "workflow_run",
                    "html_url": "https://example.test/success",
                },
            ]
        }

    monkeypatch.setattr(watch, "_gh_get", fake_gh_get)

    stage = watch.workflow_stage(
        "Production deploy",
        "owner/repo",
        "deploy-prod.yml",
        api="https://api.github.test",
        token=None,
        timeout=1,
        now=now,
        max_age_min=None,
    )

    assert stage["status"] == "green"
    assert stage["details"]["run_id"] == 1
    assert stage["details"]["ignored_skipped_run_ids"] == [2]


def test_workflow_stage_keeps_in_progress_meaningful_run(monkeypatch):
    now = dt.datetime(2026, 5, 1, 5, 10, tzinfo=dt.timezone.utc)

    def fake_gh_get(*_args, **_kwargs):
        return {
            "workflow_runs": [
                {
                    "id": 3,
                    "status": "in_progress",
                    "conclusion": None,
                    "created_at": "2026-05-01T05:09:00Z",
                    "updated_at": "2026-05-01T05:09:30Z",
                    "event": "push",
                    "html_url": "https://example.test/in-progress",
                },
                {
                    "id": 2,
                    "status": "completed",
                    "conclusion": "skipped",
                    "created_at": "2026-05-01T05:08:00Z",
                    "updated_at": "2026-05-01T05:08:01Z",
                    "event": "workflow_run",
                    "html_url": "https://example.test/skipped",
                },
            ]
        }

    monkeypatch.setattr(watch, "_gh_get", fake_gh_get)

    stage = watch.workflow_stage(
        "Writer workflow",
        "owner/repo",
        "auto-fix-bug.yml",
        api="https://api.github.test",
        token=None,
        timeout=1,
        now=now,
        max_age_min=90,
    )

    assert stage["status"] == "yellow"
    assert stage["details"]["run_id"] == 3
