"""Claude provider -- ``claude -p`` subprocess.

Covered by the Claude Max subscription.  No API credits consumed.
Exit code 1 within 5 seconds signals API unavailability and triggers
a sticky cooldown in the router.
"""

from __future__ import annotations

import asyncio
import json
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


def _resolve_claude_cmd() -> tuple[list[str], bool]:
    """Resolve the claude command, handling Windows .cmd/.bat wrappers.

    Returns (base_cmd, use_shell) where base_cmd is the command prefix
    and use_shell indicates whether to use shell execution.
    """
    claude_path = shutil.which("claude")
    if claude_path and sys.platform == "win32" and claude_path.lower().endswith((".cmd", ".bat")):
        return [claude_path], True
    return ["claude"], False


class ClaudeProvider(BaseProvider):
    """Calls Claude via the ``claude -p`` CLI binary."""

    name = "claude-code"
    family = "anthropic"

    async def complete(
        self,
        prompt: str,
        system: str,
        config: ModelConfig,
    ) -> ProviderResponse:
        base_cmd, use_shell = _resolve_claude_cmd()
        cmd = [*base_cmd, "-p"]
        if system:
            cmd.extend(["--system-prompt", system])

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
                proc.communicate(input=prompt.encode("utf-8")),
                timeout=config.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ProviderTimeoutError(
                f"claude -p exceeded {config.timeout}s timeout"
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Exit code 1 within 5 seconds => API unavailable (sticky cooldown)
        if proc.returncode == 1 and elapsed_ms < 5000:
            raise ProviderUnavailableError(
                "claude -p returned exit code 1 quickly -- API likely unavailable"
            )

        if proc.returncode != 0:
            raise ProviderError(
                f"claude -p exit {proc.returncode}: {stderr.decode(errors='replace')}"
            )

        text = stdout.decode("utf-8", errors="replace").strip()

        return ProviderResponse(
            text=text,
            provider=self.name,
            model="claude",
            family=self.family,
            latency_ms=elapsed_ms,
        )

    async def complete_json(
        self,
        prompt: str,
        system: str,
        config: ModelConfig,
    ) -> ProviderResponse:
        """Call with ``--output-format json`` for structured output."""
        base_cmd, use_shell = _resolve_claude_cmd()
        cmd = [*base_cmd, "-p", "--output-format", "json"]
        if system:
            cmd.extend(["--system-prompt", system])

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
                proc.communicate(input=prompt.encode("utf-8")),
                timeout=config.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ProviderTimeoutError("claude -p (json) timed out")

        elapsed_ms = (time.monotonic() - start) * 1000

        if proc.returncode == 1 and elapsed_ms < 5000:
            raise ProviderUnavailableError(
                "claude -p (json) returned exit code 1 quickly"
            )

        if proc.returncode != 0:
            raise ProviderError(
                f"claude -p (json) exit {proc.returncode}: "
                f"{stderr.decode(errors='replace')}"
            )

        raw = stdout.decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        text = parsed.get("result", raw)

        return ProviderResponse(
            text=text,
            provider=self.name,
            model="claude",
            family=self.family,
            latency_ms=elapsed_ms,
        )
