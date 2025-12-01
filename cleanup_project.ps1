# Project Cleanup Script
# Cleans up temporary files, migration scripts, and unwanted documentation

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project Cleanup for Hosting" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$itemsToRemove = @()

# 1. Migration-related temporary files in docs/
Write-Host "1. Migration-related temporary files..." -ForegroundColor Yellow
$migrationFiles = @(
    "docs\STEP2_INSTRUCTIONS.md",
    "docs\STEP2_RUN.bat",
    "docs\run_mysql.ps1",
    "docs\run_step2.bat",
    "docs\setup_mysql_step2_interactive.ps1",
    "docs\setup_mysql_step2.ps1",
    "docs\mysql_setup_step2.sql",
    "docs\verify_step2.ps1",
    "docs\verify_step2_complete.ps1",
    "docs\verify_step3.ps1",
    "docs\verify_step5.ps1",
    "docs\verify_step6.ps1",
    "docs\verify_step7.ps1",
    "docs\verify_step9.ps1",
    "docs\verify_step10.ps1"
)

foreach ($file in $migrationFiles) {
    if (Test-Path $file) {
        $itemsToRemove += $file
        Write-Host "  [REMOVE] $file" -ForegroundColor Red
    }
}

# 2. Temporary Python scripts in backend/
Write-Host "`n2. Temporary Python scripts..." -ForegroundColor Yellow
$tempScripts = @(
    "backend\check_mysql_tables.py",
    "backend\export_sqlite_data.py",
    "backend\fix_datasource_duplicates.py",
    "backend\fix_import_issues.py",
    "backend\import_sqlite_data.py",
    "backend\test_db_connection.py",
    "backend\verify_datasource_fix.py",
    "backend\verify_import.py",
    "backend\remove_sqlite_safely.ps1"
)

foreach ($file in $tempScripts) {
    if (Test-Path $file) {
        $itemsToRemove += $file
        Write-Host "  [REMOVE] $file" -ForegroundColor Red
    }
}

# 3. Log files
Write-Host "`n3. Log files..." -ForegroundColor Yellow
$logFiles = Get-ChildItem -Path "backend" -Filter "*.log" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch "node_modules" }
foreach ($file in $logFiles) {
    $itemsToRemove += $file.FullName
    Write-Host "  [REMOVE] $($file.FullName)" -ForegroundColor Red
}

# 4. Python cache files
Write-Host "`n4. Python cache files (__pycache__)..." -ForegroundColor Yellow
$cacheDirs = Get-ChildItem -Path "backend" -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch "venv|\.venv" }
foreach ($dir in $cacheDirs) {
    $itemsToRemove += $dir.FullName
    Write-Host "  [REMOVE] $($dir.FullName)" -ForegroundColor Red
}

# 5. Celery beat schedule files
Write-Host "`n5. Celery beat schedule files..." -ForegroundColor Yellow
$celeryFiles = @(
    "backend\celerybeat-schedule",
    "backend\celerybeat-schedule-shm",
    "backend\celerybeat-schedule-wal"
)
foreach ($file in $celeryFiles) {
    if (Test-Path $file) {
        $itemsToRemove += $file
        Write-Host "  [REMOVE] $file" -ForegroundColor Red
    }
}

# 6. Redis dump file (if exists)
Write-Host "`n6. Redis dump file..." -ForegroundColor Yellow
if (Test-Path "backend\redis\dump.rdb") {
    $itemsToRemove += "backend\redis\dump.rdb"
    Write-Host "  [REMOVE] backend\redis\dump.rdb" -ForegroundColor Red
}

# 7. Migration guide (keep main one, remove step-by-step)
Write-Host "`n7. Migration documentation..." -ForegroundColor Yellow
if (Test-Path "docs\sqlite-to-mysql-migration-guide.md") {
    Write-Host "  [KEEP] docs\sqlite-to-mysql-migration-guide.md (main guide)" -ForegroundColor Green
    Write-Host "  [REMOVE] (already listed above)" -ForegroundColor Gray
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Total items to remove: $($itemsToRemove.Count)" -ForegroundColor Yellow
Write-Host ""

# Ask for confirmation
$confirm = Read-Host "Do you want to proceed with cleanup? (YES to confirm)"

if ($confirm -eq "YES") {
    Write-Host "`nStarting cleanup..." -ForegroundColor Yellow
    
    $removed = 0
    $failed = 0
    
    foreach ($item in $itemsToRemove) {
        try {
            if (Test-Path $item) {
                if ((Get-Item $item) -is [System.IO.DirectoryInfo]) {
                    Remove-Item $item -Recurse -Force -ErrorAction SilentlyContinue
                } else {
                    Remove-Item $item -Force -ErrorAction SilentlyContinue
                }
                $removed++
            }
        } catch {
            Write-Host "  Failed to remove: $item" -ForegroundColor Red
            $failed++
        }
    }
    
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "Cleanup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Removed: $removed items" -ForegroundColor Green
    if ($failed -gt 0) {
        Write-Host "Failed: $failed items" -ForegroundColor Yellow
    }
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "`nCleanup cancelled." -ForegroundColor Yellow
}






