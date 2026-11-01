# Read-only health check for skirt_steak.
#
# Windows twin of health-check.sh. Same outcomes: PASS, FAIL, DID_NOT_RUN.
# Does not install packages, change git config, stage files, or contact the
# network. Does not run setup-hooks or preflight -DryRunSync.
#
# Exit 0 only when every check is PASS.
# Exit 1 when any check is FAIL.
# Exit 2 when nothing failed but at least one check did not run.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

if ($args.Count -gt 0) {
    Write-Host "health-check.ps1 takes no arguments and does not modify the repo."
    exit 2
}

$repoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
    Write-Host "Not inside a git repository."
    exit 2
}
$repoRoot = $repoRoot.Trim()
Set-Location $repoRoot

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:NO_COLOR = "1"
$pycachePrefix = Join-Path ([System.IO.Path]::GetTempPath()) ("skirt-steak-health-pycache-" + $PID)
$env:PYTHONPYCACHEPREFIX = $pycachePrefix

$pythonBin = $null
foreach ($candidate in @("python", "python3")) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($command) {
        $pythonBin = $command.Source
        break
    }
}

$script:PassCount = 0
$script:FailCount = 0
$script:DidNotRunCount = 0

function Write-CheckOutput {
    param([string]$Text, [switch]$Full)
    if (-not $Text) {
        return
    }
    Write-Host "  output:"
    $lines = $Text -split "`r?`n"
    if (-not $Full -and $lines.Count -gt 40) {
        $lines = $lines | Select-Object -Last 40
    }
    foreach ($line in $lines) {
        if ($line -ne "") {
            Write-Host "    $line"
        }
    }
}

function Add-Pass {
    param([string]$Role, [string]$Name, [string]$CommandDisplay, [string]$OutputText, [switch]$FullOutput)
    Write-Host "[PASS] ($Role) $Name"
    Write-Host "  command: $CommandDisplay"
    Write-CheckOutput -Text $OutputText -Full:$FullOutput
    $script:PassCount = $script:PassCount + 1
}

function Add-Fail {
    param([string]$Role, [string]$Name, [string]$CommandDisplay, [int]$ExitCode, [string]$OutputText, [switch]$FullOutput)
    Write-Host "[FAIL] ($Role) $Name"
    Write-Host "  command: $CommandDisplay"
    Write-Host "  exit: $ExitCode"
    if ($FullOutput) {
        Write-CheckOutput -Text $OutputText -Full
    }
    else {
        Write-CheckOutput -Text $OutputText
    }
    $script:FailCount = $script:FailCount + 1
}

function Add-DidNotRun {
    param([string]$Role, [string]$Name, [string]$CommandDisplay, [string]$Reason)
    Write-Host "[DID_NOT_RUN] ($Role) $Name"
    Write-Host "  command: $CommandDisplay"
    Write-Host "  reason: $Reason"
    $script:DidNotRunCount = $script:DidNotRunCount + 1
}

function Invoke-Native {
    param([scriptblock]$Command)
    $logPath = [System.IO.Path]::GetTempFileName()
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Command *> $logPath
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }
    $ErrorActionPreference = $previous
    $output = ""
    if (Test-Path $logPath) {
        $output = [string](Get-Content -Raw -Path $logPath -ErrorAction SilentlyContinue)
        Remove-Item -Force $logPath
    }
    $result = @{ ExitCode = [int]$exitCode; Output = $output }
    return ,$result
}

function Invoke-Recorded {
    param(
        [string]$Role,
        [string]$Name,
        [string]$CommandDisplay,
        [scriptblock]$Command
    )
    $result = Invoke-Native -Command $Command
    if ($result.ExitCode -eq 0) {
        if ($Role -eq "workflow") {
            Add-Pass -Role $Role -Name $Name -CommandDisplay $CommandDisplay -OutputText $result.Output -FullOutput
        }
        else {
            Add-Pass -Role $Role -Name $Name -CommandDisplay $CommandDisplay -OutputText $result.Output
        }
    }
    elseif ($Role -eq "workflow") {
        Add-Fail -Role $Role -Name $Name -CommandDisplay $CommandDisplay -ExitCode $result.ExitCode -OutputText $result.Output -FullOutput
    }
    else {
        Add-Fail -Role $Role -Name $Name -CommandDisplay $CommandDisplay -ExitCode $result.ExitCode -OutputText $result.Output
    }
}

