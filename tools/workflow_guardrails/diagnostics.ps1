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
$branch = (git -C $repoRoot branch --show-current).Trim()
$hooksPath = (git -C $repoRoot config --get core.hooksPath 2>$null)

if (-not $hooksPath) {
    $hooksPath = "(not set)"
}
else {
    $hooksPath = $hooksPath.Trim()
}

$staged = @(git -C $repoRoot diff --cached --name-only)
$sensitiveStaged = @($staged | Where-Object { $_ -match "^(?i)Sensitive/" })

Write-Host "Workflow diagnostics"
Write-Host "Repo root      : $repoRoot"
Write-Host "Current branch : $branch"
Write-Host "core.hooksPath : $hooksPath"
Write-Host ""

if ($branch -eq "main" -or $branch -eq "master") {
    Write-Host "Branch status  : BLOCKED for commit/push guardrails" -ForegroundColor Red
}
else {
    Write-Host "Branch status  : OK (feature branch)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Staged files:"
if ($staged.Count -eq 0) {
    Write-Host "  (none)"
}
else {
    $staged | ForEach-Object { Write-Host "  - $_" }
}

Write-Host ""
if ($sensitiveStaged.Count -gt 0) {
    Write-Host "Sensitive staged files detected (commit will be blocked):" -ForegroundColor Red
    $sensitiveStaged | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}
else {
    Write-Host "Sensitive staged files: none detected." -ForegroundColor Green
}

$hookDir = Join-Path $repoRoot ".githooks"
Write-Host ""
Write-Host "Hook files:"
if (-not (Test-Path $hookDir)) {
    Write-Host "  Missing .githooks directory." -ForegroundColor Yellow
}
else {
    Get-ChildItem $hookDir -File | Select-Object -ExpandProperty Name | ForEach-Object { Write-Host "  - $_" }
}
