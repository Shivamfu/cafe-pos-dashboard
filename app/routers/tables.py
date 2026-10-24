"""
Dining Tables and Floor Plan Endpoints.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import math
from app.database import get_connection
from app.schemas.table import TableOut, TableStatusUpdate, TableTransferRequest, SectionOut
from app.services.notifier import notifier

router = APIRouter(prefix="/api", tags=["Floor Plan & Tables"])

@router.get("/tables", response_model=list[TableOut])
async def list_tables(section_id: str = None, status: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT dt.*, s.name as section_name,
               o.total as current_bill_total,
               (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = dt.current_order_id AND oi.status != 'CANCELLED') as current_item_count
        FROM dining_tables dt
        JOIN sections s ON dt.section_id = s.id
        LEFT JOIN orders o ON dt.current_order_id = o.id
        WHERE 1=1
    """
    params = []
    if section_id:
        query += " AND dt.section_id = ?"
        params.append(section_id)
    if status and status != "All":
        query += " AND dt.status = ?"
        params.append(status)
        
    query += " ORDER BY dt.table_number ASC;"
    
    rows = cursor.execute(query, params).fetchall()
    now_utc = datetime.now(timezone.utc)
    
    results = []
    for r in rows:
        elapsed = None
        if r["seated_at"]:
            try:
                seated_dt = datetime.fromisoformat(r["seated_at"])
                if seated_dt.tzinfo is None:
                    seated_dt = seated_dt.replace(tzinfo=timezone.utc)
                elapsed = max(0, int((now_utc - seated_dt).total_seconds() / 60))
            except Exception:
                pass
                
        results.append(TableOut(
            id=r["id"],
            table_number=r["table_number"],
            section_id=r["section_id"],
            section_name=r["section_name"],
            capacity=r["capacity"],
            status=r["status"],
            guest_count=r["guest_count"],
            seated_at=r["seated_at"],
            current_order_id=r["current_order_id"],
            x_pos=r["x_pos"] or 0,
            y_pos=r["y_pos"] or 0,
            reservation_note=r["reservation_note"],
            elapsed_minutes=elapsed,
            current_bill_total=r["current_bill_total"] or 0.0,
            current_item_count=r["current_item_count"] or 0
        ))
        
    conn.close()
    return results

@router.get("/tables/{table_id}")
async def get_table(table_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    table = cursor.execute("""
        SELECT dt.*, s.name as section_name, o.order_number, o.total as bill_total, o.status as order_status
        FROM dining_tables dt
        JOIN sections s ON dt.section_id = s.id
        LEFT JOIN orders o ON dt.current_order_id = o.id
        WHERE dt.id = ? OR dt.table_number = ?;
    """, (table_id, table_id)).fetchone()
    
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Table not found")
        
    order_items = []
    if table["current_order_id"]:
        items = cursor.execute("""
            SELECT oi.*, 
                   (SELECT GROUP_CONCAT(oim.modifier_name, ', ') 
                    FROM order_item_modifiers oim WHERE oim.order_item_id = oi.id) as modifiers_text
            FROM order_items oi
            WHERE oi.order_id = ? AND oi.status != 'CANCELLED';
        """, (table["current_order_id"],)).fetchall()
        order_items = [dict(i) for i in items]
        
    conn.close()
    return {
        "table": dict(table),
        "order_items": order_items
    }

@router.patch("/tables/{table_id}/status")
async def update_table_status(table_id: str, payload: TableStatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    
    table = cursor.execute("SELECT * FROM dining_tables WHERE id = ? OR table_number = ?;", (table_id, table_id)).fetchone()
    if not table:
        conn.close()
        raise HTTPException(status_code=404, detail="Table not found")
        
    now_iso = datetime.now(timezone.utc).isoformat()
    seated_at = table["seated_at"]
    
    # If transitioning to Occupied and seated_at is empty, start timer
    if payload.status == "Occupied" and not seated_at:
        seated_at = now_iso
    elif payload.status == "Available":
        seated_at = None
        
    guest_count = payload.guest_count if payload.guest_count is not None else table["guest_count"]
    reservation_note = payload.reservation_note if payload.reservation_note is not None else table["reservation_note"]
    
    cursor.execute("""
        UPDATE dining_tables 
        SET status = ?, guest_count = ?, seated_at = ?, reservation_note = ?
        WHERE id = ?;
    """, (payload.status, guest_count, seated_at, reservation_note, table["id"]))
    
    conn.commit()
    conn.close()
    
    # Broadcast live event
    await notifier.broadcast("TABLE_STATUS_UPDATED", {
        "table_id": table["id"],
        "table_number": table["table_number"],
        "status": payload.status,
        "guest_count": guest_count
    })
    
    return {"message": "Table status updated successfully", "table_id": table["id"], "status": payload.status}

@router.post("/tables/{table_id}/transfer")
async def transfer_table(table_id: str, payload: TableTransferRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    src = cursor.execute("SELECT * FROM dining_tables WHERE id = ?;", (table_id,)).fetchone()
    tgt = cursor.execute("SELECT * FROM dining_tables WHERE id = ?;", (payload.target_table_id,)).fetchone()
    
    if not src or not tgt:
        conn.close()
        raise HTTPException(status_code=404, detail="Source or target table not found")
        
    if not src["current_order_id"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Source table has no active order to transfer")
        
    order_id = src["current_order_id"]
    
    # Update target table
    cursor.execute("""
        UPDATE dining_tables 
        SET current_order_id = ?, status = 'Occupied', guest_count = ?, seated_at = ?
        WHERE id = ?;
    """, (order_id, src["guest_count"], src["seated_at"], tgt["id"]))
    
    # Release source table
    cursor.execute("""
        UPDATE dining_tables 
        SET current_order_id = NULL, status = 'Cleaning', guest_count = 0, seated_at = NULL
        WHERE id = ?;
    """, (src["id"],))
    
    # Update order
    cursor.execute("UPDATE orders SET table_id = ? WHERE id = ?;", (tgt["id"], order_id))
    
    # Update any active kitchen tickets
    cursor.execute("UPDATE kitchen_tickets SET table_number = ? WHERE order_id = ?;", (tgt["table_number"], order_id))
    
    conn.commit()
    conn.close()
    
    await notifier.broadcast("TABLE_TRANSFERRED", {
        "from_table": src["table_number"],
        "to_table": tgt["table_number"],
        "order_id": order_id
    })
    
    return {"message": f"Transferred order from {src['table_number']} to {tgt['table_number']}"}

@router.get("/sections", response_model=list[SectionOut])
async def list_sections():
    conn = get_connection()
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT s.id, s.name, s.display_order,
               COUNT(dt.id) as total_tables,
               SUM(CASE WHEN dt.status = 'Occupied' THEN 1 ELSE 0 END) as occupied_tables,
               SUM(CASE WHEN dt.status = 'Available' THEN 1 ELSE 0 END) as available_tables,
               SUM(CASE WHEN dt.status = 'Bill Pending' THEN 1 ELSE 0 END) as bill_pending_tables
        FROM sections s
        LEFT JOIN dining_tables dt ON s.id = dt.section_id
        GROUP BY s.id
        ORDER BY s.display_order ASC;
    """).fetchall()
    
    conn.close()
    return [SectionOut(
        id=r["id"],
        name=r["name"],
        display_order=r["display_order"],
        total_tables=r["total_tables"] or 0,
        occupied_tables=r["occupied_tables"] or 0,
        available_tables=r["available_tables"] or 0,
        bill_pending_tables=r["bill_pending_tables"] or 0
    ) for r in rows]
