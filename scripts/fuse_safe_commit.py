#!/usr/bin/env python3
"""Atomic, scope-verified git commit builder for FUSE-locked checkouts.

Background: Cowork's FUSE mount makes ``git add`` + ``git commit`` racy
against the lock files. The workaround is git plumbing
(``hash-object`` + ``update-index`` + ``write-tree`` + ``commit-tree``)
with ``GIT_INDEX_FILE`` pointing at a temp path. But there's a sharp-edge
in that pattern: ``cp .git/index $GIT_INDEX_FILE`` snapshots the LOCAL
staged tree, which can be many commits behind ``origin/main`` if the
checkout has drifted. The resulting commit looks small (one file added)
but actually regresses every file that landed on origin/main between
the local index timestamp and the push.

This wrapper makes the safe pattern the easy pattern. It always reads
the tree fresh from a known-good base ref, applies only the explicit
file changes you ask for, and refuses to produce the commit if the
resulting diff scope exceeds your declared expectation.

Spec reference: ``.agents/skills/loop-uptime-maintenance/incidents/2026-05-04-cowork-stale-index-regression.md``
(skill discipline incident #3 — 730-file regression caused by
``cp .git/index`` pattern).

Usage:
    python3 scripts/fuse_safe_commit.py \\
        --base-ref origin/main \\
        --file PATH:CONTENT_PATH [--file PATH:CONTENT_PATH ...] \\
        --message "commit message" \\
        --max-files 5

What it does:
  1. Creates a fresh temp ``GIT_INDEX_FILE`` (does NOT copy ``.git/index``).
  2. ``git read-tree <base-ref>`` to seed it from canonical state.
  3. For each ``--file`` arg, hashes the content blob and ``update-index --add``.
  4. ``git write-tree`` to produce the new tree object.
  5. ``git commit-tree <tree> -p <base-ref-sha> -F message`` to produce the commit.
  6. Computes ``git diff --stat <base-ref>..<new-commit>`` and parses
     the file count.
  7. **Aborts** if file count exceeds ``--max-files``. (Default: same as
     count of ``--file`` args provided.)
  8. Prints the new commit hash to stdout for caller use.
  9. Optionally updates a local ref via ``--update-ref`` and prepares
     a push command (caller still does the actual push so multi-commit
     atomicity stays in caller's hands).

Why this is safer than raw plumbing:
  - Fresh index every time — never inherits stale local state.
  - Diff scope verified BEFORE the commit hash is returned.
  - Clear failure mode: refuses to mint commits that regress files
    you didn't ask to touch.
  - Single CLI entrypoint so the discipline is the default path.

Why the same shape as fuse_safe_write.py:
  - "Write the right thing or fail loudly" instead of "succeed quietly
    while corrupting state" — same safety stance applied to commits.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile


_GIT_DIFF_STAT_FOOTER = re.compile(
    r"\s*(\d+)\s+files?\s+changed",
    re.IGNORECASE,
)


def _run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Wrap subprocess.run with consistent error handling."""
    proc = subprocess.run(
        cmd,
        env=env,
        cwd=cwd,
        check=False,
        capture_output=capture,
        text=True,
    )
    if check and proc.returncode != 0:
        msg = (
            f"FUSE_SAFE_COMMIT: command failed (exit={proc.returncode}): "
            f"{' '.join(cmd)}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
        raise SystemExit(msg)
    return proc


def _parse_file_arg(raw: str) -> tuple[str, str]:
    """Parse 'REPO_PATH:CONTENT_PATH' into a tuple. REPO_PATH is the
    in-tree path; CONTENT_PATH is a local file holding the new contents."""
    if ":" not in raw:
        raise SystemExit(
            f"FUSE_SAFE_COMMIT: --file must be REPO_PATH:CONTENT_PATH; got {raw!r}"
        )
    # Split on the LAST colon so Windows-style content paths work.
    repo_path, _, content_path = raw.rpartition(":")
    if not repo_path or not content_path:
        raise SystemExit(
            f"FUSE_SAFE_COMMIT: --file value must have non-empty repo_path "
            f"AND content_path; got {raw!r}"
        )
    if not os.path.isfile(content_path):
        raise SystemExit(
            f"FUSE_SAFE_COMMIT: content_path does not exist: {content_path!r}"
        )
    return repo_path, content_path


def _resolve_ref(repo_root: str, ref: str) -> str:
    """git rev-parse <ref> → 40-char sha or fail loudly."""
    proc = _run(["git", "rev-parse", ref], cwd=repo_root)
    sha = proc.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise SystemExit(
            f"FUSE_SAFE_COMMIT: ref {ref!r} did not resolve to a sha; got {sha!r}"
        )
    return sha


def _diff_stat_files(repo_root: str, base_sha: str, new_sha: str) -> int:
    """Parse the file-count from `git diff --stat`."""
    proc = _run(
        ["git", "diff", "--stat", f"{base_sha}..{new_sha}"],
        cwd=repo_root,
    )
    # Last non-empty line is "N files changed, ..." or "N file changed, ...".
    last = ""
    for line in reversed(proc.stdout.splitlines()):
        if line.strip():
            last = line
            break
    m = _GIT_DIFF_STAT_FOOTER.search(last)
    if not m:
        # Empty diff — no files changed.
        return 0
    return int(m.group(1))


def build_commit(
    *,
    repo_root: str,
    base_ref: str,
    files: list[tuple[str, str]],
    message: str,
    max_files: int | None = None,
) -> str:
    """Build a commit using the safe pattern. Returns the new commit sha."""
    base_sha = _resolve_ref(repo_root, base_ref)

    # Use a fresh temp index — DO NOT copy .git/index (the bug we're
    # preventing).
    fd, index_path = tempfile.mkstemp(
        prefix=".fuse_safe_commit_idx_",
        suffix=".idx",
    )
    os.close(fd)
    os.unlink(index_path)  # git read-tree will create it.

    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = index_path

    try:
        # Seed index from canonical base — fresh, no drift.
        _run(["git", "read-tree", base_sha], env=env, cwd=repo_root)

        # Hash each blob + add to fresh index.
        for repo_path, content_path in files:
            with open(content_path, "rb") as f:
                content = f.read()
            proc = subprocess.run(
                ["git", "hash-object", "-w", "--stdin"],
                env=env,
                cwd=repo_root,
                input=content,
                capture_output=True,
                check=True,
            )
            blob_sha = proc.stdout.decode("utf-8").strip()
            if not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
                raise SystemExit(
                    f"FUSE_SAFE_COMMIT: hash-object did not return a sha; got {blob_sha!r}"
                )
            _run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"100644,{blob_sha},{repo_path}",
                ],
                env=env,
                cwd=repo_root,
            )

        # Write tree + commit.
        proc = _run(["git", "write-tree"], env=env, cwd=repo_root)
        tree_sha = proc.stdout.strip()

        proc = subprocess.run(
            ["git", "commit-tree", tree_sha, "-p", base_sha, "-F", "-"],
            env=env,
            cwd=repo_root,
            input=message,
            capture_output=True,
            text=True,
            check=True,
        )
        new_sha = proc.stdout.strip()

        # Verify scope BEFORE returning the hash.
        actual_files = _diff_stat_files(repo_root, base_sha, new_sha)
        cap = max_files if max_files is not None else len(files)
        if actual_files > cap:
            raise SystemExit(
                f"FUSE_SAFE_COMMIT: SCOPE VIOLATION — diff touches {actual_files} "
                f"files but expected ≤ {cap} (--max-files / --file count). "
                f"Refusing to return commit hash {new_sha!r} — base may be stale or "
                f"file paths may collide with index entries from a different tree. "
                f"Rerun with explicit --max-files if intentional."
            )

        return new_sha

    finally:
        # Clean up temp index.
        try:
            os.unlink(index_path)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a git commit safely from a known-good base ref",
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Canonical base ref to read tree from (e.g., origin/main)",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        required=True,
        help="REPO_PATH:CONTENT_PATH pair — one --file per file to add. Repeatable.",
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Commit message",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Max files allowed in resulting diff. Default: count of --file args.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root (default: cwd)",
    )
    parser.add_argument(
        "--update-ref",
        default=None,
        help="If set, write the resulting commit sha to this local ref path "
             "(e.g., .git/refs/heads/main). Caller still pushes.",
    )
    args = parser.parse_args()

    files = [_parse_file_arg(raw) for raw in args.file]
    new_sha = build_commit(
        repo_root=args.repo_root,
        base_ref=args.base_ref,
        files=files,
        message=args.message,
        max_files=args.max_files,
    )

    if args.update_ref:
        # Use fuse_safe_write for the ref update so we stay in the
        # safe-pattern family.
        ref_path = args.update_ref
        # Allow caller to pass either the relative or absolute ref path.
        if not os.path.isabs(ref_path):
            ref_path = os.path.join(args.repo_root, ref_path)
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            suffix=".ref",
        ) as tf:
            tf.write(new_sha + "\n")
            tmp_ref = tf.name
        # If fuse_safe_write.py exists, use it; otherwise direct atomic write.
        fuse_safe_write = os.path.join(args.repo_root, "scripts", "fuse_safe_write.py")
        if os.path.isfile(fuse_safe_write):
            _run(
                [
                    sys.executable,
                    fuse_safe_write,
                    "--path",
                    ref_path,
                    "--content-from",
                    tmp_ref,
                ],
            )
        else:
            shutil.copy(tmp_ref, ref_path)
        os.unlink(tmp_ref)

    print(new_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
                                                                                                                                                                                                                                                             