from pydantic import BaseModel, Field
from typing import Optional

class InventoryItemOut(BaseModel):
    id: str
    name: str
    category: str
    current_stock: float
    unit: str
    reorder_threshold: float
    cost_per_unit: float
    status: str

class RestockRequest(BaseModel):
    quantity_added: float = Field(gt=0)

class StockAdjustRequest(BaseModel):
    delta: float  # can be positive (add) or negative (use/deplete)

class CashDrawerOut(BaseModel):
    id: str
    terminal_id: str
    staff_name: str
    starting_cash: float
    current_cash: float
    cash_sales: float
    cash_in: float
    cash_out: float
    opened_at: str
    closed_at: Optional[str] = None
    status: str

class DrawerAdjustmentRequest(BaseModel):
    amount: float = Field(gt=0)
    reason: str
    is_cash_in: bool = True  # True = cash in, False = cash out (paid out)
