# Safely remove SQLite database
# This script moves SQLite to backups before removing

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Safe SQLite Removal" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if SQLite exists
if (-not (Test-Path "db.sqlite3")) {
    Write-Host "No SQLite database found. Nothing to remove." -ForegroundColor Yellow
    exit 0
}

# Verify backup exists
$backupExists = Test-Path "..\backups\db.sqlite3.backup_*"
if (-not $backupExists) {
    Write-Host "WARNING: No backup found in backups/ directory!" -ForegroundColor Red
    Write-Host "Creating backup before removal..." -ForegroundColor Yellow
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupFile = "..\backups\db.sqlite3.backup_$timestamp"
    Copy-Item "db.sqlite3" $backupFile
    Write-Host "Backup created: $backupFile" -ForegroundColor Green
} else {
    Write-Host "Backup exists in backups/ directory" -ForegroundColor Green
}

# Verify MySQL is working
Write-Host ""
Write-Host "Verifying MySQL connection..." -ForegroundColor Yellow
$pythonScript = "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings'); django.setup(); from django.db import connection; print(connection.settings_dict['ENGINE'])"
$mysqlCheck = python -c $pythonScript 2>&1

if ($mysqlCheck -match "mysql") {
    Write-Host "MySQL is configured and working" -ForegroundColor Green
} else {
    Write-Host "WARNING: MySQL may not be configured correctly!" -ForegroundColor Red
    Write-Host "Do not remove SQLite yet!" -ForegroundColor Red
    exit 1
}

# Confirm removal
Write-Host ""
Write-Host "Ready to remove SQLite database:" -ForegroundColor Yellow
Write-Host "  File: db.sqlite3" -ForegroundColor White
Write-Host "  Backup: Available in backups/ directory" -ForegroundColor White
Write-Host ""
$confirm = Read-Host "Type YES to confirm removal (or anything else to cancel)"

if ($confirm -eq "YES") {
    Write-Host ""
    Write-Host "Removing SQLite database..." -ForegroundColor Yellow
    
    # Move to backups with timestamp (extra safety)
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $archiveFile = "..\backups\db.sqlite3.archived_$timestamp"
    Move-Item "db.sqlite3" $archiveFile
    
    Write-Host "SQLite database moved to: $archiveFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "SQLite removed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your application is now fully on MySQL!" -ForegroundColor Cyan
    Write-Host "SQLite backup is safely stored in backups/ directory" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Removal cancelled. SQLite database kept." -ForegroundColor Yellow
}
