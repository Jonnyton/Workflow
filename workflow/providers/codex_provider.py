"""Codex / GPT provider -- ``codex exec`` subprocess.

Covered by the ChatGPT Plus subscription.  Different model family from
Claude, making it ideal as a judge when Claude is the writer.
"""

from __future__ import annotations

import asyncio
import shlex
import shutil
import sys
import time

from workflow.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from workflow.providers.base import BaseProvider, ModelConfig, ProviderResponse


def _resolve_codex_cmd() -> tuple[list[str], bool]:
    """Resolve the codex command, handling Windows .cmd/.bat wrappers.

    Returns (base_cmd, use_shell) where base_cmd is the command prefix
    and use_shell indicates whether to use shell execution.
    """
    codex_path = shutil.which("codex")
    if codex_path and sys.platform == "win32" and codex_path.lower().endswith((".cmd", ".bat")):
        return [codex_path], True
    return ["codex"], False


class CodexProvider(BaseProvider):
    """Calls GPT via the ``codex exec`` CLI binary."""

    name = "codex"
    family = "openai"

    async def complete(
        self,
        prompt: str,
        system: str,
        config: ModelConfig,
    ) -> ProviderResponse:
        full_input = f"{system}\n\n{prompt}" if system else prompt

        base_cmd, use_shell = _resolve_codex_cmd()
        cmd = [*base_cmd, "exec", "--full-auto"]

        if use_shell:
            proc = await asyncio.create_subprocess_shell(
                shlex.join(cmd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        start = time.monotonic()

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=full_input.encode("utf-8")),
                timeout=config.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ProviderTimeoutError(
                f"codex exec exceeded {config.timeout}s timeout"
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Quick exit-code-1 => provider unavailable (same heuristic as claude)
        if proc.returncode == 1 and elapsed_ms < 5000:
            raise ProviderUnavailableError(
                "codex exec returned exit code 1 quickly -- likely unavailable"
            )

        if proc.returncode != 0:
            raise ProviderError(
                f"codex exec exit {proc.returncode}: "
                f"{stderr.decode(errors='replace')}"
            )

        text = stdout.decode("utf-8", errors="replace").strip()

        return ProviderResponse(
            text=text,
            provider=self.name,
            model="gpt",
            family=self.family,
            latency_ms=elapsed_ms,
        )
