"""bootstrap_add_second_ssh_key.py — add a backup ed25519 SSH key to the Droplet.

Raises bus factor from 1 to 2 for Droplet SSH access (HD-1 close action).

What it does (idempotent):
  1. Generates a new ed25519 keypair in a temp dir.
  2. SSHes into the Droplet using the existing primary key and appends the
     new public key to /root/.ssh/authorized_keys (skip if already present).
  3. Seeds the new private key as a GH Actions secret (DO_SSH_KEY_BACKUP)
     using the gh_seed_secret pattern (git credential token; skip if secret
     already set).
  4. Erases the local ephemeral key files.

Exit codes
----------
0   Success (or already-seeded and idempotency guard triggered).
1   Required env / arg missing.
2   ssh-keygen failed.
3   SSH upload to Droplet failed.
4   GH secret seeding failed.

Usage
-----
    python scripts/bootstrap_add_second_ssh_key.py \\
        --host 161.35.237.133 \\
        --primary-key ~/.ssh/workflow_deploy_ed25519 \\
        --repo Jonnyton/Workflow

Environment (override CLI for CI use):
    DROPLET_HOST          Droplet IP/hostname.
    PRIMARY_SSH_KEY_PATH  Path to the existing private key for initial SSH.
    GH_REPO               GitHub repo slug (owner/name).
    GH_TOKEN              GitHub token (falls back to git credential helper).
    DRY_RUN               Set to "1" to skip mutations (useful for CI plan).

Stdlib + subprocess only — no third-party deps.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from base64 import b64encode
from pathlib import Path

DEFAULT_REPO = "Jonnyton/Workflow"
SECRET_NAME = "DO_SSH_KEY_BACKUP"
AUTHORIZED_KEYS = "/root/.ssh/authorized_keys"


# ── GH helpers (mirrors gh_seed_secret.py pattern) ───────────────────

def _git_token() -> str:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="url=https://github.com\n\n",
        capture_output=True, text=True, timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git credential fill failed: {proc.stderr.strip()}")
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    raise RuntimeError("no password in git credential output")


def _gh_token(env_token: str | None) -> str:
    if env_token:
        return env_token
    t = os.environ.get("GH_TOKEN", "").strip()
    if t:
        return t
    return _git_token()


def _gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "workflow-second-key/1.0",
    }


def _gh_get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers=_gh_headers(token))
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _secret_exists(token: str, repo: str) -> bool:
    url = f"https://api.github.com/repos/{repo}/actions/secrets/{SECRET_NAME}"
    try:
        _gh_get(url, token)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def _seed_secret(token: str, repo: str, private_key_pem: str) -> None:
    # Fetch the repo's public encryption key.
    key_info = _gh_get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        token,
    )
    gh_pub_key_b64 = key_info["key"]
    key_id = key_info["key_id"]

    # Encrypt with libsodium (via PyNaCl if available, else fallback message).
    try:
        from base64 import b64decode  # noqa: PLC0415  # isort: skip
        from nacl.public import PublicKey, SealedBox  # type: ignore[import]  # noqa: PLC0415  # isort: skip
        pub = PublicKey(b64decode(gh_pub_key_b64))
        box = SealedBox(pub)
        encrypted = b64encode(box.encrypt(private_key_pem.encode())).decode()
    except ImportError:
        # PyNaCl not available — fall back to gh CLI if present.
        import shutil
        if not shutil.which("gh"):
            raise RuntimeError(
                "PyNaCl not installed and gh CLI not found. "
                "Install PyNaCl (`pip install pynacl`) or the gh CLI."
            )
        proc = subprocess.run(
            ["gh", "secret", "set", SECRET_NAME,
             "--repo", repo, "--body", private_key_pem],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh secret set failed: {proc.stderr.strip()}")
        return

    body = json.dumps({"encrypted_value": encrypted, "key_id": key_id}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/secrets/{SECRET_NAME}",
        data=body,
        method="PUT",
        headers={**_gh_headers(token), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (201, 204):
            raise RuntimeError(f"secret PUT returned {resp.status}")


# ── SSH helpers ───────────────────────────────────────────────────────

def _ssh_run(host: str, primary_key: str, command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "ssh", "-i", primary_key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "BatchMode=yes",
            f"root@{host}",
            command,
        ],
        capture_output=True, text=True,
    )


def _pubkey_already_present(host: str, primary_key: str, pubkey_line: str) -> bool:
    result = _ssh_run(host, primary_key,
                      f"grep -qF '{pubkey_line}' {AUTHORIZED_KEYS} && echo YES || echo NO")
    return result.returncode == 0 and "YES" in result.stdout


def _append_pubkey(host: str, primary_key: str, pubkey_line: str) -> None:
    result = _ssh_run(
        host, primary_key,
        f"echo '{pubkey_line}' >> {AUTHORIZED_KEYS} && chmod 600 {AUTHORIZED_KEYS}",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"failed to append pubkey to {AUTHORIZED_KEYS}: {result.stderr.strip()}"
        )


# ── Main ──────────────────────────────────────────────────────────────

def run(
    host: str,
    primary_key: str,
    repo: str,
    dry_run: bool = False,
    gh_token: str | None = None,
) -> None:
    token = _gh_token(gh_token)

    print(f"[second-key] host:    {host}")
    print(f"[second-key] repo:    {repo}")
    print(f"[second-key] secret:  {SECRET_NAME}")

    # Check if secret already seeded (idempotency).
    if _secret_exists(token, repo):
        print(f"[second-key] {SECRET_NAME} already exists in GH Actions — skipping.")
        return

    if dry_run:
        print("[second-key] DRY_RUN=1 — would generate keypair, upload, seed secret.")
        return

    # Generate keypair in temp dir.
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "second_key"
        pub_path = Path(tmpdir) / "second_key.pub"

        result = subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "",
             "-C", "workflow-backup-key", "-f", str(key_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: ssh-keygen failed: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(2)

        pubkey_line = pub_path.read_text().strip()
        private_pem = key_path.read_text()

        print(f"[second-key] generated key: {pubkey_line[:50]}...")

        # Upload to Droplet authorized_keys.
        if _pubkey_already_present(host, primary_key, pubkey_line.split()[1]):
            print("[second-key] pubkey already in authorized_keys — skipping SSH upload.")
        else:
            print(f"[second-key] appending pubkey to {host}:{AUTHORIZED_KEYS}...")
            try:
                _append_pubkey(host, primary_key, pubkey_line)
            except RuntimeError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                sys.exit(3)
            print("[second-key] pubkey uploaded OK.")

        # Seed GH secret.
        print(f"[second-key] seeding {SECRET_NAME} in {repo}...")
        try:
            _seed_secret(token, repo, private_pem)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(4)
        print(f"[second-key] {SECRET_NAME} seeded OK.")

        # Private key is automatically erased when tmpdir exits context.

    print("[second-key] done. Bus factor = 2.")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Add a backup ed25519 SSH key to the Droplet + seed GH secret."
    )
    p.add_argument("--host",
                   default=os.environ.get("DROPLET_HOST", ""),
                   help="Droplet IP/hostname")
    p.add_argument("--primary-key",
                   default=os.environ.get("PRIMARY_SSH_KEY_PATH", ""),
                   help="Path to existing primary private key for initial SSH access")
    p.add_argument("--repo",
                   default=os.environ.get("GH_REPO", DEFAULT_REPO),
                   help=f"GitHub repo (default: {DEFAULT_REPO})")
    p.add_argument("--gh-token",
                   default=os.environ.get("GH_TOKEN", ""),
                   help="GitHub token (default: git credential helper)")
    args = p.parse_args()

    if not args.host:
        print("ERROR: --host or DROPLET_HOST required", file=sys.stderr)
        sys.exit(1)
    if not args.primary_key:
        print("ERROR: --primary-key or PRIMARY_SSH_KEY_PATH required", file=sys.stderr)
        sys.exit(1)

    dry_run = os.environ.get("DRY_RUN", "0").strip() == "1"
    run(
        host=args.host,
        primary_key=args.primary_key,
        repo=args.repo,
        dry_run=dry_run,
        gh_token=args.gh_token or None,
    )


if __name__ == "__main__":
    main()
