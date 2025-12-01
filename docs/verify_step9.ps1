# Verify Step 9: MySQL Database Schema

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 9: MySQL Database Schema" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Push-Location "backend"

# Check 1: Database connection
Write-Host "Check 1: Database connection..." -ForegroundColor Yellow
$result = python manage.py check --database default 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Database connection successful" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Database connection failed" -ForegroundColor Red
    Write-Host $result
    Pop-Location
    exit 1
}

Write-Host ""

# Check 2: Tables exist
Write-Host "Check 2: Database tables..." -ForegroundColor Yellow
$tableCheck = python check_mysql_tables.py 2>&1
if ($tableCheck -match "Total tables in MySQL: \d+") {
    $tableCount = [regex]::Match($tableCheck, "Total tables in MySQL: (\d+)").Groups[1].Value
    Write-Host "[OK] Tables found: $tableCount" -ForegroundColor Green
    if ([int]$tableCount -gt 50) {
        Write-Host "[OK] Sufficient number of tables created" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Fewer tables than expected" -ForegroundColor Yellow
    }
} else {
    Write-Host "[FAIL] Could not verify tables" -ForegroundColor Red
}

Write-Host ""

# Check 3: Migrations applied
Write-Host "Check 3: Migrations status..." -ForegroundColor Yellow
$migrations = python manage.py showmigrations 2>&1
$pending = ($migrations | Select-String -Pattern "\[ \]").Count
if ($pending -eq 0) {
    Write-Host "[OK] All migrations applied" -ForegroundColor Green
} else {
    Write-Host "[WARNING] $pending migrations pending" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($LASTEXITCODE -eq 0 -and $tableCount -gt 50) {
    Write-Host "Step 9 is COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "MySQL database schema is ready!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next: Step 10 - Import Data to MySQL" -ForegroundColor Cyan
} else {
    Write-Host "Step 9 needs attention" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
}

Pop-Location
Write-Host ""
