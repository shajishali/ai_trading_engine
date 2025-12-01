# Cleanup unwanted MD files

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MD Files Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$itemsToRemove = @()

# Remove all report files (not needed for hosting)
Write-Host "1. Report files (daily/weekly)..." -ForegroundColor Yellow
$reportFiles = Get-ChildItem -Path "reports" -Filter "*.md" -Recurse -ErrorAction SilentlyContinue
foreach ($file in $reportFiles) {
    $itemsToRemove += $file.FullName
    Write-Host "  [REMOVE] $($file.Name)" -ForegroundColor Red
}

# Optional: Remove deployment docs if not needed
Write-Host "`n2. Deployment documentation..." -ForegroundColor Yellow
Write-Host "  [KEEP] docs\deployment-plan-aws-ubuntu.md (may be useful)" -ForegroundColor Green
Write-Host "  [KEEP] docs\docker-deployment-plan-aws-ubuntu.md (may be useful)" -ForegroundColor Green
Write-Host "  [KEEP] docs\admin-panel-quick-guide.md (useful for admin)" -ForegroundColor Green
Write-Host "  [KEEP] docs\admin-panel-enhancement-plan.md (project docs)" -ForegroundColor Green
Write-Host "  [KEEP] docs\PROJECT_PHASES_COMPLETE.md (project docs)" -ForegroundColor Green
Write-Host "  [KEEP] docs\enhanced-data-storage-system.md (project docs)" -ForegroundColor Green

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Report files to remove: $($itemsToRemove.Count)" -ForegroundColor Yellow
Write-Host ""

# Proceed with removal
Write-Host "Removing report files..." -ForegroundColor Yellow

$removed = 0
foreach ($item in $itemsToRemove) {
    try {
        if (Test-Path $item) {
            Remove-Item $item -Force -ErrorAction SilentlyContinue
            $removed++
        }
    } catch {
        Write-Host "  Failed: $item" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "MD Files Cleanup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Removed: $removed report files" -ForegroundColor Green
Write-Host "`nRemaining MD files in docs/:" -ForegroundColor Cyan
Get-ChildItem -Path "docs" -Filter "*.md" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  - $($_.Name)" -ForegroundColor White
}
Write-Host "========================================" -ForegroundColor Green

