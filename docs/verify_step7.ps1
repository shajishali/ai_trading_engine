# Verify Step 7: SQLite Database Backup

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 7: SQLite Database Backup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allChecksPassed = $true

# Check 1: Backup directory exists
Write-Host "Check 1: Backup directory..." -ForegroundColor Yellow
if (Test-Path "backups") {
    Write-Host "[OK] Backup directory exists" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Backup directory not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 2: SQLite database backup file exists
Write-Host "Check 2: SQLite database backup..." -ForegroundColor Yellow
$backupFiles = Get-ChildItem "backups" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*backup*" -and $_.Extension -eq "" }
if ($backupFiles) {
    $latestBackup = $backupFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Host "[OK] SQLite backup found: $($latestBackup.Name)" -ForegroundColor Green
    Write-Host "     Size: $([math]::Round($latestBackup.Length/1MB, 2)) MB" -ForegroundColor Gray
    Write-Host "     Date: $($latestBackup.LastWriteTime)" -ForegroundColor Gray
} else {
    Write-Host "[FAIL] SQLite backup file not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 3: Data export file exists
Write-Host "Check 3: Data export file..." -ForegroundColor Yellow
$exportFiles = Get-ChildItem "backups" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*sqlite*" -or $_.Name -like "*export*" }
if ($exportFiles) {
    $latestExport = $exportFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Host "[OK] Data export found: $($latestExport.Name)" -ForegroundColor Green
    Write-Host "     Size: $([math]::Round($latestExport.Length/1MB, 2)) MB" -ForegroundColor Gray
    Write-Host "     Date: $($latestExport.LastWriteTime)" -ForegroundColor Gray
} else {
    Write-Host "[WARNING] Data export file not found (optional)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allChecksPassed) {
    Write-Host "Step 7 is COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Backups are safely stored in: backups/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can proceed to Step 9: Create MySQL Database Schema" -ForegroundColor Cyan
} else {
    Write-Host "Step 7 is NOT complete" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create backups before proceeding." -ForegroundColor Yellow
}

Write-Host ""






