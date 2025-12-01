#!/usr/bin/env python
"""
Playwright-based Database Connection Diagnostic and Fix Tool

This script uses Playwright to help diagnose and fix MySQL database connection issues.
It can:
1. Test database connections with different credentials
2. Provide guidance on fixing connection issues
3. Help set up the MySQL user and database if needed
"""

import os
import sys
import subprocess
import pymysql
from pathlib import Path
from playwright.sync_api import sync_playwright
import time

# Add the backend directory to the path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Try to load Django settings
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
    import django
    django.setup()
    from django.conf import settings
    DJANGO_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Django not available: {e}")
    DJANGO_AVAILABLE = False
    settings = None


def test_mysql_connection(host='localhost', port=3306, user='trading_user', password='', database='ai_trading_engine'):
    """Test MySQL connection with given credentials"""
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5
        )
        connection.close()
        return True, "Connection successful"
    except pymysql.err.OperationalError as e:
        error_code, error_msg = e.args
        return False, f"Error {error_code}: {error_msg}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def test_with_root_connection():
    """Try to connect with root user (common default scenarios)"""
    common_passwords = ['', 'root', 'password', 'admin', '123456']
    
    print("\n" + "="*60)
    print("Testing MySQL root connection with common passwords...")
    print("="*60)
    
    for pwd in common_passwords:
        success, message = test_mysql_connection(user='root', password=pwd, database='mysql')
        if success:
            print(f"✓ Root connection successful with password: {'(empty)' if not pwd else '***'}")
            return True, pwd
        else:
            print(f"✗ Root connection failed with password: {'(empty)' if not pwd else '***'}")
    
    return False, None


