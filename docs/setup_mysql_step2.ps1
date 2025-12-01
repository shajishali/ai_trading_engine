# Step 2: Create MySQL Database and User
# This script creates the database and user for the AI Trading Engine

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: MySQL Database and User Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Prompt for MySQL root password
$rootPassword = Read-Host "Enter MySQL root password" -AsSecureString
$rootPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($rootPassword)
)

# Prompt for trading_user password
Write-Host ""
Write-Host "Now, set a password for the 'trading_user' account:" -ForegroundColor Yellow
$tradingUserPassword = Read-Host "Enter password for trading_user" -AsSecureString
$tradingUserPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tradingUserPassword)
)

Write-Host ""
Write-Host "Creating database and user..." -ForegroundColor Green

# Create SQL commands
$sqlCommands = @"
CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY '$tradingUserPasswordPlain';
GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';
FLUSH PRIVILEGES;
SELECT 'Database created successfully!' as Status;
SELECT user, host FROM mysql.user WHERE user = 'trading_user';
SHOW DATABASES LIKE 'ai_trading_engine';
"@

# Create temporary SQL file
$tempSqlFile = [System.IO.Path]::GetTempFileName()
$sqlCommands | Out-File -FilePath $tempSqlFile -Encoding UTF8

# Execute SQL commands using the temp file (PowerShell compatible)
Get-Content $tempSqlFile | mysql -u root -p"$rootPasswordPlain" 2>&1

# Clean up temp file
Remove-Item $tempSqlFile -Force

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Step 2 completed successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Database: ai_trading_engine" -ForegroundColor Cyan
    Write-Host "User: trading_user" -ForegroundColor Cyan
    Write-Host "Host: localhost" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "IMPORTANT: Save the trading_user password securely!" -ForegroundColor Yellow
    Write-Host "You will need it for Step 5 (Environment Variables)" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Error occurred during setup!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Please check the error messages above." -ForegroundColor Red
}

# Clear passwords from memory
$rootPasswordPlain = $null
$tradingUserPasswordPlain = $null

