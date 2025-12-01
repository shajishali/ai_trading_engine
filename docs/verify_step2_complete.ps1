# Verify Step 2 Completion
# This script checks if the database and user were created

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verifying Step 2 Completion" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Enter MySQL root password to verify:" -ForegroundColor Yellow
$rootPassword = Read-Host -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($rootPassword)
$rootPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

Write-Host ""
Write-Host "Checking database..." -ForegroundColor Green

# Check if database exists
$dbCheck = "SHOW DATABASES LIKE 'ai_trading_engine';"

$tempFile = New-TemporaryFile
$dbCheck | Out-File -FilePath $tempFile.FullName -Encoding UTF8 -NoNewline

$dbResult = Get-Content $tempFile.FullName | & mysql -u root -p"$rootPasswordPlain" 2>&1
Remove-Item $tempFile.FullName -Force

Write-Host ""
Write-Host "Checking user..." -ForegroundColor Green

# Check if user exists
$userCheck = "SELECT user, host FROM mysql.user WHERE user = 'trading_user';"

$tempFile2 = New-TemporaryFile
$userCheck | Out-File -FilePath $tempFile2.FullName -Encoding UTF8 -NoNewline

$userResult = Get-Content $tempFile2.FullName | & mysql -u root -p"$rootPasswordPlain" 2>&1
Remove-Item $tempFile2.FullName -Force

# Analyze results
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verification Results:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$dbExists = $dbResult -match "ai_trading_engine"
$userExists = $userResult -match "trading_user"

if ($dbExists) {
    Write-Host "[OK] Database 'ai_trading_engine' exists" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Database 'ai_trading_engine' NOT found" -ForegroundColor Red
}

if ($userExists) {
    Write-Host "[OK] User 'trading_user' exists" -ForegroundColor Green
} else {
    Write-Host "[FAIL] User 'trading_user' NOT found" -ForegroundColor Red
}

Write-Host ""

if ($dbExists -and $userExists) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Step 2 is COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can proceed to Step 3: Install MySQL Python Client" -ForegroundColor Cyan
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Step 2 is NOT complete" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please complete Step 2 first:" -ForegroundColor Yellow
    Write-Host "1. Run: mysql -u root -p" -ForegroundColor White
    Write-Host "2. Execute the SQL commands from the instructions" -ForegroundColor White
}

# Clear password from memory
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
$rootPasswordPlain = $null

Write-Host ""
