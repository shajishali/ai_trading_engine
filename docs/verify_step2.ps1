# Verify Step 2: Check if database and user were created

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 2: Database and User" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if MySQL service is running
$mysqlService = Get-Service -Name "MySQL84" -ErrorAction SilentlyContinue
if ($mysqlService) {
    Write-Host "MySQL Service Status: $($mysqlService.Status)" -ForegroundColor Green
} else {
    Write-Host "MySQL Service: Not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "To verify database and user creation, please run:" -ForegroundColor Yellow
Write-Host ""
Write-Host "mysql -u root -p" -ForegroundColor Cyan
Write-Host ""
Write-Host "Then run these verification commands:" -ForegroundColor Yellow
Write-Host ""
Write-Host "SHOW DATABASES LIKE 'ai_trading_engine';" -ForegroundColor White
Write-Host "SELECT user, host FROM mysql.user WHERE user = 'trading_user';" -ForegroundColor White
Write-Host ""
Write-Host "If you see the database and user listed, Step 2 is complete!" -ForegroundColor Green
Write-Host ""






