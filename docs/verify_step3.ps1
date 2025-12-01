# Verify Step 3: MySQL Python Client Installation

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 3: MySQL Python Client" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allChecksPassed = $true

# Check 1: PyMySQL can be imported
Write-Host "Check 1: PyMySQL import..." -ForegroundColor Yellow
try {
    $result = python -c "import pymysql; print(pymysql.__version__)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] PyMySQL is installed (Version: $result)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] PyMySQL cannot be imported" -ForegroundColor Red
        $allChecksPassed = $false
    }
} catch {
    Write-Host "[FAIL] Error checking PyMySQL: $_" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 2: PyMySQL can be configured as MySQLdb
Write-Host "Check 2: PyMySQL MySQLdb compatibility..." -ForegroundColor Yellow
try {
    $result = python -c "import pymysql; pymysql.install_as_MySQLdb(); print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] PyMySQL can be configured as MySQLdb" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] PyMySQL MySQLdb configuration failed" -ForegroundColor Red
        $allChecksPassed = $false
    }
} catch {
    Write-Host "[FAIL] Error: $_" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 3: PyMySQL in requirements.txt
Write-Host "Check 3: PyMySQL in requirements.txt..." -ForegroundColor Yellow
if (Test-Path "backend\requirements.txt") {
    $content = Get-Content "backend\requirements.txt" -Raw
    if ($content -match "PyMySQL") {
        Write-Host "[OK] PyMySQL found in requirements.txt" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] PyMySQL NOT found in requirements.txt" -ForegroundColor Red
        $allChecksPassed = $false
    }
} else {
    Write-Host "[FAIL] requirements.txt not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allChecksPassed) {
    Write-Host "Step 3 is COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can proceed to Step 5: Update Environment Variables" -ForegroundColor Cyan
} else {
    Write-Host "Step 3 is NOT complete" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install PyMySQL:" -ForegroundColor Yellow
    Write-Host "pip install PyMySQL" -ForegroundColor White
}

Write-Host ""






