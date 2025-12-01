-- Step 2: Create MySQL Database and User
-- This script creates the database and user for the AI Trading Engine

-- Create Database
CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create User (replace 'your_secure_password' with your actual password)
CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY 'your_secure_password';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';

-- Apply the changes
FLUSH PRIVILEGES;

-- Verify user creation
SELECT user, host FROM mysql.user WHERE user = 'trading_user';

-- Show database
SHOW DATABASES LIKE 'ai_trading_engine';

-- Success message
SELECT 'Database and user created successfully!' as Status;

