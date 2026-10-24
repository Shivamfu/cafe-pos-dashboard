"""
Application Configuration for Velvet Roast Cafe POS Backend.
"""
import os
from pydantic import BaseModel

class Settings(BaseModel):
    CAFE_NAME: str = "Velvet Roast Cafe"
    TERMINAL_ID: str = "TERM-01"
    DEFAULT_STAFF_NAME: str = "Sarah Jenkins"
    DEFAULT_STAFF_ROLE: str = "Senior Barista"
    CURRENCY_SYMBOL: str = "₹"
    TAX_RATE: float = 0.05  # 5% GST for Cafe/Food Services
    INITIAL_DRAWER_BALANCE: float = 15000.00  # ₹15,000 opening float
    DATABASE_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        "cafe_pos.db"
    )
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()