def create_mysql_user_and_database(root_password=''):
    """Create MySQL user and database using root connection"""
    try:
        print("\n" + "="*60)
        print("Attempting to create MySQL user and database...")
        print("="*60)
        
        # Connect as root
        root_conn = pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            password=root_password,
            database='mysql'
        )
        
        cursor = root_conn.cursor()
        
        # Create database
        print("Creating database 'ai_trading_engine'...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✓ Database created")
        
        # Create user (try with a secure password)
        new_password = 'trading_secure_2024'
        print(f"Creating user 'trading_user' with password...")
        
        # Drop user if exists
        cursor.execute("DROP USER IF EXISTS 'trading_user'@'localhost'")
        
        # Create user
        cursor.execute(f"CREATE USER 'trading_user'@'localhost' IDENTIFIED BY '{new_password}'")
        print("✓ User created")
        
        # Grant privileges
        cursor.execute("GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        print("✓ Privileges granted")
        
        root_conn.close()
        
        # Update .env file
        update_env_file(new_password)
        
        print(f"\n✓ MySQL setup complete!")
        print(f"✓ New password for 'trading_user': {new_password}")
        print(f"✓ .env file has been updated")
        
        return True, new_password
        
    except Exception as e:
        print(f"✗ Failed to create user/database: {e}")
        return False, None


def update_env_file(new_password):
    """Update the .env file with the new password"""
    env_file = BASE_DIR / '.env'
    
    if not env_file.exists():
        print("⚠️  .env file not found, creating from env.local...")
        env_local = BASE_DIR / 'env.local'
        if env_local.exists():
            with open(env_local, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
        else:
            print("✗ env.local not found, cannot create .env")
            return False
    
    # Read and update
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Replace password
    lines = content.split('\n')
    updated_lines = []
    for line in lines:
        if line.startswith('DB_PASSWORD='):
            updated_lines.append(f'DB_PASSWORD={new_password}')
        elif 'DATABASE_URL=' in line and 'trading_user' in line:
            # Update DATABASE_URL
            updated_lines.append(f'DATABASE_URL=mysql://trading_user:{new_password}@localhost:3306/ai_trading_engine')
        else:
            updated_lines.append(line)
    
    with open(env_file, 'w') as f:
        f.write('\n'.join(updated_lines))
    
    return True


def interactive_password_setup():
    """Interactive setup using Playwright to guide user"""
    print("\n" + "="*60)
    print("Interactive Database Setup")
    print("="*60)
    print("\nThis will help you set up your MySQL database connection.")
    print("You'll need your MySQL root password to proceed.\n")
    
    root_password = input("Enter MySQL root password (or press Enter if no password): ").strip()
    
    # Test root connection
    success, message = test_mysql_connection(user='root', password=root_password, database='mysql')
    
    if not success:
        print(f"\n✗ Cannot connect with root: {message}")
        print("\nPlease ensure:")
        print("1. MySQL server is running")
        print("2. You have the correct root password")
        print("3. MySQL is accessible on localhost:3306")
        return False
    
    print("✓ Root connection successful!")
    
    # Create user and database
    success, new_password = create_mysql_user_and_database(root_password)
    
    if success:
        print("\n" + "="*60)
        print("✓ Setup Complete!")
        print("="*60)
        print("\nYou can now run Django with:")
        print("  python manage.py runserver")
        return True
    else:
        print("\n✗ Setup failed. Please check MySQL permissions.")
        return False


def diagnose_with_playwright():
    """Use Playwright to open MySQL documentation or admin tools"""
    print("\n" + "="*60)
    print("Opening MySQL Setup Guide in Browser...")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Create a simple HTML page with instructions
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>MySQL Database Setup Guide</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #333; }
                .step { background: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #007bff; }
                .code { background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; font-family: monospace; }
                .success { color: #28a745; }
                .error { color: #dc3545; }
            </style>
        </head>
        <body>
            <h1>MySQL Database Setup Guide</h1>
            
            <div class="step">
                <h2>Step 1: Check MySQL Service</h2>
                <p>Ensure MySQL is running:</p>
                <div class="code"># Windows (as Administrator)<br>net start MySQL</div>
                <div class="code"># Or check Services: services.msc</div>
            </div>
            
            <div class="step">
                <h2>Step 2: Connect to MySQL</h2>
                <p>Open MySQL command line:</p>
                <div class="code">mysql -u root -p</div>
            </div>
            
            <div class="step">
                <h2>Step 3: Create Database and User</h2>
                <p>Run these SQL commands:</p>
                <div class="code">
CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;<br><br>
CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY 'your_secure_password';<br><br>
GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';<br><br>
FLUSH PRIVILEGES;<br><br>
EXIT;
                </div>
            </div>
            
            <div class="step">
                <h2>Step 4: Update .env File</h2>
                <p>Make sure your <code>backend/.env</code> file has:</p>
                <div class="code">
DB_USER=trading_user<br>
DB_PASSWORD=your_secure_password<br>
DB_NAME=ai_trading_engine
                </div>
            </div>
            
            <div class="step">
                <h2>Step 5: Test Connection</h2>
                <p>Run this script again or:</p>
                <div class="code">python manage.py check</div>
            </div>
        </body>
        </html>
        """
        
        # Save HTML to temp file and open it
        temp_file = BASE_DIR / 'mysql_setup_guide.html'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        file_path = temp_file.resolve().as_uri()
        page.goto(file_path)
        
        print("✓ Browser opened with setup guide")
        print("✓ Follow the instructions in the browser")
        print("\nPress Enter when done to continue...")
        input()
        
        browser.close()
        
        # Clean up
        if temp_file.exists():
            temp_file.unlink()


def main():
    """Main diagnostic function"""
    print("="*60)
    print("MySQL Database Connection Diagnostic Tool")
    print("="*60)
    
    # Get current database settings
    if DJANGO_AVAILABLE and settings:
        db_config = settings.DATABASES['default']
        db_user = db_config.get('USER', 'trading_user')
        db_password = db_config.get('PASSWORD', '')
        db_name = db_config.get('NAME', 'ai_trading_engine')
        db_host = db_config.get('HOST', 'localhost')
        db_port = db_config.get('PORT', '3306')
    else:
        # Read from .env file directly
        from decouple import config
        db_user = config('DB_USER', default='trading_user')
        db_password = config('DB_PASSWORD', default='')
        db_name = config('DB_NAME', default='ai_trading_engine')
        db_host = config('DB_HOST', default='localhost')
        db_port = config('DB_PORT', default='3306')
    
    print(f"\nCurrent Configuration:")
    print(f"  Host: {db_host}:{db_port}")
    print(f"  User: {db_user}")
    print(f"  Database: {db_name}")
    print(f"  Password: {'***' if db_password else '(empty)'}")
    
    # Test current connection
    print("\n" + "="*60)
    print("Testing current database connection...")
    print("="*60)
    
    success, message = test_mysql_connection(
        host=db_host,
        port=int(db_port),
        user=db_user,
        password=db_password,
        database=db_name
    )
    
    if success:
        print(f"✓ {message}")
        print("\n✓ Database connection is working!")
        return 0
    else:
        print(f"✗ {message}")
        
        # Try to fix automatically
        print("\n" + "="*60)
        print("Attempting automatic fix...")
        print("="*60)
        
        # Try root connection
        root_success, root_password = test_with_root_connection()
        
        if root_success:
            print("\n✓ Root connection successful! Attempting to create user...")
            success, new_password = create_mysql_user_and_database(root_password)
            
            if success:
                print("\n✓ Automatic fix successful!")
                print("✓ Please restart your Django server")
                return 0
        
        # Interactive setup
        print("\n" + "="*60)
        print("Automatic fix failed. Starting interactive setup...")
        print("="*60)
        
        choice = input("\nWould you like to:\n1. Try interactive setup (requires root password)\n2. Open setup guide in browser\n3. Exit\n\nChoice (1/2/3): ").strip()
        
        if choice == '1':
            interactive_password_setup()
        elif choice == '2':
            diagnose_with_playwright()
            # Try again after guide
            print("\nAfter following the guide, testing connection again...")
            success, message = test_mysql_connection(
                host=db_host,
                port=int(db_port),
                user=db_user,
                password=db_password,
                database=db_name
            )
            if success:
                print(f"✓ {message}")
                return 0
        else:
            print("\nExiting. Please fix the database connection manually.")
            return 1
        
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

