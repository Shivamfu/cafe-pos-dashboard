"""
Order Service handling calculation, table binding, and KDS synchronization.
"""
import uuid
import sqlite3
from datetime import datetime, timezone
from app.config import settings
from app.database import get_connection

def recalculate_order(cursor: sqlite3.Cursor, order_id: str):
    # Sum up order items
    items = cursor.execute("""
        SELECT SUM(item_total) as subtotal FROM order_items 
        WHERE order_id = ? AND status != 'CANCELLED';
    """, (order_id,)).fetchone()
    
    subtotal = round(items["subtotal"] or 0.0, 2)
    tax = round(subtotal * settings.TAX_RATE, 2)
    
    # Get current discount and tip
    order_row = cursor.execute("SELECT discount, tip FROM orders WHERE id = ?;", (order_id,)).fetchone()
    discount = order_row["discount"] if order_row else 0.0
    tip = order_row["tip"] if order_row else 0.0
    
    total = round(max(0.0, subtotal - discount + tax + tip), 2)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        UPDATE orders 
        SET subtotal = ?, tax = ?, total = ?, updated_at = ?
        WHERE id = ?;
    """, (subtotal, tax, total, now_iso, order_id))
    
    return subtotal, tax, total

def get_next_order_number(cursor: sqlite3.Cursor) -> int:
    row = cursor.execute("SELECT MAX(order_number) as max_num FROM orders;").fetchone()
    return (row["max_num"] or 100) + 1

def create_kds_ticket_if_needed(cursor: sqlite3.Cursor, order_id: str, table_number: str, order_num: int, server_name: str, special_instructions: str = None):
    # Fetch all items in this order for kitchen & barista prep rail
    kitchen_items = cursor.execute("""
        SELECT oi.id, oi.item_name, oi.quantity, oi.notes,
               (SELECT GROUP_CONCAT(oim.modifier_name, ', ') 
                FROM order_item_modifiers oim WHERE oim.order_item_id = oi.id) as mods
        FROM order_items oi
        WHERE oi.order_id = ? AND oi.status != 'CANCELLED';
    """, (order_id,)).fetchall()
    
    if not kitchen_items:
        return None
        
    ticket_id = f"kds-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO kitchen_tickets 
        (id, order_id, table_number, order_number, server_name, special_instructions, status, is_expedited, delay_minutes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'PREPARING', 0, 0, ?);
    """, (ticket_id, order_id, table_number, order_num, server_name, special_instructions, now_iso))
    
    for item in kitchen_items:
        cursor.execute("""
            INSERT INTO kitchen_ticket_items 
            (id, ticket_id, order_item_id, item_name, quantity, modifiers_text, notes, is_completed)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0);
        """, (f"kti-{uuid.uuid4().hex[:8]}", ticket_id, item["id"], item["item_name"], item["quantity"], item["mods"] or "", item["notes"] or ""))
        
    return ticket_id
