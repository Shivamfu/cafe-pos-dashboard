"""
Application Configuration for Velvet Roast Cafe POS Backend.
"""
import os
import shutil
from pydantic import BaseModel

def resolve_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(base_dir, "cafe_pos.db")
    
    # If running in serverless environment (e.g. Vercel), copy seed DB to writable /tmp
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_path = "/tmp/cafe_pos.db"
        if not os.path.exists(tmp_path) and os.path.exists(default_path):
            shutil.copyfile(default_path, tmp_path)
        return tmp_path
        
    return os.environ.get("DATABASE_PATH", default_path)

class Settings(BaseModel):
    CAFE_NAME: str = "Velvet Roast Cafe"
    TERMINAL_ID: str = "TERM-01"
    DEFAULT_STAFF_NAME: str = "Sarah Jenkins"
    DEFAULT_STAFF_ROLE: str = "Senior Barista"
    CURRENCY_SYMBOL: str = "₹"
    TAX_RATE: float = 0.05  # 5% GST for Cafe/Food Services
    INITIAL_DRAWER_BALANCE: float = 15000.00  # ₹15,000 opening float
    DATABASE_PATH: str = resolve_db_path()
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()
