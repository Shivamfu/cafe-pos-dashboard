from pydantic import BaseModel, Field
from typing import Optional, List

class PaymentRequest(BaseModel):
    order_id: str
    payment_method: str = "CREDIT_CARD"  # CASH, CREDIT_CARD, DIGITAL_WALLET, GIFT_CARD
    amount: float = Field(ge=0.01)
    tip: float = Field(default=0.0, ge=0.0)
    tendered_amount: Optional[float] = None
    card_brand: Optional[str] = "Visa"
    card_last4: Optional[str] = "4242"
    split_type: str = "FULL"  # FULL, EQUAL, BY_ITEM
    seat_number: Optional[int] = None

class SplitEqualRequest(BaseModel):
    order_id: str
    split_count: int = Field(default=2, ge=2, le=20)

class SplitShareOut(BaseModel):
    share_number: int
    amount_due: float
    is_paid: bool = False

class SplitEqualOut(BaseModel):
    order_id: str
    total_amount: float
    split_count: int
    per_person_amount: float
    shares: List[SplitShareOut]

class SplitByItemRequest(BaseModel):
    order_id: str
    seat_assignments: dict[str, int]  # { order_item_id: seat_number }

class PaymentOut(BaseModel):
    id: str
    order_id: str
    payment_method: str
    amount: float
    tip: float
    total_paid: float
    tendered_amount: Optional[float] = None
    change_amount: Optional[float] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    created_at: str

class ReceiptOut(BaseModel):
    receipt_id: str
    cafe_name: str
    terminal_id: str
    order_number: int
    table_number: Optional[str] = None
    server_name: str
    created_at: str
    items: List[dict]
    subtotal: float
    tax: float
    discount: float
    tip: float
    total: float
    payments: List[PaymentOut]
    balance_remaining: float
    is_fully_paid: bool
