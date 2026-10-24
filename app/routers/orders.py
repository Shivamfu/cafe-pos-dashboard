"""
Order Management Endpoints.
"""
from fastapi import APIRouter, HTTPException
import uuid
from datetime import datetime, timezone
from app.database import get_connection
from app.config import settings
from app.schemas.order import OrderCreate, OrderOut, OrderItemOut, AddItemsRequest, OrderItemModifierCreate
from app.services.order_service import recalculate_order, get_next_order_number, create_kds_ticket_if_needed
from app.services.notifier import notifier

router = APIRouter(prefix="/api/orders", tags=["Orders & Register"])

def fetch_order_details(cursor, order_id: str):
    order = cursor.execute("""
        SELECT o.*, dt.table_number 
        FROM orders o 
        LEFT JOIN dining_tables dt ON o.table_id = dt.id 
        WHERE o.id = ?;
    """, (order_id,)).fetchone()
    if not order:
        return None
        
    items = cursor.execute("SELECT * FROM order_items WHERE order_id = ?;", (order_id,)).fetchall()
    item_list = []
    for itm in items:
        mods = cursor.execute("SELECT modifier_name, price FROM order_item_modifiers WHERE order_item_id = ?;", (itm["id"],)).fetchall()
        mod_list = [OrderItemModifierCreate(modifier_name=m["modifier_name"], price=m["price"]) for m in mods]
        item_list.append(OrderItemOut(
            id=itm["id"],
            order_id=itm["order_id"],
            item_id=itm["item_id"],
            item_name=itm["item_name"],
            unit_price=itm["unit_price"],
            quantity=itm["quantity"],
            item_total=itm["item_total"],
            notes=itm["notes"],
            seat_number=itm["seat_number"],
            status=itm["status"],
            modifiers=mod_list
        ))
        
    return OrderOut(
        id=order["id"],
        order_number=order["order_number"],
        table_id=order["table_id"],
        table_number=order["table_number"],
        order_type=order["order_type"],
        status=order["status"],
        guest_count=order["guest_count"],
        server_name=order["server_name"],
        special_instructions=order["special_instructions"] if "special_instructions" in order.keys() else None,
        subtotal=order["subtotal"],
        tax=order["tax"],
        discount=order["discount"],
        tip=order["tip"],
        total=order["total"],
        created_at=order["created_at"],
        updated_at=order["updated_at"],
        closed_at=order["closed_at"],
        items=item_list
    )

