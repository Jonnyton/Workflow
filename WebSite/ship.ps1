# ship.ps1 — push the prepared website-ship.bundle to GitHub.
# Run from Windows PowerShell. Uses YOUR git credentials (sandbox has none).
#
# What it does:
#   1. Clones a fresh copy of Jonnyton/Workflow main into $env:TEMP\wf-ship
#      (avoids touching the in-progress work in C:\Users\Jonathan\Projects\Workflow)
#   2. Fetches the bundle Claude prepared (WebSite/website-ship.bundle)
#   3. Pushes the website/ship-prototype branch to origin
#   4. Prints the GitHub URL where you can open a PR or merge to main
#
# After merge to main, deploy-site.yml fires automatically and ships to
# tinyassets.io via GitHub Pages.

$ErrorActionPreference = 'Stop'
$bundle = Join-Path $PSScriptRoot 'website-ship.bundle'
if (-not (Test-Path $bundle)) {
  Write-Error "Bundle not found at $bundle"
  exit 1
}

$workdir = Join-Path $env:TEMP 'wf-ship'
if (Test-Path $workdir) {
  Write-Host "Removing stale $workdir ..."
  Remove-Item -Recurse -Force $workdir
}

Write-Host "1/4  Cloning Jonnyton/Workflow main into $workdir ..."
git clone --depth=1 --branch=main https://github.com/Jonnyton/Workflow.git $workdir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location $workdir

Write-Host "2/4  Fetching bundle $bundle ..."
git fetch $bundle 'refs/heads/website/ship-prototype:refs/heads/website/ship-prototype'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "3/4  Pushing branch website/ship-prototype to origin ..."
git push -u origin website/ship-prototype
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "4/4  Pushed. Open a PR or fast-forward main:"
Write-Host "     https://github.com/Jonnyton/Workflow/compare/main...website/ship-prototype?expand=1"
Write-Host ""
Write-Host "After merge to main, .github/workflows/deploy-site.yml deploys to GitHub Pages"
Write-Host "and tinyassets.io serves the new site via Cloudflare."
