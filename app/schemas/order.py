from pydantic import BaseModel, Field
from typing import Optional, List

class OrderItemModifierCreate(BaseModel):
    modifier_name: str
    price: float = 0.0

class OrderItemCreate(BaseModel):
    item_id: str
    quantity: int = Field(default=1, ge=1)
    notes: Optional[str] = None
    seat_number: int = 1
    modifiers: List[OrderItemModifierCreate] = []

class OrderItemOut(BaseModel):
    id: str
    order_id: str
    item_id: str
    item_name: str
    unit_price: float
    quantity: int
    item_total: float
    notes: Optional[str] = None
    seat_number: int
    status: str
    modifiers: List[OrderItemModifierCreate] = []

class OrderCreate(BaseModel):
    table_id: Optional[str] = None
    order_type: str = "DINE_IN"  # DINE_IN, TAKEAWAY
    guest_count: int = 1
    server_name: Optional[str] = None
    special_instructions: Optional[str] = None
    items: List[OrderItemCreate] = []

class OrderOut(BaseModel):
    id: str
    order_number: int
    table_id: Optional[str] = None
    table_number: Optional[str] = None
    order_type: str
    status: str
    guest_count: int
    server_name: str
    special_instructions: Optional[str] = None
    subtotal: float
    tax: float
    discount: float
    tip: float
    total: float
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    items: List[OrderItemOut] = []

class AddItemsRequest(BaseModel):
    items: List[OrderItemCreate]