Write-Host "health-check (read-only)"
Write-Host "repo: $repoRoot"
$branch = (git branch --show-current).Trim()
Write-Host "branch: $branch"
if ($pythonBin) {
    Write-Host "python: $pythonBin"
}
else {
    Write-Host "python: missing"
}
Write-Host ""

$treeBefore = (git status --porcelain | Out-String).TrimEnd()

$syntaxProgram = @'
import pathlib
import py_compile
import shutil
import sys
import tempfile

files = sorted(pathlib.Path("python").rglob("*.py"))
if not files:
    sys.exit("no Python files under python/")
temporary = tempfile.mkdtemp(prefix="skirt-steak-py-compile-")
try:
    for source_path in files:
        target = pathlib.Path(temporary) / (str(source_path).replace("/", "_") + ".pyc")
        py_compile.compile(str(source_path), cfile=str(target), doraise=True)
finally:
    shutil.rmtree(temporary, ignore_errors=True)
print("compiled %d files" % len(files))
'@

if (-not $pythonBin) {
    Add-DidNotRun "blocking" "syntax check (py_compile)" "python -c <script>" "python is not on PATH"
    Add-DidNotRun "blocking" "board secretary unit tests" "python -m unittest discover -s python/msjc_board_secretary/tests -p test_*.py" "python is not on PATH"
    Add-DidNotRun "blocking" "decision log unit tests" "python -m unittest discover -s python/decision_log/tests -p test_*.py" "python is not on PATH"
    Add-DidNotRun "blocking" "fanfic story doctor tests" "python -m pytest -q -p no:cacheprovider (cwd: python/fanfic_story_doctor)" "python is not on PATH"
    Add-DidNotRun "blocking" "ruff fail-fast and naming" "python -m ruff check python" "python is not on PATH"
    Add-DidNotRun "advisory" "black --check" "python -m black --check python" "python is not on PATH"
    Add-DidNotRun "advisory" "pylint" "python -m pylint python/*.py" "python is not on PATH"
}
else {
    $syntaxCommand = "$pythonBin -c <script>"
    Invoke-Recorded "blocking" "syntax check (py_compile)" $syntaxCommand { & $pythonBin -c $syntaxProgram }
    Write-Host "  script:"
    foreach ($syntaxLine in ($syntaxProgram -split "`r?`n")) {
        Write-Host "    $syntaxLine"
    }

    $boardCommand = "$pythonBin -m unittest discover -s python/msjc_board_secretary/tests -p test_*.py"
    Invoke-Recorded "blocking" "board secretary unit tests" $boardCommand {
        & $pythonBin -m unittest discover -s python/msjc_board_secretary/tests -p "test_*.py"
    }

    $decisionCommand = "$pythonBin -m unittest discover -s python/decision_log/tests -p test_*.py"
    & $pythonBin -c "import duckdb" *> $null
    if ($LASTEXITCODE -eq 0) {
        Invoke-Recorded "blocking" "decision log unit tests" $decisionCommand {
            & $pythonBin -m unittest discover -s python/decision_log/tests -p "test_*.py"
        }
    }
    else {
        Add-DidNotRun "blocking" "decision log unit tests" $decisionCommand "duckdb is not importable, so the tests were not started"
    }

    $fanficDir = Join-Path $repoRoot "python/fanfic_story_doctor"
    $fanficCommand = "cd $fanficDir && $pythonBin -m pytest -q -p no:cacheprovider"
    & $pythonBin -c "import pytest, yaml, jsonschema" *> $null
    if ($LASTEXITCODE -eq 0) {
        Invoke-Recorded "blocking" "fanfic story doctor tests" $fanficCommand {
            Push-Location $fanficDir
            try {
                & $pythonBin -m pytest -q -p no:cacheprovider
            }
            finally {
                Pop-Location
            }
        }
    }
    else {
        Add-DidNotRun "blocking" "fanfic story doctor tests" $fanficCommand "pytest, PyYAML, or jsonschema is not importable, so the tests were not started"
    }

    $ruffCommand = "$pythonBin -m ruff check python"
    & $pythonBin -m ruff --version *> $null
    if ($LASTEXITCODE -eq 0) {
        Invoke-Recorded "blocking" "ruff fail-fast and naming" $ruffCommand { & $pythonBin -m ruff check python }
    }
    else {
        Add-DidNotRun "blocking" "ruff fail-fast and naming" $ruffCommand "ruff is not installed for this interpreter"
    }

    $blackCommand = "$pythonBin -m black --check python"
    & $pythonBin -m black --version *> $null
    if ($LASTEXITCODE -eq 0) {
        Invoke-Recorded "advisory" "black --check" $blackCommand { & $pythonBin -m black --check python }
    }
    else {
        Add-DidNotRun "advisory" "black --check" $blackCommand "black is not installed for this interpreter"
    }

    $pylintFiles = @(Get-ChildItem -Path (Join-Path $repoRoot "python") -Filter "*.py" -File | Sort-Object Name | ForEach-Object { $_.FullName })
    if ($pylintFiles.Count -eq 0) {
        Add-DidNotRun "advisory" "pylint" "python -m pylint" "no Python files directly under python/"
    }
    else {
        & $pythonBin -m pylint --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $pylintCommand = "$pythonBin -m pylint $($pylintFiles -join ' ')"
            Invoke-Recorded "advisory" "pylint" $pylintCommand { & $pythonBin -m pylint @pylintFiles }
        }
        else {
            Add-DidNotRun "advisory" "pylint" "$pythonBin -m pylint python/*.py" "pylint is not installed for this interpreter"
        }
    }
}

