Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $root = (git rev-parse --show-toplevel 2>$null)
    if (-not $root) {
        throw "Not inside a git repository."
    }
    return $root.Trim()
}

$repoRoot = Get-RepoRoot
$hooksDir = Join-Path $repoRoot ".githooks"

if (-not (Test-Path $hooksDir)) {
    throw "Missing hooks directory: $hooksDir"
}

git -C $repoRoot config core.hooksPath .githooks | Out-Null
$configuredRaw = (git -C $repoRoot config --get core.hooksPath 2>$null)
if (-not $configuredRaw) {
    throw "Failed to read core.hooksPath after setup. Check repository permissions."
}
$configured = $configuredRaw.Trim()

Write-Host "Hooks configured."
Write-Host "Repository: $repoRoot"
Write-Host "core.hooksPath: $configured"
Write-Host "Active hooks:"
Get-ChildItem $hooksDir -File | Select-Object -ExpandProperty Name | ForEach-Object { Write-Host "  - $_" }
