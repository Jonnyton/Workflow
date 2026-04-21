"""Tests for scripts/bootstrap_add_second_ssh_key.py — bus-factor SSH key seeder."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT = Path(__file__).parent.parent / "scripts" / "bootstrap_add_second_ssh_key.py"


def _load() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_add_second_ssh_key", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bsk = _load()


# ── Arg / env validation ──────────────────────────────────────────────


def test_exits_1_without_host(monkeypatch) -> None:
    monkeypatch.delenv("DROPLET_HOST", raising=False)
    with patch("sys.argv", ["bsk", "--primary-key", "/tmp/k"]), \
         pytest.raises(SystemExit) as exc:
        bsk.main()
    assert exc.value.code == 1


def test_exits_1_without_primary_key(monkeypatch) -> None:
    monkeypatch.delenv("PRIMARY_SSH_KEY_PATH", raising=False)
    with patch("sys.argv", ["bsk", "--host", "1.2.3.4"]), \
         pytest.raises(SystemExit) as exc:
        bsk.main()
    assert exc.value.code == 1


# ── Idempotency guard ─────────────────────────────────────────────────


def test_run_skips_when_secret_already_exists(monkeypatch) -> None:
    monkeypatch.setattr(bsk, "_secret_exists", lambda token, repo: True)
    monkeypatch.setattr(bsk, "_gh_token", lambda t: "tok")
    called = []
    monkeypatch.setattr(bsk, "_append_pubkey", lambda *a: called.append("upload"))
    monkeypatch.setattr(bsk, "_seed_secret", lambda *a: called.append("seed"))
    bsk.run(host="1.2.3.4", primary_key="/tmp/k", repo="owner/repo")
    assert called == []


def test_dry_run_skips_mutations(monkeypatch) -> None:
    monkeypatch.setattr(bsk, "_secret_exists", lambda token, repo: False)
    monkeypatch.setattr(bsk, "_gh_token", lambda t: "tok")
    called = []
    monkeypatch.setattr(bsk, "_seed_secret", lambda *a: called.append("seed"))
    monkeypatch.setattr(bsk, "_append_pubkey", lambda *a: called.append("upload"))
    bsk.run(host="1.2.3.4", primary_key="/tmp/k", repo="owner/repo", dry_run=True)
    assert called == []


# ── SSH append ────────────────────────────────────────────────────────


def _run_with_fake_keygen(monkeypatch, tmp_path, pubkey_present: bool) -> list:
    """Helper: patches keygen + all I/O, returns list of upload calls."""
    monkeypatch.setattr(bsk, "_secret_exists", lambda t, r: False)
    monkeypatch.setattr(bsk, "_gh_token", lambda t: "tok")
    monkeypatch.setattr(bsk, "_pubkey_already_present", lambda *a: pubkey_present)
    uploaded = []
    monkeypatch.setattr(bsk, "_append_pubkey", lambda *a: uploaded.append(True))
    monkeypatch.setattr(bsk, "_seed_secret", lambda *a: None)

    # Write fake key files that the script will read.
    fake_priv = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n"
    fake_pub = "ssh-ed25519 AAAA workflow-backup-key\n"

    real_td = __import__("tempfile").TemporaryDirectory

    original_path_class = Path

    class _PatchedTD:
        def __enter__(self):
            self._real = real_td()
            d = self._real.__enter__()
            (original_path_class(d) / "second_key").write_text(fake_priv)
            (original_path_class(d) / "second_key.pub").write_text(fake_pub)
            return d

        def __exit__(self, *args):
            return self._real.__exit__(*args)

    monkeypatch.setattr("tempfile.TemporaryDirectory", _PatchedTD)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        bsk.run(host="1.2.3.4", primary_key="/tmp/k", repo="owner/repo")
    return uploaded


def test_pubkey_already_present_skips_upload(monkeypatch, tmp_path) -> None:
    uploaded = _run_with_fake_keygen(monkeypatch, tmp_path, pubkey_present=True)
    assert uploaded == []


def test_upload_attempted_when_pubkey_absent(monkeypatch, tmp_path) -> None:
    uploaded = _run_with_fake_keygen(monkeypatch, tmp_path, pubkey_present=False)
    assert uploaded == [True]


# ── GH token resolution ───────────────────────────────────────────────


def test_gh_token_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "env-token")
    assert bsk._gh_token(None) == "env-token"


def test_gh_token_explicit_arg_takes_priority(monkeypatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "env-token")
    assert bsk._gh_token("explicit-token") == "explicit-token"


# ── SSH helpers ───────────────────────────────────────────────────────


def test_pubkey_already_present_parses_yes(monkeypatch) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="YES\n", stderr="")
        result = bsk._pubkey_already_present("1.2.3.4", "/tmp/k", "AAAA")
    assert result is True


def test_pubkey_not_present_parses_no(monkeypatch) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="NO\n", stderr="")
        result = bsk._pubkey_already_present("1.2.3.4", "/tmp/k", "AAAA")
    assert result is False


def test_append_pubkey_raises_on_nonzero(monkeypatch) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="permission denied")
        with pytest.raises(RuntimeError, match="failed to append"):
            bsk._append_pubkey("1.2.3.4", "/tmp/k", "ssh-ed25519 AAAA backup")


# ── Script file exists ────────────────────────────────────────────────


def test_script_exists() -> None:
    assert _SCRIPT.is_file(), f"missing: {_SCRIPT}"


# ── Resilience audit updated ──────────────────────────────────────────


def test_audit_mentions_dual_key() -> None:
    audit = Path(__file__).parent.parent / "docs" / "ops" / "host-off-resilience-audit.md"
    text = audit.read_text(encoding="utf-8")
    assert "DO_SSH_KEY_BACKUP" in text or "dual-key" in text or "bus factor" in text.lower()


def test_audit_mentions_second_key_script() -> None:
    audit = Path(__file__).parent.parent / "docs" / "ops" / "host-off-resilience-audit.md"
    text = audit.read_text(encoding="utf-8")
    assert "bootstrap_add_second_ssh_key" in text


def test_secret_name_constant() -> None:
    assert bsk.SECRET_NAME == "DO_SSH_KEY_BACKUP"
