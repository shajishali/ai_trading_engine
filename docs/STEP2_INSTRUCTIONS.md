# Step 2: Create MySQL Database and User - Instructions

## Quick Method (Recommended)

Run this command in PowerShell or Command Prompt:

```bash
mysql -u root -p
```

When prompted, enter your MySQL root password.

Then, copy and paste these SQL commands one by one (replace `your_secure_password` with your chosen password):

```sql
CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY 'your_secure_password';

GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';

FLUSH PRIVILEGES;

SELECT user, host FROM mysql.user WHERE user = 'trading_user';

SHOW DATABASES LIKE 'ai_trading_engine';

SELECT 'Database and user created successfully!' as Status;
```

Type `EXIT;` when done.

---

## Alternative: Use the Interactive Script

1. Open PowerShell in the `docs` folder
2. Run: `powershell -ExecutionPolicy Bypass -File setup_mysql_step2_interactive.ps1`
3. Enter your MySQL root password when prompted
4. Enter a password for the `trading_user` account
5. Save the `trading_user` password - you'll need it for Step 5!

---

## Verify Setup

After running the commands, verify everything works:

```bash
mysql -u trading_user -p ai_trading_engine
```

Enter the `trading_user` password. If you can connect, Step 2 is complete!

---

## What Was Created

- **Database:** `ai_trading_engine`
- **User:** `trading_user`
- **Host:** `localhost`
- **Privileges:** Full access to `ai_trading_engine` database

---

## Next Step

Once Step 2 is complete, proceed to **Step 3: Install MySQL Python Client**

