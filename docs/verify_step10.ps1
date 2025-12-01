# Verify Step 10: Data Import to MySQL

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 10: Data Import" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Push-Location "backend"

# Check key tables have data
Write-Host "Checking key tables..." -ForegroundColor Yellow

$result = python -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings'); django.setup(); from django.db import connection; cursor = connection.cursor(); tables = {'data_marketdata': 0, 'signals_tradingsignal': 0, 'signals_spottradingsignal': 0, 'auth_user': 0}; for table in tables: cursor.execute(f'SELECT COUNT(*) FROM {table}'); tables[table] = cursor.fetchone()[0]; print('|'.join([f'{k}:{v}' for k,v in tables.items()]))" 2>&1

if ($LASTEXITCODE -eq 0) {
    $data = $result -split '\|'
    $allGood = $true
    
    foreach ($item in $data) {
        $parts = $item -split ':'
        $table = $parts[0]
        $count = [int]$parts[1]
        
        if ($count -gt 0) {
            Write-Host "[OK] $table : $count rows" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] $table : $count rows (empty)" -ForegroundColor Yellow
            $allGood = $false
        }
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    
    if ($allGood) {
        Write-Host "Step 10 is COMPLETE!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Data successfully imported to MySQL!" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Migration from SQLite to MySQL is COMPLETE!" -ForegroundColor Green
    } else {
        Write-Host "Step 10 completed with warnings" -ForegroundColor Yellow
        Write-Host "========================================" -ForegroundColor Yellow
    }
} else {
    Write-Host "[FAIL] Could not verify data" -ForegroundColor Red
    Write-Host $result
}

Pop-Location
Write-Host ""

