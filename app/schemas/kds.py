from pydantic import BaseModel
from typing import Optional, List

class KDSTicketItemOut(BaseModel):
    id: str
    order_item_id: str
    item_name: str
    quantity: int
    modifiers_text: str = ""
    notes: Optional[str] = None
    is_completed: bool = False

class KDSTicketOut(BaseModel):
    id: str
    order_id: str
    table_number: str
    order_number: int
    server_name: str
    status: str  # PREPARING, READY, BUMPED, RECALLED
    is_expedited: bool = False
    delay_minutes: int = 0
    special_instructions: Optional[str] = None
    created_at: str
    elapsed_minutes: int = 0
    items: List[KDSTicketItemOut] = []

class KDSTicketUpdate(BaseModel):
    status: Optional[str] = None  # PREPARING, READY, BUMPED, RECALLED
    is_expedited: Optional[bool] = None
    delay_minutes: Optional[int] = None
