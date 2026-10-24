"""
Kitchen Display System (KDS) Endpoints.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.database import get_connection
from app.schemas.kds import KDSTicketOut, KDSTicketItemOut, KDSTicketUpdate
from app.services.notifier import notifier

router = APIRouter(prefix="/api/kds", tags=["Kitchen Display System (KDS)"])

@router.get("/tickets", response_model=list[KDSTicketOut])
async def list_kds_tickets(status: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM kitchen_tickets WHERE 1=1"
    params = []
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    else:
        query += " AND status != 'BUMPED'"
        
    query += " ORDER BY is_expedited DESC, created_at ASC;"
    
    tickets = cursor.execute(query, params).fetchall()
    now_utc = datetime.now(timezone.utc)
    
    results = []
    for t in tickets:
        items = cursor.execute("SELECT * FROM kitchen_ticket_items WHERE ticket_id = ?;", (t["id"],)).fetchall()
        item_list = [KDSTicketItemOut(
            id=i["id"],
            order_item_id=i["order_item_id"],
            item_name=i["item_name"],
            quantity=i["quantity"],
            modifiers_text=i["modifiers_text"] or "",
            notes=i["notes"],
            is_completed=bool(i["is_completed"])
        ) for i in items]
        
        elapsed = 0
        if t["created_at"]:
            try:
                c_dt = datetime.fromisoformat(t["created_at"])
                if c_dt.tzinfo is None:
                    c_dt = c_dt.replace(tzinfo=timezone.utc)
                elapsed = max(0, int((now_utc - c_dt).total_seconds() / 60))
            except Exception:
                pass
                
        results.append(KDSTicketOut(
            id=t["id"],
            order_id=t["order_id"],
            table_number=t["table_number"],
            order_number=t["order_number"],
            server_name=t["server_name"],
            status=t["status"],
            is_expedited=bool(t["is_expedited"]),
            delay_minutes=t["delay_minutes"],
            special_instructions=t["special_instructions"] if "special_instructions" in t.keys() else None,
            created_at=t["created_at"],
            elapsed_minutes=elapsed,
            items=item_list
        ))
        
    conn.close()
    return results

@router.patch("/tickets/{ticket_id}", response_model=KDSTicketOut)
async def update_ticket(ticket_id: str, payload: KDSTicketUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    
    ticket = cursor.execute("SELECT * FROM kitchen_tickets WHERE id = ?;", (ticket_id,)).fetchone()
    if not ticket:
        conn.close()
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    updates = []
    params = []
    now_iso = datetime.now(timezone.utc).isoformat()
    
    if payload.status:
        updates.append("status = ?")
        params.append(payload.status)
        if payload.status == "BUMPED":
            updates.append("bumped_at = ?")
            params.append(now_iso)
    if payload.is_expedited is not None:
        updates.append("is_expedited = ?")
        params.append(1 if payload.is_expedited else 0)
    if payload.delay_minutes is not None:
        updates.append("delay_minutes = delay_minutes + ?")
        params.append(payload.delay_minutes)
        
    if updates:
        params.append(ticket_id)
        cursor.execute(f"UPDATE kitchen_tickets SET {', '.join(updates)} WHERE id = ?;", params)
        conn.commit()
        
    # Re-fetch ticket
    updated = cursor.execute("SELECT * FROM kitchen_tickets WHERE id = ?;", (ticket_id,)).fetchone()
    items = cursor.execute("SELECT * FROM kitchen_ticket_items WHERE ticket_id = ?;", (ticket_id,)).fetchall()
    conn.close()
    
    item_list = [KDSTicketItemOut(
        id=i["id"],
        order_item_id=i["order_item_id"],
        item_name=i["item_name"],
        quantity=i["quantity"],
        modifiers_text=i["modifiers_text"] or "",
        notes=i["notes"],
        is_completed=bool(i["is_completed"])
    ) for i in items]
    
    await notifier.broadcast("KDS_TICKET_UPDATED", {
        "ticket_id": ticket_id,
        "table_number": updated["table_number"],
        "status": updated["status"]
    })
    
    return KDSTicketOut(
        id=updated["id"],
        order_id=updated["order_id"],
        table_number=updated["table_number"],
        order_number=updated["order_number"],
        server_name=updated["server_name"],
        status=updated["status"],
        is_expedited=bool(updated["is_expedited"]),
        delay_minutes=updated["delay_minutes"],
        special_instructions=updated["special_instructions"] if "special_instructions" in updated.keys() else None,
        created_at=updated["created_at"],
        elapsed_minutes=0,
        items=item_list
    )

@router.post("/tickets/{ticket_id}/recall")
async def recall_last_bumped_ticket(ticket_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE kitchen_tickets SET status = 'READY', bumped_at = NULL WHERE id = ?;", (ticket_id,))
    conn.commit()
    conn.close()
    await notifier.broadcast("KDS_TICKET_RECALLED", {"ticket_id": ticket_id})
    return {"message": "Ticket recalled back to active KDS board", "ticket_id": ticket_id}
