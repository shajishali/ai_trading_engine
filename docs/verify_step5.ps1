# Verify Step 5: Environment Variables Update

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 5: Environment Variables" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allChecksPassed = $true

# Check 1: env.local exists and has MySQL config
Write-Host "Check 1: backend/env.local MySQL configuration..." -ForegroundColor Yellow
if (Test-Path "backend\env.local") {
    $content = Get-Content "backend\env.local" -Raw
    if ($content -match "DB_ENGINE=django.db.backends.mysql" -and 
        $content -match "DB_NAME=ai_trading_engine" -and 
        $content -match "DB_USER=trading_user") {
        Write-Host "[OK] MySQL configuration found in env.local" -ForegroundColor Green
        
        # Check if password is still placeholder
        if ($content -match "DB_PASSWORD=your_secure_password") {
            Write-Host "[WARNING] Password is still placeholder - please update it!" -ForegroundColor Yellow
        } else {
            Write-Host "[OK] Password appears to be set" -ForegroundColor Green
        }
    } else {
        Write-Host "[FAIL] MySQL configuration not found or incomplete" -ForegroundColor Red
        $allChecksPassed = $false
    }
} else {
    Write-Host "[FAIL] env.local not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""

# Check 2: env.example updated
Write-Host "Check 2: backend/env.example MySQL configuration..." -ForegroundColor Yellow
if (Test-Path "backend\env.example") {
    $content = Get-Content "backend\env.example" -Raw
    if ($content -match "DB_ENGINE=django.db.backends.mysql" -and 
        $content -match "DB_NAME=ai_trading_engine") {
        Write-Host "[OK] MySQL configuration found in env.example" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] MySQL configuration not found in env.example" -ForegroundColor Red
        $allChecksPassed = $false
    }
} else {
    Write-Host "[FAIL] env.example not found" -ForegroundColor Red
    $allChecksPassed = $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allChecksPassed) {
    Write-Host "Step 5 is COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "IMPORTANT: Make sure to update DB_PASSWORD in backend/env.local" -ForegroundColor Yellow
    Write-Host "with your actual trading_user password!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You can proceed to Step 6: Update Django Settings" -ForegroundColor Cyan
} else {
    Write-Host "Step 5 is NOT complete" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Write-Host ""






