# Add MySQL to PATH and open MySQL
$env:Path += ";C:\Program Files\MySQL\MySQL Server 8.4\bin"

Write-Host "MySQL has been added to PATH for this session." -ForegroundColor Green
Write-Host ""
Write-Host "You can now run: mysql -u root -p" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening MySQL..." -ForegroundColor Yellow
Write-Host ""

mysql -u root -p






