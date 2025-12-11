-- Setup script for local MySQL database
-- Run this after connecting to MySQL as root user

-- Create database
CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Drop existing user if exists (to avoid conflicts)
DROP USER IF EXISTS 'trading_user'@'localhost';

-- Create user with password from .env file
CREATE USER 'trading_user'@'localhost' IDENTIFIED BY '12345';

-- Grant all privileges
GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Verify user was created
SELECT User, Host FROM mysql.user WHERE User = 'trading_user';

-- Show database
SHOW DATABASES LIKE 'ai_trading_engine';

SELECT 'Setup complete! Database and user created successfully.' AS Status;

