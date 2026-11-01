# Calls tools/workflow_guardrails/health_check.py. That file is the check.
$ErrorActionPreference = "Continue"

$repoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
    Write-Host "Not inside a git repository."
    exit 2
}
Set-Location $repoRoot.Trim()

$pythonBin = $null
foreach ($candidate in @("python", "python3")) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        $pythonBin = $command.Source
        break
    }
}

$scriptPath = Join-Path (Get-Location) "tools/workflow_guardrails/health_check.py"
if (-not $pythonBin) {
    Write-Host "[DID_NOT_RUN] health check"
    Write-Host "  python tools/workflow_guardrails/health_check.py"
    Write-Host "  python is not on PATH"
    Write-Host "pass=0 fail=0 did_not_run=1"
    Write-Host "overall: not success"
    exit 2
}

& $pythonBin $scriptPath @args
exit $LASTEXITCODE
