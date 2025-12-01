#!/usr/bin/env python
"""
Helper script to create .env file from env.local
"""
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_LOCAL = BASE_DIR / 'env.local'
ENV_FILE = BASE_DIR / '.env'

if ENV_LOCAL.exists():
    shutil.copy(ENV_LOCAL, ENV_FILE)
    print(f"✓ Created .env file from env.local")
    print(f"✓ Location: {ENV_FILE}")
    print("\n⚠️  IMPORTANT: Update DB_PASSWORD in .env with your actual MySQL password!")
else:
    print(f"✗ env.local not found at {ENV_LOCAL}")

