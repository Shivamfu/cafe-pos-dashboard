"""
Vercel Serverless Function Entry Point for FastAPI Backend.
"""
import os
import sys

# Add project root to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Initialize writable DB if needed in /tmp
from app.config import settings
from app.main import app

try:
    from app.database import init_db
    init_db()
except Exception as e:
    pass