$ignoreCommand = "git check-ignore -q --no-index for fanfic private paths; tests/fixtures/ashfall/ch01.md must not be ignored"
$ignoreFailed = $false
$ignoreLog = New-Object System.Collections.Generic.List[string]
$package = "python/fanfic_story_doctor"
foreach ($relative in @("drafts/x.txt", "works/x/ch01.md", "runs/run.json", "cache/key.json", "eval/holdout/set.yaml")) {
    $target = "$package/$relative"
    git check-ignore -q --no-index $target
    if ($LASTEXITCODE -ne 0) {
        $ignoreLog.Add("$target is not gitignored")
        $ignoreFailed = $true
    }
}
$trackedFixture = "$package/tests/fixtures/ashfall/ch01.md"
git check-ignore -q --no-index $trackedFixture
if ($LASTEXITCODE -eq 0) {
    $ignoreLog.Add("$trackedFixture should be tracked")
    $ignoreFailed = $true
}
if (-not $ignoreFailed) {
    Add-Pass "blocking" "fanfic story doctor private paths are gitignored" $ignoreCommand "fanfic ignore rules ok"
}
else {
    Add-Fail "blocking" "fanfic story doctor private paths are gitignored" $ignoreCommand 1 ($ignoreLog -join "`n")
}

$script:PowerShellHost = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
if (-not $script:PowerShellHost) {
    $script:PowerShellHost = "powershell"
}

$preflightPath = Join-Path $repoRoot "tools/workflow_guardrails/preflight.ps1"
$preflightCommand = "$script:PowerShellHost -NoProfile -ExecutionPolicy Bypass -File $preflightPath"
Invoke-Recorded "workflow" "workflow preflight" $preflightCommand {
    & $script:PowerShellHost -NoProfile -ExecutionPolicy Bypass -File $preflightPath
}

$diagnosticsPath = Join-Path $repoRoot "tools/workflow_guardrails/diagnostics.ps1"
$diagnosticsCommand = "$script:PowerShellHost -NoProfile -ExecutionPolicy Bypass -File $diagnosticsPath"
Invoke-Recorded "workflow" "workflow diagnostics" $diagnosticsCommand {
    & $script:PowerShellHost -NoProfile -ExecutionPolicy Bypass -File $diagnosticsPath
}

$treeAfter = (git status --porcelain | Out-String).TrimEnd()
$treeCommand = "git status --porcelain (compared before and after the checks above)"
if ($treeBefore -eq $treeAfter) {
    Add-Pass "guard" "working tree unchanged by this health check" $treeCommand ""
}
else {
    $diffText = "before:`n$treeBefore`nafter:`n$treeAfter"
    Add-Fail "guard" "working tree unchanged by this health check" $treeCommand 1 $diffText
}

Write-Host ""
Write-Host "result: pass=$($script:PassCount) fail=$($script:FailCount) did_not_run=$($script:DidNotRunCount)"
if ($script:FailCount -eq 0 -and $script:DidNotRunCount -eq 0) {
    Write-Host "overall: success"
    exit 0
}
Write-Host "overall: not success"
if ($script:FailCount -gt 0) {
    exit 1
}
exit 2
