# One-shot runner for the weekly newsletter generator.
#
# Usage:
#   .\run.ps1                       # dry-run, opens the resulting HTML
#   .\run.ps1 -NoOpen               # dry-run, don't auto-open
#   .\run.ps1 -Live                 # actually send email (no --dry-run)
#   .\run.ps1 -ExtraArgs "--since 14 --max-items 20"
#
# The script always uses the project's local venv at .\.venv so it works
# regardless of your current PowerShell execution policy.

[CmdletBinding()]
param(
    [switch]$Live,
    [switch]$NoOpen,
    [string]$ExtraArgs = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Python = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Python venv not found at $Python. Create it first: python -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -e ."
}

$argList = @("run.py")
if (-not $Live) { $argList += "--dry-run" }
if ($ExtraArgs) { $argList += $ExtraArgs.Split(" ") | Where-Object { $_ } }

Write-Host ""
Write-Host "==> $Python $($argList -join ' ')" -ForegroundColor Cyan
Write-Host ""

& $Python @argList
$exit = $LASTEXITCODE

if ($exit -ne 0) {
    Write-Host ""
    Write-Error "run.py exited with code $exit"
}

if ($Live) {
    Write-Host ""
    Write-Host "Live run finished. Email dispatched (check logs\run.log if unsure)." -ForegroundColor Green
    exit $exit
}

$outDir = Join-Path $ScriptDir "out"
$latest = Get-ChildItem -Path $outDir -Filter "newsletter-*.html" -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1

if (-not $latest) {
    Write-Warning "No newsletter HTML found in $outDir."
    exit $exit
}

Write-Host ""
Write-Host "Latest newsletter: $($latest.FullName)" -ForegroundColor Green
Write-Host "Size: $([math]::Round($latest.Length / 1KB, 1)) KB | Modified: $($latest.LastWriteTime)" -ForegroundColor DarkGray

if (-not $NoOpen) {
    Write-Host "Opening..." -ForegroundColor DarkGray
    Invoke-Item $latest.FullName
}

exit $exit
