$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root ".agents\\skills"
$targets = @(
    (Join-Path $root ".claude\\skills"),
    (Join-Path $root ".codex\\skills")
)

if (!(Test-Path $source)) {
    throw "Canonical skills directory not found: $source"
}

foreach ($target in $targets) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Get-ChildItem -Force $target | Remove-Item -Recurse -Force
    Copy-Item -Recurse -Force (Join-Path $source "*") $target
}

Write-Output "Skill mirrors refreshed from .agents\\skills"