@router.get("", response_model=list[OrderOut])
async def list_orders(status: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT id FROM orders WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    else:
        query += " AND status != 'PAID' AND status != 'CANCELLED'"
        
    query += " ORDER BY created_at DESC;"
    rows = cursor.execute(query, params).fetchall()
    
    orders = [fetch_order_details(cursor, r["id"]) for r in rows if r["id"]]
    conn.close()
    return [o for o in orders if o]

@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    order = fetch_order_details(cursor, order_id)
    conn.close()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.post("", response_model=OrderOut)
async def create_order(payload: OrderCreate):
    conn = get_connection()
    cursor = conn.cursor()
    
    table = None
    if payload.table_id:
        table = cursor.execute("SELECT * FROM dining_tables WHERE id = ?;", (payload.table_id,)).fetchone()
        if not table:
            conn.close()
            raise HTTPException(status_code=404, detail="Table not found")
            
    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    order_num = get_next_order_number(cursor)
    now_iso = datetime.now(timezone.utc).isoformat()
    server_name = payload.server_name or settings.DEFAULT_STAFF_NAME
    
    cursor.execute("""
        INSERT INTO orders 
        (id, order_number, table_id, order_type, status, guest_count, server_name, special_instructions, subtotal, tax, discount, tip, total, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, 0.0, 0.0, 0.0, 0.0, 0.0, ?, ?);
    """, (order_id, order_num, payload.table_id, payload.order_type, payload.guest_count, server_name, payload.special_instructions, now_iso, now_iso))
    
    # Add items
    for item in payload.items:
        m_item = cursor.execute("SELECT * FROM menu_items WHERE id = ?;", (item.item_id,)).fetchone()
        if not m_item:
            continue
            
        unit_price = m_item["price"]
        mod_cost = sum(m.price for m in item.modifiers)
        total_unit = unit_price + mod_cost
        item_total = round(total_unit * item.quantity, 2)
        
        oi_id = f"oi-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING');
        """, (oi_id, order_id, item.item_id, m_item["name"], unit_price, item.quantity, item_total, item.notes, item.seat_number))
        
        for m in item.modifiers:
            cursor.execute("""
                INSERT INTO order_item_modifiers (id, order_item_id, modifier_name, price)
                VALUES (?, ?, ?, ?);
            """, (f"oim-{uuid.uuid4().hex[:8]}", oi_id, m.modifier_name, m.price))
            
    # Calculate totals
    recalculate_order(cursor, order_id)
    
    # Bind to table if Dine-In
    if table:
        cursor.execute("""
            UPDATE dining_tables 
            SET current_order_id = ?, status = 'Occupied', guest_count = ?, seated_at = COALESCE(seated_at, ?)
            WHERE id = ?;
        """, (order_id, payload.guest_count, now_iso, table["id"]))
        
    # Auto-send to KDS
    tbl_num = table["table_number"] if table else f"Takeaway #{order_num}"
    create_kds_ticket_if_needed(cursor, order_id, tbl_num, order_num, server_name, payload.special_instructions)
    
    conn.commit()
    order_data = fetch_order_details(cursor, order_id)
    conn.close()
    
    await notifier.broadcast("ORDER_CREATED", {
        "order_id": order_id,
        "order_number": order_num,
        "table_number": tbl_num,
        "total": order_data.total
    })
    await notifier.broadcast("KDS_UPDATED", {
        "order_id": order_id,
        "order_number": order_num
    })
    
    return order_data

@router.post("/{order_id}/items", response_model=OrderOut)
async def add_items_to_order(order_id: str, payload: AddItemsRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    order = cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
        
    for item in payload.items:
        m_item = cursor.execute("SELECT * FROM menu_items WHERE id = ?;", (item.item_id,)).fetchone()
        if not m_item:
            continue
            
        unit_price = m_item["price"]
        mod_cost = sum(m.price for m in item.modifiers)
        total_unit = unit_price + mod_cost
        item_total = round(total_unit * item.quantity, 2)
        
        oi_id = f"oi-{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING');
        """, (oi_id, order_id, item.item_id, m_item["name"], unit_price, item.quantity, item_total, item.notes, item.seat_number))
        
        for m in item.modifiers:
            cursor.execute("""
                INSERT INTO order_item_modifiers (id, order_item_id, modifier_name, price)
                VALUES (?, ?, ?, ?);
            """, (f"oim-{uuid.uuid4().hex[:8]}", oi_id, m.modifier_name, m.price))
            
    recalculate_order(cursor, order_id)
    
    # If table is assigned, ensure status reflects occupied
    if order["table_id"]:
        cursor.execute("UPDATE dining_tables SET status = 'Occupied' WHERE id = ?;", (order["table_id"],))
        
    conn.commit()
    order_data = fetch_order_details(cursor, order_id)
    conn.close()
    
    await notifier.broadcast("ORDER_UPDATED", {"order_id": order_id, "total": order_data.total})
    return order_data

@router.delete("/{order_id}/items/{item_id}", response_model=OrderOut)
async def remove_item_from_order(order_id: str, item_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE order_items SET status = 'CANCELLED' WHERE id = ? AND order_id = ?;", (item_id, order_id))
    recalculate_order(cursor, order_id)
    
    conn.commit()
    order_data = fetch_order_details(cursor, order_id)
    conn.close()
    
    await notifier.broadcast("ORDER_UPDATED", {"order_id": order_id, "total": order_data.total})
    return order_data
