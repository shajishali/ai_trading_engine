#!/usr/bin/env python3
"""
Setup script for AI-Enhanced Trading Signal Engine
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error during {description}: {e}")
        print(f"Error output: {e.stderr}")
        return False


def main():
    """Main setup function"""
    print("🚀 Setting up AI-Enhanced Trading Signal Engine")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("manage.py").exists():
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Step 1: Create virtual environment
    if not Path("venv").exists():
        print("\n📦 Creating virtual environment...")
        if not run_command("python -m venv venv", "Creating virtual environment"):
            sys.exit(1)
    
    # Step 2: Activate virtual environment and install dependencies
    print("\n📦 Installing dependencies...")
    if os.name == 'nt':  # Windows
        activate_cmd = "venv\\Scripts\\activate"
        pip_cmd = "venv\\Scripts\\pip install -r requirements.txt"
    else:  # Unix/Linux/Mac
        activate_cmd = "source venv/bin/activate"
        pip_cmd = "venv/bin/pip install -r requirements.txt"
    
    if not run_command(pip_cmd, "Installing Python dependencies"):
        sys.exit(1)
    
    # Step 3: Run migrations
    if not run_command("python manage.py migrate", "Running database migrations"):
        sys.exit(1)
    
    # Step 4: Create superuser
    print("\n👤 Creating superuser...")
    print("Username: admin")
    print("Email: admin@example.com")
    print("Password: admin123")
    
    # Create superuser with default password
    superuser_cmd = 'python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_superuser(\'admin\', \'admin@example.com\', \'admin123\') if not User.objects.filter(username=\'admin\').exists() else print(\'Superuser already exists\')"'
    
    if not run_command(superuser_cmd, "Creating superuser"):
        print("⚠️  Superuser creation failed, you can create one manually later")
    
    # Step 5: Setup sample data
    if not run_command("python manage.py setup_sample_data", "Setting up sample data"):
        print("⚠️  Sample data setup failed")
    
    # Step 6: Create environment file
    env_content = """# Django Settings
DEBUG=True
SECRET_KEY=django-insecure-v%kz(i_y%6y1v7^l9i2i9kxx$s1ia&u5f#_7ww&m7mj)4yi7bd
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration (using SQLite for development)
DATABASE_URL=sqlite:///db.sqlite3

# Redis Configuration (for Celery)
REDIS_URL=redis://localhost:6379/0

# Trading Configuration
DEFAULT_CURRENCY=USD
RISK_PERCENTAGE=2.0
MAX_POSITION_SIZE=10.0

# AI Model Configuration
MODEL_UPDATE_FREQUENCY=3600
SIGNAL_CONFIDENCE_THRESHOLD=0.7

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_engine.log

# Security
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✓ Environment file created")
    except Exception as e:
        print(f"⚠️  Could not create .env file: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Activate the virtual environment:")
    if os.name == 'nt':
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    
    print("\n2. Start the development server:")
    print("   python manage.py runserver")
    
    print("\n3. Access the application:")
    print("   - Home page: http://localhost:8000/")
    print("   - Admin panel: http://localhost:8000/admin/")
    print("   - Dashboard: http://localhost:8000/dashboard/")
    
    print("\n4. Admin credentials:")
    print("   Username: admin")
    print("   Password: admin123")
    
    print("\n📚 For more information, see README.md")
    print("=" * 50)


if __name__ == "__main__":
    main()
