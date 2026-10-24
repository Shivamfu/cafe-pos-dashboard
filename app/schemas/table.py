from pydantic import BaseModel
from typing import Optional, List

class TableBase(BaseModel):
    table_number: str
    section_id: str
    capacity: int
    status: str
    guest_count: int = 0
    seated_at: Optional[str] = None
    current_order_id: Optional[str] = None
    x_pos: int = 0
    y_pos: int = 0
    reservation_note: Optional[str] = None

class TableOut(TableBase):
    id: str
    section_name: Optional[str] = None
    elapsed_minutes: Optional[int] = None
    current_bill_total: Optional[float] = None
    current_item_count: Optional[int] = None

class TableStatusUpdate(BaseModel):
    status: str  # Available, Occupied, Bill Pending, Reserved, Cleaning
    guest_count: Optional[int] = None
    reservation_note: Optional[str] = None

class TableTransferRequest(BaseModel):
    target_table_id: str

class SectionOut(BaseModel):
    id: str
    name: str
    display_order: int
    total_tables: int = 0
    occupied_tables: int = 0
    available_tables: int = 0
    bill_pending_tables: int = 0
