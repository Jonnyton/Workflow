$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root ".agents\\skills"
# Claude Code is the only mirror target. Codex + project-visible agents read
# `.agents/skills/` directly (AGENTS.md "Project Skills"), so there is no
# `.codex/skills` mirror by design -- do not add one here.
$targets = @(
    (Join-Path $root ".claude\\skills")
)

if (!(Test-Path $source)) {
    throw "Canonical skills directory not found: $source"
}

foreach ($target in $targets) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Get-ChildItem -Force $target | Remove-Item -Recurse -Force
    Copy-Item -Recurse -Force (Join-Path $source "*") $target
}

$validator = Join-Path $root "scripts\validate_skills.py"
python $validator --root $root

Write-Output "Skill mirrors refreshed from .agents\\skills"
