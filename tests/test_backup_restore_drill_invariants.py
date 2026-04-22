"""Tests for the DR-drill-blocking invariants fixed in Task #12.

Two invariants, both structural (grep-shape), both guarded here so a
future refactor can't silently reintroduce the exit-5 drill abort class
that ate DR drill #3:

  (a) `deploy/backup-restore.sh` must NOT attempt to start the daemon.
      The drill's dedicated "Start compose on drill Droplet" step owns
      that with full retry + probe logic. Coupling caused the restore
      script to exit 5 when cloudflared couldn't initialize without a
      real CLOUDFLARE_TUNNEL_TOKEN on the drill droplet — the daemon
      itself was perfectly capable of starting.

  (b) `.github/workflows/dr-drill.yml` "Start compose" step must scope
      to `docker compose up -d daemon` (not a bare `up -d`). Bringing
      up all services on a drill droplet fails hard on cloudflared +
      vector because those require real secrets that don't exist on a
      fresh drill provision.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_RESTORE = _REPO / "deploy" / "backup-restore.sh"
_DR_DRILL = _REPO / ".github" / "workflows" / "dr-drill.yml"


# ---- (a) restore script: no start-daemon coupling ------------------------


def test_restore_script_exists():
    assert _RESTORE.is_file()


def _restore_code() -> str:
    """Return the script body *excluding* comment lines AND `log "..."`
    message strings. Both of these legitimately reference the
    historical behavior ('docker start failed', 'try: systemctl
    restart') as operator guidance without actually invoking those
    commands. We only want to catch real shell-command invocations.
    """
    text = _RESTORE.read_text(encoding="utf-8")
    cleaned: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Strip lines that are log-message strings — they contain
        # narrative text (operator guidance) not shell invocations.
        if stripped.startswith('log "') or stripped.startswith("log '"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def test_restore_does_not_call_docker_start():
    """`docker start workflow-daemon` in the active code path was the
    2026-04-22 drill blocker. Must stay out."""
    code = _restore_code()
    assert "docker start workflow-daemon" not in code, (
        "backup-restore.sh must not `docker start workflow-daemon` — "
        "the drill's own Start step owns that with retry + probe logic"
    )


def test_restore_does_not_call_systemctl_start():
    """`systemctl start workflow-daemon` / `restart` from restore would
    trip the ExecStartPre ENV-UNREADABLE guard on a fresh drill droplet
    (Task #3). Keep it out of the restore path."""
    code = _restore_code()
    # Tolerant regex — catches `systemctl start`, `systemctl restart`,
    # and any `systemctl reload-or-restart` variants.
    assert not re.search(r"systemctl\s+(start|restart|reload-or-restart)\s+workflow-daemon",
                         code), (
        "backup-restore.sh must not systemctl-(re)start workflow-daemon"
    )


def test_restore_still_stops_daemon_before_extract():
    """The pre-extract `docker stop` is still load-bearing — overwriting
    the volume while the daemon has files open would corrupt the restored
    state. Only the post-extract start is removed."""
    code = _restore_code()
    assert "docker stop workflow-daemon" in code, (
        "pre-extract `docker stop workflow-daemon` is required for safe "
        "volume overwrite; do not remove alongside the start-coupling fix"
    )


def test_restore_exits_zero_after_extract():
    """The last `exit` in the active code path must be 0, indicating
    the split-responsibility contract (restore done, caller starts)."""
    code = _restore_code()
    # Walk through all `exit N` statements; the final one in normal flow
    # should be `exit 0` (success exit after extract). The earlier exits
    # are error-path (exit 1/2/3/4).
    exits = re.findall(r"^\s*exit\s+(\d+)\s*$", code, flags=re.MULTILINE)
    assert exits, "restore script should have explicit exit statements"
    # The LAST exit in the script is the success path.
    assert exits[-1] == "0", (
        f"restore script's final exit must be 0 (success after extract); "
        f"found exit sequence: {exits}"
    )


def test_restore_exit_5_no_longer_emitted():
    """Exit code 5 was the drill-blocker. It's reserved (documented in
    the exit-codes block) but must not be reachable from active code."""
    code = _restore_code()
    # In active code, `exit 5` must NOT appear. The docstring may
    # reference it historically; _restore_code() strips comments so any
    # exit 5 found here is in live code and must fail the test.
    assert not re.search(r"^\s*exit\s+5\s*$", code, flags=re.MULTILINE), (
        "exit 5 is the drill-blocker; keep it out of active code"
    )


# ---- (b) DR-drill workflow: daemon-scoped compose-up --------------------


try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


pytestmark_yaml = pytest.mark.skipif(
    not _YAML_AVAILABLE, reason="pyyaml not installed",
)


def _drill_yaml() -> dict:
    return _yaml.safe_load(_DR_DRILL.read_text(encoding="utf-8"))


def _start_compose_step() -> dict:
    for step in _drill_yaml()["jobs"]["drill"]["steps"]:
        if step.get("name") == "Start compose on drill Droplet":
            return step
    raise AssertionError("'Start compose on drill Droplet' step missing")


@pytestmark_yaml
def test_drill_start_compose_scopes_to_daemon_service():
    """The drill's compose-up must explicitly target the `daemon` service.
    A bare `compose up -d` would also try to start cloudflared + vector,
    both of which fail on a fresh drill droplet missing their real
    secrets, causing the step to abort before the probe ever runs.
    """
    run = _start_compose_step()["run"]
    assert "compose -f /opt/workflow/deploy/compose.yml up -d daemon" in run, (
        "drill's compose-up must scope to `daemon` service only; a bare "
        "`up -d` would also try to start cloudflared + vector and fail"
    )


@pytestmark_yaml
def test_drill_start_compose_does_not_start_cloudflared():
    """Belt + suspenders: confirm cloudflared isn't explicitly listed."""
    run = _start_compose_step()["run"]
    # The step must not start cloudflared. Any `up -d <...> cloudflared`
    # pattern is wrong. Negative check — this fires if someone later
    # edits the step to add cloudflared.
    assert "cloudflared" not in run, (
        "drill must not start the cloudflared service (no real tunnel "
        "token on drill droplet); probe hits daemon port directly"
    )


def test_drill_probe_still_hits_daemon_port():
    """Sanity: the probe step probes port 8001 directly — if someone
    'fixes' step 14 by routing probe through cloudflared, drill mode
    stops working."""
    text = _DR_DRILL.read_text(encoding="utf-8")
    # The probe URL should target port 8001 directly on the drill IP.
    assert ":8001/mcp" in text, (
        "drill probe must target daemon port 8001 directly, not the "
        "tunnel URL (which wouldn't work without cloudflared anyway)"
    )
