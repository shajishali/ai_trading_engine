# Verify Step 6: Django Settings Update

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 6: Django Settings" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allChecksPassed = $true

# Check 1: PyMySQL initialization in settings.py
Write-Host "Check 1: PyMySQL initialization..." -ForegroundColor Yellow
if (Test-Path "backend\ai_trading_engine\settings.py") {
    $content = Get-Content "backend\ai_trading_engine\settings.py" -Raw
    if ($content -match "pymysql.install_as_MySQLdb") {
        Write-Host "[OK] PyMySQL initialization found" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] PyMySQL initialization not found" -ForegroundColor Red
        $allChecksPassed = $false
    }
} else {
    Write-Host "[FAIL] settings.py not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 2: MySQL database configuration
Write-Host "Check 2: MySQL database configuration..." -ForegroundColor Yellow
if (Test-Path "backend\ai_trading_engine\settings.py") {
    $content = Get-Content "backend\ai_trading_engine\settings.py" -Raw
    if ($content -match "django.db.backends.mysql" -and 
        $content -match "DB_NAME" -and
        $content -match "ai_trading_engine") {
        Write-Host "[OK] MySQL database configuration found" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] MySQL database configuration not found or incomplete" -ForegroundColor Red
        $allChecksPassed = $false
    }
} else {
    Write-Host "[FAIL] settings.py not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 3: SQLite code removed
Write-Host "Check 3: SQLite code removed..." -ForegroundColor Yellow
if (Test-Path "backend\ai_trading_engine\settings.py") {
    $content = Get-Content "backend\ai_trading_engine\settings.py" -Raw
    if ($content -notmatch "django.db.backends.sqlite3" -or 
        ($content -match "django.db.backends.sqlite3" -and $content -match "#.*sqlite3")) {
        # Check if SQLite is only in comments
        $sqliteActive = $content -match "ENGINE.*sqlite3" -and $content -notmatch "#.*ENGINE.*sqlite3"
        if (-not $sqliteActive) {
            Write-Host "[OK] SQLite configuration removed or commented" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] SQLite configuration still active" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARNING] SQLite references found (may be in comments)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[FAIL] settings.py not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 4: Django can load settings
Write-Host "Check 4: Django settings validation..." -ForegroundColor Yellow
try {
    Push-Location "backend"
    $result = python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings'); django.setup(); from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])" 2>&1
    if ($LASTEXITCODE -eq 0 -and $result -match "mysql") {
        Write-Host "[OK] Django settings load correctly with MySQL" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Django settings validation failed" -ForegroundColor Red
        Write-Host "Output: $result" -ForegroundColor Red
        $allChecksPassed = $false
    }
    Pop-Location
} catch {
    Write-Host "[FAIL] Error validating Django settings: $_" -ForegroundColor Red
    $allChecksPassed = $false
    Pop-Location
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allChecksPassed) {
    Write-Host "Step 6 is COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: Test database connection with:" -ForegroundColor Cyan
    Write-Host "python manage.py check --database default" -ForegroundColor White
    Write-Host ""
    Write-Host "Or proceed to Step 9: Create MySQL Database Schema" -ForegroundColor Cyan
} else {
    Write-Host "Step 6 is NOT complete" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Write-Host ""

