"""Phase G — NodeBid executor + paid market priority weights.

Tests:
- NodeBid dataclass + YAML I/O (6)
- validate_node_bid_inputs (4)
- read_node_bids / claim_node_bid (5)
- NodeBidProducer (7)
- execute_node_bid (6)
- Dispatcher scorer + LLM filter (7)
- submit_node_bid MCP action (5)
- Flag matrix (4)
- Settlement + ledger (3)
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
import yaml

from workflow.bid_ledger import append_ledger_entry, read_ledger
from workflow.branch_tasks import BranchTask
from workflow.dispatcher import (
    DispatcherConfig,
    load_dispatcher_config,
    score_task,
    select_next_task,
)
from workflow.dispatcher import (
    paid_market_enabled as dispatcher_paid_market_enabled,
)
from workflow.executors.node_bid import execute_node_bid
from workflow.node_bid import (
    NodeBid,
    bid_path,
    claim_node_bid,
    new_node_bid_id,
    read_node_bid,
    read_node_bids,
    update_node_bid_status,
    validate_node_bid_inputs,
    write_node_bid_post,
)
from workflow.producers import branch_task as bt_producer_mod
from workflow.producers.branch_task import (
    reset_branch_task_registry,
)
from workflow.producers.node_bid import (
    NODE_BID_SENTINEL_PREFIX,
    NodeBidProducer,
    paid_market_enabled,
    register_if_enabled,
)

# ───────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = list(bt_producer_mod._REGISTRY)
    reset_branch_task_registry()
    yield
    reset_branch_task_registry()
    bt_producer_mod._REGISTRY.extend(saved)


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "branches").mkdir()
    (root / "bids").mkdir()
    monkeypatch.setenv("WORKFLOW_REPO_ROOT", str(root))
    return root


@pytest.fixture
def universe_dir(tmp_path: Path) -> Path:
    udir = tmp_path / "uni-a"
    udir.mkdir()
    return udir


@pytest.fixture
def paid_flag_on(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on")
    return True


@pytest.fixture
def paid_flag_off(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "off")
    return True


def _write_bid_yaml(
    repo_root: Path,
    node_bid_id: str,
    *,
    node_def_id: str = "extract_entities",
    required_llm_type: str = "",
    inputs: dict | None = None,
    bid: float = 0.0,
    status: str = "open",
) -> Path:
    path = repo_root / "bids" / f"{node_bid_id}.yaml"
    payload = {
        "node_bid_id": node_bid_id,
        "node_def_id": node_def_id,
        "required_llm_type": required_llm_type,
        "inputs": inputs or {},
        "bid": bid,
        "submitted_by": "alice",
        "status": status,
        "evidence_url": "",
        "submitted_at": "2026-04-14T12:00:00+00:00",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _make_approved_node(node_id: str, source_code: str):
    from workflow.branches import NodeDefinition
    return NodeDefinition(
        node_id=node_id,
        display_name=node_id,
        approved=True,
        source_code=source_code,
    )


# ───────────────────────────────────────────────────────────────────────
# NodeBid dataclass + YAML I/O
# ───────────────────────────────────────────────────────────────────────


def test_nodebid_dataclass_defaults():
    bid = NodeBid(node_bid_id="nb_1", node_def_id="foo")
    assert bid.status == "open"
    assert bid.bid == 0.0
    assert bid.inputs == {}


def test_nodebid_to_and_from_dict_roundtrip():
    bid = NodeBid(
        node_bid_id="nb_1", node_def_id="foo",
        required_llm_type="claude-opus", inputs={"x": 1}, bid=2.5,
        submitted_by="alice", status="open", submitted_at="2026-04-14",
    )
    restored = NodeBid.from_dict(bid.to_dict())
    assert restored == bid


def test_nodebid_from_dict_ignores_unknown_keys():
    data = {"node_bid_id": "nb_1", "node_def_id": "foo", "extra": "ignored"}
    bid = NodeBid.from_dict(data)
    assert bid.node_bid_id == "nb_1"


def test_write_and_read_node_bid(repo_root):
    path = write_node_bid_post(repo_root, {
        "node_bid_id": "nb_test", "node_def_id": "foo",
        "inputs": {"x": 1}, "bid": 3.0, "status": "open",
    })
    assert path.exists()
    bid = read_node_bid(repo_root, "nb_test")
    assert bid is not None
    assert bid.node_def_id == "foo"
    assert bid.bid == 3.0


def test_read_node_bids_empty_dir(tmp_path):
    empty = tmp_path / "empty_repo"
    empty.mkdir()
    assert read_node_bids(empty) == []


def test_read_node_bids_skips_malformed(repo_root, caplog):
    bad = repo_root / "bids" / "bad.yaml"
    bad.write_text("::: invalid yaml :::", encoding="utf-8")
    _write_bid_yaml(repo_root, "good_nb", node_def_id="foo")
    bids = read_node_bids(repo_root)
    assert [b.node_bid_id for b in bids] == ["good_nb"]


# ───────────────────────────────────────────────────────────────────────
# validate_node_bid_inputs
# ───────────────────────────────────────────────────────────────────────


def test_validate_accepts_flat_primitives():
    ok, reason = validate_node_bid_inputs({"a": "s", "b": 1, "c": 1.5, "d": True, "e": None})
    assert ok, reason


def test_validate_rejects_nested_dict():
    ok, _ = validate_node_bid_inputs({"a": {"nested": 1}})
    assert not ok


def test_validate_rejects_underscore_prefix():
    ok, _ = validate_node_bid_inputs({"_universe_path": "/etc"})
    assert not ok


def test_validate_rejects_list_values():
    ok, _ = validate_node_bid_inputs({"items": [1, 2, 3]})
    assert not ok


# ───────────────────────────────────────────────────────────────────────
# claim_node_bid + status update
# ───────────────────────────────────────────────────────────────────────


def test_claim_node_bid_first_wins(repo_root):
    _write_bid_yaml(repo_root, "nb_claim")
    assert claim_node_bid(repo_root, "nb_claim", "daemon-A") is True
    assert claim_node_bid(repo_root, "nb_claim", "daemon-B") is False
    bid = read_node_bid(repo_root, "nb_claim")
    assert bid.status == "claimed:daemon-A"


def test_claim_missing_bid_returns_false(repo_root):
    assert claim_node_bid(repo_root, "nb_missing", "daemon-A") is False


def test_update_node_bid_status(repo_root):
    _write_bid_yaml(repo_root, "nb_up")
    assert update_node_bid_status(
        repo_root, "nb_up",
        status="succeeded", evidence_url="file:///tmp/out.json",
    ) is True
    bid = read_node_bid(repo_root, "nb_up")
    assert bid.status == "succeeded"
    assert bid.evidence_url == "file:///tmp/out.json"


# ───────────────────────────────────────────────────────────────────────
# NodeBidProducer
# ───────────────────────────────────────────────────────────────────────


def test_producer_emits_open_bids(repo_root, universe_dir):
    _write_bid_yaml(repo_root, "nb_1", node_def_id="foo", bid=2.5)
    _write_bid_yaml(repo_root, "nb_2", node_def_id="bar", bid=1.0)
    producer = NodeBidProducer()
    tasks = producer.produce(universe_dir, subscribed_goals=[])
    assert len(tasks) == 2
    for t in tasks:
        assert t.branch_def_id.startswith(NODE_BID_SENTINEL_PREFIX)
        assert t.trigger_source == "paid_bid"
        assert t.bid > 0


def test_producer_skips_non_open_status(repo_root, universe_dir):
    _write_bid_yaml(repo_root, "nb_open", node_def_id="foo")
    _write_bid_yaml(repo_root, "nb_done", node_def_id="bar", status="succeeded")
    _write_bid_yaml(repo_root, "nb_claimed", node_def_id="baz", status="claimed:d1")
    producer = NodeBidProducer()
    tasks = producer.produce(universe_dir, subscribed_goals=[])
    assert [t.inputs["__node_bid_id"] for t in tasks] == ["nb_open"]


def test_producer_filters_llm_type_mismatch(repo_root, universe_dir):
    _write_bid_yaml(repo_root, "nb_opus", node_def_id="f", required_llm_type="claude-opus")
    _write_bid_yaml(repo_root, "nb_sonnet", node_def_id="f", required_llm_type="claude-sonnet")
    _write_bid_yaml(repo_root, "nb_any", node_def_id="f", required_llm_type="")
    producer = NodeBidProducer()
    tasks = producer.produce(
        universe_dir, subscribed_goals=[],
        config={"served_llm_type": "claude-opus"},
    )
    ids = sorted(t.inputs["__node_bid_id"] for t in tasks)
    assert ids == ["nb_any", "nb_opus"]


def test_producer_empty_served_llm_accepts_all(repo_root, universe_dir):
    _write_bid_yaml(repo_root, "nb_opus", node_def_id="f", required_llm_type="claude-opus")
    _write_bid_yaml(repo_root, "nb_sonnet", node_def_id="f", required_llm_type="claude-sonnet")
    producer = NodeBidProducer()
    tasks = producer.produce(universe_dir, subscribed_goals=[])
    assert len(tasks) == 2


def test_producer_skips_invalid_inputs(repo_root, universe_dir):
    _write_bid_yaml(
        repo_root, "nb_bad", node_def_id="f",
        inputs={"_universe_path": "/etc"},
    )
    _write_bid_yaml(repo_root, "nb_ok", node_def_id="f", inputs={"x": 1})
    producer = NodeBidProducer()
    tasks = producer.produce(universe_dir, subscribed_goals=[])
    assert [t.inputs["__node_bid_id"] for t in tasks] == ["nb_ok"]


def test_producer_stamps_internal_input_keys(repo_root, universe_dir):
    _write_bid_yaml(
        repo_root, "nb_stamp", node_def_id="foo", inputs={"x": 1},
    )
    producer = NodeBidProducer()
    tasks = producer.produce(universe_dir, subscribed_goals=[])
    assert tasks[0].inputs["__node_bid_id"] == "nb_stamp"
    assert tasks[0].inputs["__node_def_id"] == "foo"
    assert tasks[0].inputs["x"] == 1


def test_producer_mtime_cache(repo_root, universe_dir):
    _write_bid_yaml(repo_root, "nb_c", node_def_id="foo")
    producer = NodeBidProducer()
    first = producer.produce(universe_dir, subscribed_goals=[])
    # Second call with no mtime change should hit cache.
    second = producer.produce(universe_dir, subscribed_goals=[])
    assert [t.branch_task_id for t in first] == [t.branch_task_id for t in second]


# ───────────────────────────────────────────────────────────────────────
# execute_node_bid
# ───────────────────────────────────────────────────────────────────────


def test_execute_succeeds_writes_artifact(tmp_path):
    node = _make_approved_node(
        "simple",
        "def run(state):\n    return {'echo': state.get('x', 0) * 2}\n",
    )
    bid = NodeBid(
        node_bid_id="nb_exec", node_def_id="simple",
        inputs={"x": 21}, status="open",
    )
    result = execute_node_bid(
        bid, node_lookup_fn=lambda nid: node if nid == "simple" else None,
        output_dir=tmp_path,
    )
    assert result.status == "succeeded"
    assert result.output == {"echo": 42}
    assert result.evidence_url.startswith("file://")
    artifact = tmp_path / "bid_outputs" / "nb_exec" / "output.json"
    assert artifact.exists()
    assert json.loads(artifact.read_text()) == {"echo": 42}


def test_execute_unknown_node_fails(tmp_path):
    bid = NodeBid(node_bid_id="nb_nf", node_def_id="missing", status="open")
    result = execute_node_bid(
        bid, node_lookup_fn=lambda _nid: None, output_dir=tmp_path,
    )
    assert result.status == "failed"
    assert "node_not_found" in result.error


def test_execute_unapproved_node_fails(tmp_path):
    from workflow.branches import NodeDefinition
    node = NodeDefinition(
        node_id="bad", display_name="bad",
        approved=False, source_code="def run(s): return {}",
    )
    bid = NodeBid(node_bid_id="nb_ua", node_def_id="bad", status="open")
    result = execute_node_bid(
        bid, node_lookup_fn=lambda _nid: node, output_dir=tmp_path,
    )
    assert result.status == "failed"
    assert "unapproved_node" in result.error


def test_execute_dangerous_pattern_fails(tmp_path):
    node = _make_approved_node(
        "mal",
        "import pickle\ndef run(s): return {}\n",
    )
    bid = NodeBid(node_bid_id="nb_mal", node_def_id="mal", status="open")
    result = execute_node_bid(
        bid, node_lookup_fn=lambda _nid: node, output_dir=tmp_path,
    )
    assert result.status == "failed"
    assert "dangerous_pattern" in result.error


def test_execute_strips_internal_input_keys(tmp_path):
    node = _make_approved_node(
        "echo",
        "def run(state):\n    return {'keys': sorted(state.keys())}\n",
    )
    bid = NodeBid(
        node_bid_id="nb_strip", node_def_id="echo",
        inputs={
            "__node_bid_id": "nb_strip",
            "__node_def_id": "echo",
            "user_key": "ok",
        },
        status="open",
    )
    result = execute_node_bid(
        bid, node_lookup_fn=lambda _nid: node, output_dir=tmp_path,
    )
    assert result.status == "succeeded"
    assert result.output == {"keys": ["user_key"]}


def test_execute_node_that_raises_fails(tmp_path):
    node = _make_approved_node(
        "boom",
        "def run(state):\n    raise ValueError('x')\n",
    )
    bid = NodeBid(node_bid_id="nb_boom", node_def_id="boom", status="open")
    result = execute_node_bid(
        bid, node_lookup_fn=lambda _nid: node, output_dir=tmp_path,
    )
    assert result.status == "failed"
    assert "run_error" in result.error


# ───────────────────────────────────────────────────────────────────────
# Dispatcher scoring + LLM-type filter
# ───────────────────────────────────────────────────────────────────────


def _mk_task(**kw):
    defaults = dict(
        branch_task_id=kw.pop("tid", "t1"),
        branch_def_id="foo",
        universe_id="uni",
        trigger_source="paid_bid",
        status="pending",
        queued_at="2026-04-14T12:00:00+00:00",
    )
    defaults.update(kw)
    return BranchTask(**defaults)


def test_score_bid_zero_when_coefficient_zero():
    task = _mk_task(bid=100.0)
    cfg = DispatcherConfig(bid_coefficient=0.0)
    s1 = score_task(task, now_iso="2026-04-14T12:00:00+00:00", config=cfg)
    task0 = _mk_task(bid=0.0)
    s0 = score_task(task0, now_iso="2026-04-14T12:00:00+00:00", config=cfg)
    assert s1 == s0


def test_score_bid_scales_with_coefficient():
    cfg = DispatcherConfig(bid_coefficient=1.0, bid_term_cap=1000.0)
    t1 = _mk_task(tid="a", bid=1.0)
    t10 = _mk_task(tid="b", bid=10.0)
    now = "2026-04-14T12:00:00+00:00"
    assert (
        score_task(t10, now_iso=now, config=cfg)
        > score_task(t1, now_iso=now, config=cfg)
    )


def test_bid_term_cap_enforced():
    cfg = DispatcherConfig(bid_coefficient=1.0, bid_term_cap=5.0)
    t_big = _mk_task(bid=10000.0)
    t_cap = _mk_task(bid=5.0)
    now = "2026-04-14T12:00:00+00:00"
    s_big = score_task(t_big, now_iso=now, config=cfg)
    s_cap = score_task(t_cap, now_iso=now, config=cfg)
    assert s_big == s_cap


def test_host_request_beats_max_bid_paid(tmp_path):
    from workflow.branch_tasks import append_task
    u = tmp_path / "u"
    u.mkdir()
    append_task(u, _mk_task(
        tid="host1", trigger_source="host_request", bid=0.0,
    ))
    append_task(u, _mk_task(
        tid="paid1", trigger_source="paid_bid", bid=99999.0,
    ))
    cfg = DispatcherConfig(
        accept_paid_bids=True, bid_coefficient=1.0, bid_term_cap=30.0,
    )
    picked = select_next_task(u, config=cfg)
    assert picked.branch_task_id == "host1"


def test_llm_type_filter_empty_served_passes_all(tmp_path):
    from workflow.branch_tasks import append_task
    u = tmp_path / "u"
    u.mkdir()
    append_task(u, _mk_task(
        tid="t1", trigger_source="paid_bid", required_llm_type="claude-opus",
    ))
    cfg = DispatcherConfig(accept_paid_bids=True, served_llm_type="")
    assert select_next_task(u, config=cfg) is not None


def test_llm_type_filter_matching_passes(tmp_path):
    from workflow.branch_tasks import append_task
    u = tmp_path / "u"
    u.mkdir()
    append_task(u, _mk_task(
        tid="t1", trigger_source="paid_bid", required_llm_type="claude-opus",
    ))
    cfg = DispatcherConfig(accept_paid_bids=True, served_llm_type="claude-opus")
    assert select_next_task(u, config=cfg) is not None


def test_llm_type_filter_mismatch_skipped(tmp_path):
    from workflow.branch_tasks import append_task
    u = tmp_path / "u"
    u.mkdir()
    append_task(u, _mk_task(
        tid="t1", trigger_source="paid_bid", required_llm_type="claude-opus",
    ))
    cfg = DispatcherConfig(accept_paid_bids=True, served_llm_type="claude-sonnet")
    assert select_next_task(u, config=cfg) is None


# ───────────────────────────────────────────────────────────────────────
# submit_node_bid MCP action
# ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def mcp_harness(tmp_path, monkeypatch, paid_flag_on):
    base = tmp_path / "output"
    base.mkdir()
    uid = "test-uni"
    (base / uid).mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bids").mkdir()
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(base))
    monkeypatch.setenv("UNIVERSE_SERVER_DEFAULT_UNIVERSE", uid)
    monkeypatch.setenv("WORKFLOW_REPO_ROOT", str(repo))
    return {"base": base, "uid": uid, "repo": repo}


def test_submit_node_bid_flag_off_returns_not_available(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "off")
    base = tmp_path / "output"
    base.mkdir()
    uid = "test-uni"
    (base / uid).mkdir()
    monkeypatch.setenv("UNIVERSE_SERVER_BASE", str(base))
    monkeypatch.setenv("UNIVERSE_SERVER_DEFAULT_UNIVERSE", uid)

    from workflow.universe_server import _action_submit_node_bid
    resp = json.loads(_action_submit_node_bid(
        universe_id=uid, node_def_id="foo", inputs_json="{}", bid=1.0,
    ))
    assert resp["status"] == "not_available"


def test_submit_node_bid_valid_writes_yaml(mcp_harness):
    from workflow.universe_server import _action_submit_node_bid
    resp = json.loads(_action_submit_node_bid(
        universe_id=mcp_harness["uid"],
        node_def_id="extract_entities",
        inputs_json=json.dumps({"text": "hi"}),
        bid=2.5,
    ))
    assert resp["status"] == "posted"
    assert Path(resp["path"]).exists()
    bid_id = resp["node_bid_id"]
    data = yaml.safe_load((mcp_harness["repo"] / "bids" / f"{bid_id}.yaml").read_text())
    assert data["node_def_id"] == "extract_entities"
    assert data["bid"] == 2.5
    assert data["status"] == "open"


def test_submit_node_bid_response_has_git_push_hint(mcp_harness):
    from workflow.universe_server import _action_submit_node_bid
    resp = json.loads(_action_submit_node_bid(
        universe_id=mcp_harness["uid"],
        node_def_id="extract_entities",
        inputs_json="{}",
        bid=1.0,
    ))
    assert "git add" in resp["next_step"]
    assert "git push" in resp["next_step"]


def test_submit_node_bid_rejects_nested_inputs(mcp_harness):
    from workflow.universe_server import _action_submit_node_bid
    resp = json.loads(_action_submit_node_bid(
        universe_id=mcp_harness["uid"],
        node_def_id="f",
        inputs_json=json.dumps({"nested": {"bad": 1}}),
        bid=1.0,
    ))
    assert resp["status"] == "rejected"
    assert "invalid_inputs" in resp["error"]


def test_submit_node_bid_rejects_negative_bid(mcp_harness):
    from workflow.universe_server import _action_submit_node_bid
    resp = json.loads(_action_submit_node_bid(
        universe_id=mcp_harness["uid"],
        node_def_id="f",
        inputs_json="{}",
        bid=-1.0,
    ))
    assert resp["status"] == "rejected"


# ───────────────────────────────────────────────────────────────────────
# Flag matrix (registration + config)
# ───────────────────────────────────────────────────────────────────────


def test_flag_off_producer_not_registered(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "off")
    reset_branch_task_registry()
    registered = register_if_enabled()
    assert registered is False
    names = [p.name for p in bt_producer_mod._REGISTRY]
    assert "node_bid" not in names


def test_flag_on_producer_registered(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on")
    reset_branch_task_registry()
    registered = register_if_enabled()
    assert registered is True
    names = [p.name for p in bt_producer_mod._REGISTRY]
    assert "node_bid" in names


def test_dispatcher_paid_market_enabled_reads_env(monkeypatch):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on")
    assert dispatcher_paid_market_enabled() is True
    assert paid_market_enabled() is True
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "off")
    assert dispatcher_paid_market_enabled() is False
    assert paid_market_enabled() is False


def test_load_dispatcher_config_flag_on_defaults_bid_coefficient(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on")
    u = tmp_path / "u"
    u.mkdir()
    cfg = load_dispatcher_config(u)
    assert cfg.bid_coefficient == 1.0
    assert cfg.accept_paid_bids is True


def test_load_dispatcher_config_yaml_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_PAID_MARKET", "on")
    u = tmp_path / "u"
    u.mkdir()
    (u / "dispatcher_config.yaml").write_text(
        "bid_coefficient: 0.0\n", encoding="utf-8",
    )
    cfg = load_dispatcher_config(u)
    assert cfg.bid_coefficient == 0.0


def test_tier_status_map_live_when_accept(monkeypatch):
    cfg = DispatcherConfig(accept_paid_bids=True)
    assert cfg.tier_status_map()["paid_bid"] == "live"
    cfg2 = DispatcherConfig(accept_paid_bids=False)
    assert cfg2.tier_status_map()["paid_bid"] == "disabled"


# ───────────────────────────────────────────────────────────────────────
# Settlement + ledger
# ───────────────────────────────────────────────────────────────────────


def test_ledger_append_creates_file(universe_dir):
    entry = {"bid_id": "nb_1", "daemon_id": "d1", "success": True}
    append_ledger_entry(universe_dir, entry)
    entries = read_ledger(universe_dir)
    assert len(entries) == 1
    assert entries[0]["bid_id"] == "nb_1"


def test_ledger_append_accumulates(universe_dir):
    append_ledger_entry(universe_dir, {"bid_id": "nb_1"})
    append_ledger_entry(universe_dir, {"bid_id": "nb_2"})
    append_ledger_entry(universe_dir, {"bid_id": "nb_3"})
    entries = read_ledger(universe_dir)
    assert [e["bid_id"] for e in entries] == ["nb_1", "nb_2", "nb_3"]


def test_ledger_concurrent_appends_dont_lose_entries(universe_dir):
    """File lock should serialize. 10 threads × 5 entries = 50 total."""
    def _worker(n):
        for i in range(5):
            append_ledger_entry(universe_dir, {
                "bid_id": f"nb_{n}_{i}", "daemon_id": f"d{n}",
            })
    threads = [threading.Thread(target=_worker, args=(n,)) for n in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    entries = read_ledger(universe_dir)
    assert len(entries) == 50


# ───────────────────────────────────────────────────────────────────────
# new_node_bid_id uniqueness
# ───────────────────────────────────────────────────────────────────────


def test_new_node_bid_id_unique():
    ids = {new_node_bid_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(i.startswith("nb_") for i in ids)


def test_bid_path_shape(tmp_path):
    assert bid_path(tmp_path, "nb_x") == tmp_path / "bids" / "nb_x.yaml"
