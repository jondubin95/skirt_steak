param(
    [string]$SyncSource = "python/Project/Gem_Factory/Jons_Gems/clarity-concision-editor/internal/core/instructions",
    [string]$ClientSecrets = "Sensitive/credentials.json",
    [string]$Token = "Sensitive/google/gdocs_token.json",
    [string]$Map = "Sensitive/google/clarity-concision-editor.gdocs-map.json",
    [switch]$DryRunSync
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $root = (git rev-parse --show-toplevel 2>$null)
    if (-not $root) {
        throw "Not inside a git repository."
    }
    return $root.Trim()
}

function Resolve-InputPath {
    param([string]$PathValue, [string]$RepoRoot)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $PathValue))
}

$repoRoot = Get-RepoRoot
$branch = (git -C $repoRoot branch --show-current).Trim()
$cwd = (Get-Location).Path

$syncScriptRepoRelative = "python/Project/Gem_Factory/tools/gdocs_sync/sync_gem_folder_to_gdocs.py"
$syncScriptAbsolute = Join-Path $repoRoot $syncScriptRepoRelative

$sourceAbs = Resolve-InputPath -PathValue $SyncSource -RepoRoot $repoRoot
$clientSecretsAbs = Resolve-InputPath -PathValue $ClientSecrets -RepoRoot $repoRoot
$tokenAbs = Resolve-InputPath -PathValue $Token -RepoRoot $repoRoot
$mapAbs = Resolve-InputPath -PathValue $Map -RepoRoot $repoRoot

$errors = @()
$warnings = @()

if ($branch -eq "main" -or $branch -eq "master") {
    $errors += "Current branch is '$branch'. Use a feature branch before sync/commit."
}

if (-not (Test-Path $syncScriptAbsolute)) {
    $errors += "Sync script not found: $syncScriptAbsolute"
}

if (-not (Test-Path $sourceAbs)) {
    $errors += "Sync source path not found: $sourceAbs"
}

if (-not (Test-Path $clientSecretsAbs)) {
    $errors += "Client secrets file not found: $clientSecretsAbs"
}

$tokenParent = Split-Path -Parent $tokenAbs
$mapParent = Split-Path -Parent $mapAbs
if (-not (Test-Path $tokenParent)) {
    $errors += "Token parent directory is missing: $tokenParent`nCreate it with: New-Item -ItemType Directory -Force '$tokenParent'"
}
if (-not (Test-Path $mapParent)) {
    $errors += "Map parent directory is missing: $mapParent`nCreate it with: New-Item -ItemType Directory -Force '$mapParent'"
}

$cwdPathVariantA = Join-Path $cwd "tools/gdocs_sync/sync_gem_folder_to_gdocs.py"
$cwdPathVariantB = Join-Path $cwd "python/Project/Gem_Factory/tools/gdocs_sync/sync_gem_folder_to_gdocs.py"
if (-not (Test-Path $cwdPathVariantA) -and -not (Test-Path $cwdPathVariantB)) {
    $warnings += "Current directory does not match the two standard command layouts."
}

$rootCommand = @'
.\.venv\Scripts\python.exe python\Project\Gem_Factory\tools\gdocs_sync\sync_gem_folder_to_gdocs.py `
  --src python\Project\Gem_Factory\Jons_Gems\clarity-concision-editor\internal\core\instructions `
  --title-prefix "Polish - " `
  --client-secrets Sensitive\credentials.json `
  --token Sensitive\google\gdocs_token.json `
  --map Sensitive\google\clarity-concision-editor.gdocs-map.json
'@

$gemFactoryCommand = @'
..\..\..\.venv\Scripts\python.exe tools\gdocs_sync\sync_gem_folder_to_gdocs.py `
  --src Jons_Gems\clarity-concision-editor\internal\core\instructions `
  --title-prefix "Polish - " `
  --client-secrets ..\..\..\Sensitive\credentials.json `
  --token ..\..\..\Sensitive\google\gdocs_token.json `
  --map ..\..\..\Sensitive\google\clarity-concision-editor.gdocs-map.json
'@

Write-Host "Workflow preflight"
Write-Host "Repo root : $repoRoot"
Write-Host "Branch    : $branch"
Write-Host "CWD       : $cwd"
Write-Host "Sync src  : $sourceAbs"
Write-Host ""

if ($warnings.Count -gt 0) {
    Write-Host "Warnings:" -ForegroundColor Yellow
    $warnings | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host ""
}

if ($errors.Count -gt 0) {
    Write-Host "Preflight failed:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Standard sync command from repo root:"
    Write-Host $rootCommand
    Write-Host ""
    Write-Host "Standard sync command from python/Project/Gem_Factory:"
    Write-Host $gemFactoryCommand
    exit 1
}

Write-Host "Preflight checks passed." -ForegroundColor Green
Write-Host ""
Write-Host "Standard sync command from repo root:"
Write-Host $rootCommand
Write-Host ""
Write-Host "Standard sync command from python/Project/Gem_Factory:"
Write-Host $gemFactoryCommand

if ($DryRunSync) {
    Write-Host ""
    Write-Host "Running dry-run sync..."
    $pythonExe = Join-Path $repoRoot ".venv/Scripts/python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = "python"
    }

    & $pythonExe $syncScriptAbsolute `
        --src $sourceAbs `
        --title-prefix "Polish - " `
        --client-secrets $clientSecretsAbs `
        --token $tokenAbs `
        --map $mapAbs `
        --dry-run
}
