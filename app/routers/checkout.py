"""
Billing, Payment, Checkout, and Split Bill Endpoints.
"""
from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime, timezone
from app.database import get_connection
from app.config import settings
from app.schemas.payment import (
    PaymentRequest, PaymentOut, SplitEqualRequest, SplitEqualOut, 
    SplitShareOut, SplitByItemRequest, ReceiptOut
)
from app.services.notifier import notifier

router = APIRouter(prefix="/api/checkout", tags=["Checkout & Payments"])

@router.get("/preview/{order_id}")
async def get_checkout_preview(order_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    order = cursor.execute("""
        SELECT o.*, dt.table_number 
        FROM orders o 
        LEFT JOIN dining_tables dt ON o.table_id = dt.id 
        WHERE o.id = ?;
    """, (order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
        
    items = cursor.execute("""
        SELECT oi.*, 
               (SELECT GROUP_CONCAT(oim.modifier_name, ', ') 
                FROM order_item_modifiers oim WHERE oim.order_item_id = oi.id) as modifiers_text
        FROM order_items oi
        WHERE oi.order_id = ? AND oi.status != 'CANCELLED';
    """, (order_id,)).fetchall()
    
    payments = cursor.execute("SELECT * FROM payments WHERE order_id = ?;", (order_id,)).fetchall()
    paid_so_far = sum(p["amount"] for p in payments)
    balance_due = round(max(0.0, order["total"] - paid_so_far), 2)
    
    # Suggested tips (15%, 18%, 20%, 25%)
    subtotal = order["subtotal"]
    suggested_tips = {
        "15%": round(subtotal * 0.15, 2),
        "18%": round(subtotal * 0.18, 2),
        "20%": round(subtotal * 0.20, 2),
        "25%": round(subtotal * 0.25, 2),
    }
    
    conn.close()
    return {
        "order_id": order["id"],
        "order_number": order["order_number"],
        "table_number": order["table_number"] or "Takeaway",
        "guest_count": order["guest_count"],
        "server_name": order["server_name"],
        "items": [dict(i) for i in items],
        "subtotal": order["subtotal"],
        "tax": order["tax"],
        "discount": order["discount"],
        "total": order["total"],
        "paid_so_far": round(paid_so_far, 2),
        "balance_due": balance_due,
        "is_fully_paid": balance_due <= 0.01,
        "suggested_tips": suggested_tips
    }

@router.post("/split-equal", response_model=SplitEqualOut)
async def split_bill_equally(payload: SplitEqualRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    order = cursor.execute("SELECT total FROM orders WHERE id = ?;", (payload.order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
        
    total = order["total"]
    per_person = round(total / payload.split_count, 2)
    
    # Fetch existing payments
    payments = cursor.execute("SELECT * FROM payments WHERE order_id = ? AND split_type = 'EQUAL';", (payload.order_id,)).fetchall()
    paid_shares_count = len(payments)
    
    shares = []
    for i in range(1, payload.split_count + 1):
        shares.append(SplitShareOut(
            share_number=i,
            amount_due=per_person,
            is_paid=(i <= paid_shares_count)
        ))
        
    conn.close()
    return SplitEqualOut(
        order_id=payload.order_id,
        total_amount=total,
        split_count=payload.split_count,
        per_person_amount=per_person,
        shares=shares
    )

@router.post("/pay", response_model=PaymentOut)
async def process_payment(payload: PaymentRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    order = cursor.execute("""
        SELECT o.*, dt.table_number, dt.id as table_primary_id 
        FROM orders o 
        LEFT JOIN dining_tables dt ON o.table_id = dt.id 
        WHERE o.id = ?;
    """, (payload.order_id,)).fetchone()
    
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
        
    # Check already paid amount
    past_payments = cursor.execute("SELECT SUM(amount) as paid FROM payments WHERE order_id = ?;", (payload.order_id,)).fetchone()
    already_paid = past_payments["paid"] or 0.0
    balance_remaining = round(max(0.0, order["total"] - already_paid), 2)
    
    if balance_remaining <= 0.00:
        conn.close()
        raise HTTPException(status_code=400, detail="Order is already fully paid")
        
    payment_amount = min(payload.amount, balance_remaining)
    total_paid = round(payment_amount + payload.tip, 2)
    
    change_amount = None
    if payload.payment_method == "CASH" and payload.tendered_amount:
        if payload.tendered_amount < total_paid:
            conn.close()
            raise HTTPException(status_code=400, detail="Tendered amount is less than total due")
        change_amount = round(payload.tendered_amount - total_paid, 2)
        
    payment_id = f"pay-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO payments 
        (id, order_id, payment_method, amount, tip, total_paid, tendered_amount, change_amount, card_brand, card_last4, split_type, seat_number, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        payment_id, payload.order_id, payload.payment_method, payment_amount, payload.tip, 
        total_paid, payload.tendered_amount, change_amount, payload.card_brand, payload.card_last4,
        payload.split_type, payload.seat_number, now_iso
    ))
    
    # Update cash drawer if paid in cash
    if payload.payment_method == "CASH":
        cursor.execute("""
            UPDATE cash_drawer 
            SET current_cash = current_cash + ?, cash_sales = cash_sales + ?
            WHERE status = 'OPEN';
        """, (payment_amount, payment_amount))
        
    # Check if order is now fully settled
    new_total_paid = already_paid + payment_amount
    is_settled = new_total_paid >= (order["total"] - 0.01)
    
    if is_settled:
        # Mark order PAID
        cursor.execute("""
            UPDATE orders 
            SET status = 'PAID', tip = tip + ?, closed_at = ?
            WHERE id = ?;
        """, (payload.tip, now_iso, payload.order_id))
        
        # Release table to Available
        if order["table_primary_id"]:
            cursor.execute("""
                UPDATE dining_tables 
                SET current_order_id = NULL, status = 'Available', guest_count = 0, seated_at = NULL
                WHERE id = ?;
            """, (order["table_primary_id"],))
    else:
        # If bill not fully paid but in progress, mark table Bill Pending
        if order["table_primary_id"]:
            cursor.execute("UPDATE dining_tables SET status = 'Bill Pending' WHERE id = ?;", (order["table_primary_id"],))
            
    conn.commit()
    conn.close()
    
    await notifier.broadcast("PAYMENT_PROCESSED", {
        "order_id": payload.order_id,
        "amount_paid": payment_amount,
        "is_settled": is_settled,
        "table_number": order["table_number"]
    })
    await notifier.broadcast("ANALYTICS_UPDATED", {
        "order_id": payload.order_id,
        "amount_paid": payment_amount
    })
    
    return PaymentOut(
        id=payment_id,
        order_id=payload.order_id,
        payment_method=payload.payment_method,
        amount=payment_amount,
        tip=payload.tip,
        total_paid=total_paid,
        tendered_amount=payload.tendered_amount,
        change_amount=change_amount,
        card_brand=payload.card_brand,
        card_last4=payload.card_last4,
        created_at=now_iso
    )

@router.get("/receipt/{order_id}", response_model=ReceiptOut)
async def get_receipt(order_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    order = cursor.execute("""
        SELECT o.*, dt.table_number 
        FROM orders o 
        LEFT JOIN dining_tables dt ON o.table_id = dt.id 
        WHERE o.id = ?;
    """, (order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
        
    items = cursor.execute("""
        SELECT oi.*, 
               (SELECT GROUP_CONCAT(oim.modifier_name, ', ') 
                FROM order_item_modifiers oim WHERE oim.order_item_id = oi.id) as modifiers_text
        FROM order_items oi
        WHERE oi.order_id = ? AND oi.status != 'CANCELLED';
    """, (order_id,)).fetchall()
    
    payments = cursor.execute("SELECT * FROM payments WHERE order_id = ?;", (order_id,)).fetchall()
    payment_list = [PaymentOut(
        id=p["id"],
        order_id=p["order_id"],
        payment_method=p["payment_method"],
        amount=p["amount"],
        tip=p["tip"],
        total_paid=p["total_paid"],
        tendered_amount=p["tendered_amount"],
        change_amount=p["change_amount"],
        card_brand=p["card_brand"],
        card_last4=p["card_last4"],
        created_at=p["created_at"]
    ) for p in payments]
    
    total_paid = sum(p["amount"] for p in payments)
    balance_remaining = round(max(0.0, order["total"] - total_paid), 2)
    
    conn.close()
    return ReceiptOut(
        receipt_id=f"rec-{order['order_number']:05d}",
        cafe_name=settings.CAFE_NAME,
        terminal_id=settings.TERMINAL_ID,
        order_number=order["order_number"],
        table_number=order["table_number"],
        server_name=order["server_name"],
        created_at=order["created_at"],
        items=[dict(i) for i in items],
        subtotal=order["subtotal"],
        tax=order["tax"],
        discount=order["discount"],
        tip=order["tip"],
        total=order["total"],
        payments=payment_list,
        balance_remaining=balance_remaining,
        is_fully_paid=(balance_remaining <= 0.01)
    )
