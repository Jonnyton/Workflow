from __future__ import annotations

from workflow.branch_tasks import BranchTask, append_task, claim_task, read_queue
from workflow.dispatcher import (
    DispatcherConfig,
    load_dispatcher_config,
    select_next_task,
)


def _task(task_id: str, **kwargs) -> BranchTask:
    return BranchTask(
        branch_task_id=task_id,
        branch_def_id=f"branch-{task_id}",
        universe_id="u",
        queued_at="2026-05-02T00:00:00+00:00",
        **kwargs,
    )


def test_claim_task_rejects_wrong_directed_daemon(tmp_path):
    append_task(
        tmp_path,
        _task("t1", directed_daemon_id="daemon::soren"),
    )

    assert claim_task(
        tmp_path,
        "t1",
        "runtime-1",
        claimer_daemon_id="daemon::mira",
    ) is None

    [pending] = read_queue(tmp_path)
    assert pending.status == "pending"
    assert pending.claimed_by == ""


def test_claim_task_requires_domain_claims_and_claim_proofs(tmp_path):
    append_task(
        tmp_path,
        _task(
            "t1",
            required_domain_claims=["workflow-platform", "reviewer"],
            required_claim_proofs=["proof:loop-review"],
        ),
    )

    assert claim_task(
        tmp_path,
        "t1",
        "daemon::soren",
        claimer_daemon_id="daemon::soren",
        domain_claims=["workflow-platform"],
        claim_proofs=["proof:other"],
    ) is None

    claimed = claim_task(
        tmp_path,
        "t1",
        "daemon::soren-runtime-1",
        claimer_daemon_id="daemon::soren",
        domain_claims=["workflow-platform", "reviewer"],
        claim_proofs=["proof:loop-review"],
    )

    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.claimed_by == "daemon::soren-runtime-1"


def test_borrowed_role_context_satisfies_domain_without_copying_identity(tmp_path):
    append_task(
        tmp_path,
        _task(
            "t1",
            required_domain_claims=["release-checker"],
            borrowed_role_context_id="daemon::release-checker-core",
        ),
    )

    claimed = claim_task(
        tmp_path,
        "t1",
        "daemon::community-runner-runtime-1",
        claimer_daemon_id="daemon::community-runner",
        borrowed_role_context_ids=["daemon::release-checker-core"],
    )

    assert claimed is not None
    assert claimed.claimed_by == "daemon::community-runner-runtime-1"
    assert claimed.borrowed_role_context_id == "daemon::release-checker-core"


def test_dispatcher_filters_directed_domain_and_proof_requirements(tmp_path):
    append_task(
        tmp_path,
        _task(
            "wrong",
            directed_daemon_id="daemon::other",
            priority_weight=100,
        ),
    )
    append_task(
        tmp_path,
        _task(
            "missing-proof",
            required_domain_claims=["workflow-platform"],
            required_claim_proofs=["proof:other-loop"],
            priority_weight=90,
        ),
    )
    append_task(
        tmp_path,
        _task(
            "eligible",
            directed_daemon_id="daemon::soren",
            required_domain_claims=["workflow-platform"],
            required_claim_proofs=["proof:community-loop"],
            priority_weight=10,
        ),
    )

    selected = select_next_task(
        tmp_path,
        config=DispatcherConfig(
            daemon_id="daemon::soren",
            domain_claims=["workflow-platform"],
            claim_proofs=["proof:community-loop"],
        ),
        now_iso="2026-05-02T00:01:00+00:00",
    )

    assert selected is not None
    assert selected.branch_task_id == "eligible"


def test_dispatcher_accepts_explicit_borrowed_role_context(tmp_path):
    append_task(
        tmp_path,
        _task(
            "borrowed",
            required_domain_claims=["security-reviewer"],
            borrowed_role_context_id="daemon::security-core",
        ),
    )

    selected = select_next_task(
        tmp_path,
        config=DispatcherConfig(
            daemon_id="daemon::implementation-runner",
            borrowed_role_context_ids=["daemon::security-core"],
        ),
        now_iso="2026-05-02T00:01:00+00:00",
    )

    assert selected is not None
    assert selected.branch_task_id == "borrowed"


def test_load_dispatcher_config_reads_daemon_eligibility_fields(tmp_path):
    (tmp_path / "dispatcher_config.yaml").write_text(
        "daemon_id: daemon::soren\n"
        "domain_claims:\n"
        "  - workflow-platform\n"
        "claim_proofs:\n"
        "  - proof:community-loop\n"
        "borrowed_role_context_ids:\n"
        "  - daemon::release-checker-core\n",
        encoding="utf-8",
    )

    config = load_dispatcher_config(tmp_path)

    assert config.daemon_id == "daemon::soren"
    assert config.domain_claims == ["workflow-platform"]
    assert config.claim_proofs == ["proof:community-loop"]
    assert config.borrowed_role_context_ids == ["daemon::release-checker-core"]


def test_runtime_dispatcher_pick_passes_daemon_profile_to_claim(tmp_path, monkeypatch):
    from fantasy_daemon.__main__ import _try_dispatcher_pick

    monkeypatch.setenv("WORKFLOW_UNIFIED_EXECUTION", "1")
    append_task(
        tmp_path,
        _task(
            "runtime",
            directed_daemon_id="daemon::soren",
            required_domain_claims=["workflow-platform"],
        ),
    )

    claimed, inputs = _try_dispatcher_pick(
        tmp_path,
        "daemon::soren",
        domain_claims=["workflow-platform"],
    )

    assert claimed is not None
    assert claimed.branch_task_id == "runtime"
    assert claimed.claimed_by == "daemon::soren"
    assert inputs == {}


def test_runtime_dispatcher_pick_rejects_config_identity_mismatch(
    tmp_path, monkeypatch,
):
    from fantasy_daemon.__main__ import _try_dispatcher_pick

    monkeypatch.setenv("WORKFLOW_UNIFIED_EXECUTION", "1")
    (tmp_path / "dispatcher_config.yaml").write_text(
        "daemon_id: daemon::copied-soul\n",
        encoding="utf-8",
    )
    append_task(
        tmp_path,
        _task("runtime", directed_daemon_id="daemon::copied-soul"),
    )

    claimed, inputs = _try_dispatcher_pick(tmp_path, "daemon::actual-runtime")

    assert claimed is None
    assert inputs == {}
    [pending] = read_queue(tmp_path)
    assert pending.status == "pending"
