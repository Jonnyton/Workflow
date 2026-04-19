# Install Workflow's repo-level git hooks into .git/hooks/.
#
# Hooks live canonically at scripts/git-hooks/ and are copied into
# .git/hooks/ on install. Re-run this script whenever the canonical
# hooks change. Zero dependencies beyond git + PowerShell.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root "scripts\git-hooks"
$target = Join-Path $root ".git\hooks"

if (!(Test-Path $source)) {
    throw "Canonical hooks dir not found: $source"
}
if (!(Test-Path $target)) {
    throw "No .git/hooks dir found — is this a git worktree? $target"
}

$installed = 0
Get-ChildItem -File $source | ForEach-Object {
    $name = $_.Name
    $destPath = Join-Path $target $name
    Copy-Item -Force $_.FullName $destPath
    # On Windows, git-bash respects the file contents regardless of
    # NTFS exec bit, so no chmod needed. On POSIX, mark executable.
    if ($IsLinux -or $IsMacOS) {
        chmod +x $destPath
    }
    $installed++
    Write-Output "Installed: $name"
}

Write-Output "$installed git hook(s) installed in $target"
