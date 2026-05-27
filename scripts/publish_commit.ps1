# Commit and push WITHOUT Co-authored-by: Cursor (agent commits add that trailer automatically).
# YOU must run this in your own PowerShell terminal — not "ask Cursor to git commit".
#
#   cd C:\Users\raghu\AI-Projects\data-catalog-assistant
#   .\scripts\publish_commit.ps1 -Message "Your commit message"
#
# Uses only: git commit -m "..."  (no --trailer flags)

param(
    [Parameter(Mandatory = $false)]
    [string]$Message = "Update documentation"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Repo: $Root" -ForegroundColor Cyan

# Safety: refuse if .env would be staged
$status = git status --porcelain
if ($status -match '(?m)^A\s+\.env' -or $status -match '(?m)^\?\?\s+\.env') {
    Write-Error ".env must not be committed. Check .gitignore and git status."
}

git add -A
git status

$pending = git diff --cached --quiet 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Nothing to commit." -ForegroundColor Yellow
    exit 0
}

# Plain commit message only — no Co-authored-by trailer
git commit -m $Message

$body = git log -1 --format=%B
if ($body -match 'Co-authored-by:\s*Cursor') {
    Write-Error "Commit still contains Co-authored-by: Cursor. Amend manually: git commit --amend"
}

Write-Host "Committed:" -ForegroundColor Green
git log -1 --oneline

$push = Read-Host "Push to origin/main? (y/N)"
if ($push -eq 'y' -or $push -eq 'Y') {
    git push origin main
    Write-Host "Pushed." -ForegroundColor Green
} else {
    Write-Host "Skipped push. Run: git push origin main" -ForegroundColor Yellow
}
