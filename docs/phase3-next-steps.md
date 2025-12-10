# Phase 3: Next Steps After Cloning Repository
**Status**: Repository Cloned ✅ → Continue with Setup

---

## 🎯 What You've Completed

✅ **Phase 0**: Pre-Deployment Preparation  
✅ **Phase 1**: Server Initial Setup & Security  
✅ **Phase 2**: Database Setup (MySQL)  
✅ **Phase 3.1**: Clone Repository

---

## 🚀 Next Steps (In Order)

### Step 1: Navigate to Backend Directory

```bash
# Make sure you're in the right directory
cd ~/trading-engine/backend

# Verify you're in the correct location
pwd
# Should show: /home/tradingengine/trading-engine/backend

# Check that manage.py exists
ls -la manage.py
```

---

### Step 2: Create Virtual Environment

```bash
# Create Python virtual environment
python3.10 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# You should see (venv) in your prompt now
# Upgrade pip and essential tools
pip install --upgrade pip setuptools wheel
```

**Note**: You'll need to activate the virtual environment every time you work with the project:
```bash
source venv/bin/activate
```

---

### Step 3: Install Python Dependencies

```bash
# Make sure virtual environment is activated
# (You should see (venv) in your prompt)

# Install all dependencies from requirements.txt
pip install -r requirements.txt

# This may take a few minutes
# Watch for any errors, especially with mysqlclient
```

**If mysqlclient installation fails**, use PyMySQL instead:
```bash
# PyMySQL is already in requirements.txt, but if needed:
pip install pymysql
```

**Verify key packages installed**:
```bash
pip list | grep -E "(django|celery|redis|mysql|gunicorn)"
```

---

### Step 4: Configure Environment Variables

**Option A: Upload .env file from Windows (Easier)**

1. **On Windows**: 
   - Open `backend/env.production.template` in Notepad++
   - Fill in all the values (you already have SECRET_KEY)
   - Save as `.env` (make sure it's `.env`, not `.env.txt`)

2. **Upload using WinSCP**:
   - Connect to server with WinSCP
   - Navigate to `/home/tradingengine/trading-engine/backend/`
   - Drag and drop your `.env` file from Windows

**Option B: Create .env on Server**

```bash
# Copy the template
cp env.production.template .env

# Edit the .env file
nano .env
```

**Required values to fill in**:
```bash
# Django Core Settings
DEBUG=False
SECRET_KEY=your-secret-key-here  # You already have this
PRODUCTION_SECRET_KEY=your-secret-key-here  # Same as SECRET_KEY
ALLOWED_HOSTS=52.221.248.235  # Your server IP
PRODUCTION_ALLOWED_HOSTS=52.221.248.235

# Database Configuration (MySQL) - Use values from Phase 2
DB_ENGINE=django.db.backends.mysql
DB_NAME=trading_engine_db
DB_USER=tradingengine_user
DB_PASSWORD=your-database-password-here  # From Phase 2
DB_HOST=localhost
DB_PORT=3306

# Redis Configuration
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=2

# AWS S3 (Set to False for local storage)
USE_S3=False

# CORS Configuration (use your IP or domain)
CORS_ALLOWED_ORIGINS=http://52.221.248.235
```

**After editing, save and exit**:
- In nano: Press `Ctrl+X`, then `Y`, then `Enter`

**Secure the .env file**:
```bash
chmod 600 .env
```

---

### Step 5: Verify Production Settings

**Check that settings_production.py uses MySQL** (should already be configured):

```bash
# Check database configuration
grep -A 10 "DATABASES = {" ai_trading_engine/settings_production.py

# Should show:
# 'ENGINE': 'django.db.backends.mysql',
```

**If it shows PostgreSQL**, you need to update it (see Phase 3.5 in deployment plan).

---

### Step 6: Run Database Migrations

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Set production settings
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production

# Run migrations
python manage.py migrate

# This will create all database tables
# Watch for any errors
```

**If you see database connection errors**:
- Check that MySQL is running: `sudo systemctl status mysql`
- Verify database credentials in `.env` file
- Test database connection: `mysql -u tradingengine_user -p trading_engine_db`

---

### Step 7: Create Superuser (Optional but Recommended)

```bash
# Create Django admin superuser
python manage.py createsuperuser

# Follow prompts:
# - Username: (choose a username)
# - Email: (your email)
# - Password: (strong password)
```

---

### Step 8: Collect Static Files

```bash
# Collect all static files
python manage.py collectstatic --noinput

# This collects files to backend/staticfiles/ when USE_S3=False
# Verify files were collected
ls -la staticfiles/

# You should see admin/, images/, etc.
```

---

### Step 9: Test Application Locally

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Set production settings
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production

# Start Django development server
python manage.py runserver 0.0.0.0:8000
```

**In another PuTTY terminal** (open a new PuTTY session), test:

```bash
# Test from server
curl http://localhost:8000

# Test static files
curl http://localhost:8000/static/admin/css/base.css
```

**If successful**, stop the server in the first terminal:
- Press `Ctrl+C`

---

## ✅ Phase 3 Checklist

After completing all steps above, verify:

- [ ] Virtual environment created and activated
- [ ] All Python dependencies installed (`pip list` shows Django, Celery, etc.)
- [ ] `.env` file created with all required values
- [ ] Database migrations completed successfully
- [ ] Static files collected (`staticfiles/` directory exists)
- [ ] Application runs locally (`python manage.py runserver` works)
- [ ] Database connection works (no errors in migrations)

---

## 🚀 What's Next After Phase 3?

Once Phase 3 is complete, you'll proceed to:

1. **Phase 4**: Redis Setup (15-20 min)
2. **Phase 5**: Celery Setup (30-45 min)
3. **Phase 6**: Gunicorn Setup (20-30 min)
4. **Phase 7**: Nginx Configuration (30-45 min)
5. **Phase 8-12**: Monitoring, Backups, Security, Testing

---

## 🆘 Troubleshooting

### "Command not found: python3.10"
```bash
# Check Python version
python3 --version

# If Python 3.10 not available, use:
python3 -m venv venv
```

### "mysqlclient installation failed"
```bash
# Install system dependencies first
sudo apt install -y default-libmysqlclient-dev pkg-config

# Then try again
pip install mysqlclient

# Or use PyMySQL (already in requirements.txt)
pip install pymysql
```

### "ModuleNotFoundError: No module named 'decouple'"
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Install missing package
pip install python-decouple
```

### "Database connection error"
```bash
# Test MySQL connection
mysql -u tradingengine_user -p trading_engine_db

# Check MySQL is running
sudo systemctl status mysql

# Verify .env file has correct database credentials
cat .env | grep DB_
```

---

## 📝 Quick Reference Commands

```bash
# Always start with these when working on the project:
cd ~/trading-engine/backend
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production

# Then run Django commands:
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
```

---

**Ready to continue?** Start with Step 1 above! 🚀

