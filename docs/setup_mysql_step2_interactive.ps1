# Step 2: Create MySQL Database and User
# Interactive script to create database and user securely

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: MySQL Database and User Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Prompt for MySQL root password
Write-Host "Enter MySQL root password:" -ForegroundColor Yellow
$rootPassword = Read-Host -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($rootPassword)
$rootPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Prompt for trading_user password
Write-Host ""
Write-Host "Set a password for the 'trading_user' account:" -ForegroundColor Yellow
Write-Host "(This will be used in your Django settings)" -ForegroundColor Gray
$tradingPassword = Read-Host -AsSecureString
$BSTR2 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($tradingPassword)
$tradingPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR2)

Write-Host ""
Write-Host "Creating database and user..." -ForegroundColor Green
Write-Host ""

# Build SQL commands dynamically
$sqlScript = @"
CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY '$tradingPasswordPlain';
GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';
FLUSH PRIVILEGES;
SELECT 'Database created successfully!' as Status;
SELECT user, host FROM mysql.user WHERE user = 'trading_user';
SHOW DATABASES LIKE 'ai_trading_engine';
"@

# Create temp file
$tempFile = New-TemporaryFile
$sqlScript | Out-File -FilePath $tempFile.FullName -Encoding UTF8 -NoNewline

# Execute SQL
try {
    $result = Get-Content $tempFile.FullName | & mysql -u root -p"$rootPasswordPlain" 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $result
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "Step 2 completed successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Database: ai_trading_engine" -ForegroundColor Cyan
        Write-Host "User: trading_user" -ForegroundColor Cyan
        Write-Host "Host: localhost" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "IMPORTANT: Save this password securely!" -ForegroundColor Yellow
        Write-Host "Password: $tradingPasswordPlain" -ForegroundColor Yellow
        Write-Host "You will need it for Step 5 (Environment Variables)" -ForegroundColor Yellow
    } else {
        Write-Host $result -ForegroundColor Red
        Write-Host ""
        Write-Host "Error occurred. Please check the messages above." -ForegroundColor Red
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
} finally {
    # Clean up
    Remove-Item $tempFile.FullName -Force -ErrorAction SilentlyContinue
    # Clear passwords from memory
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR2)
    $rootPasswordPlain = $null
    $tradingPasswordPlain = $null
}

