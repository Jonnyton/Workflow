import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "cowork-bootstrap.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_cowork_bootstrap_uses_gh_token_from_environment(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    git_log = tmp_path / "git.log"
    (fake_bin / "git").write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> {git_log}\n",
        encoding="utf-8",
    )
    (fake_bin / "gh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (fake_bin / "git").chmod(0o755)
    (fake_bin / "gh").chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["GH_TOKEN"] = "vendor-token"
    Path(env["HOME"]).mkdir()

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (Path(env["HOME"]) / ".git-credentials").read_text(
        encoding="utf-8"
    ) == "https://Jonnyton:vendor-token@github.com\n"
    assert (Path(env["HOME"]) / ".cowork-env").read_text(
        encoding="utf-8"
    ) == "GH_TOKEN=vendor-token\n"
    assert "credential.helper store" in git_log.read_text(encoding="utf-8")


def test_secrets_vendor_key_list_includes_sandbox_push_token() -> None:
    keys = {
        line.split()[0]
        for line in (REPO_ROOT / "scripts" / "secrets_keys.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "GH_TOKEN" in keys
