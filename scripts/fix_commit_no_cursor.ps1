# Remove "Co-authored-by: Cursor" from the latest commit message and optionally push.
# Run in PowerShell from repo root (your terminal, not Cursor agent):
#   .\scripts\fix_commit_no_cursor.ps1
#   .\scripts\fix_commit_no_cursor.ps1 -Push

param(
    [switch]$Push
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$body = git log -1 --format=%B
if ($body -notmatch 'Co-authored-by:\s*Cursor') {
    Write-Host "Latest commit has no Cursor co-author trailer. Nothing to fix." -ForegroundColor Green
    git log -1 --oneline
    exit 0
}

# Keep first paragraph / subject only, or pass explicit message
$lines = $body -split "`n" | Where-Object {
    $_ -notmatch '^\s*Co-authored-by:\s*Cursor'
}
$newMsg = ($lines | Where-Object { $_.Trim() }) -join "`n"
if (-not $newMsg.Trim()) {
    $newMsg = "Update repository"
}

Write-Host "Amending commit message to:" -ForegroundColor Cyan
Write-Host $newMsg
git commit --amend -m $newMsg

$check = git log -1 --format=%B
if ($check -match 'Co-authored-by:\s*Cursor') {
    Write-Error "Amend failed — Cursor trailer still present."
}

Write-Host "Fixed:" -ForegroundColor Green
git log -1 --format=fuller

if ($Push) {
    git push --force-with-lease origin main
    Write-Host "Pushed with --force-with-lease." -ForegroundColor Green
} else {
    Write-Host "Local amend done. Push with: git push --force-with-lease origin main" -ForegroundColor Yellow
}
