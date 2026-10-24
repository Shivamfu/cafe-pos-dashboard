"""
Cash Drawer Balance & Staff Shift Management.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.database import get_connection
from app.schemas.inventory import CashDrawerOut, DrawerAdjustmentRequest
from app.services.notifier import notifier

router = APIRouter(prefix="/api/shift", tags=["Shifts & Cash Drawer"])

@router.get("/drawer", response_model=CashDrawerOut)
async def get_drawer():
    conn = get_connection()
    cursor = conn.cursor()
    
    drawer = cursor.execute("SELECT * FROM cash_drawer WHERE status = 'OPEN' ORDER BY opened_at DESC LIMIT 1;").fetchone()
    conn.close()
    
    if not drawer:
        raise HTTPException(status_code=404, detail="No open cash drawer found for this terminal")
        
    return CashDrawerOut(
        id=drawer["id"],
        terminal_id=drawer["terminal_id"],
        staff_name=drawer["staff_name"],
        starting_cash=drawer["starting_cash"],
        current_cash=drawer["current_cash"],
        cash_sales=drawer["cash_sales"],
        cash_in=drawer["cash_in"],
        cash_out=drawer["cash_out"],
        opened_at=drawer["opened_at"],
        closed_at=drawer["closed_at"],
        status=drawer["status"]
    )

@router.post("/drawer/adjust", response_model=CashDrawerOut)
async def adjust_drawer(payload: DrawerAdjustmentRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    drawer = cursor.execute("SELECT * FROM cash_drawer WHERE status = 'OPEN' ORDER BY opened_at DESC LIMIT 1;").fetchone()
    if not drawer:
        conn.close()
        raise HTTPException(status_code=404, detail="No open cash drawer found")
        
    if payload.is_cash_in:
        cursor.execute("""
            UPDATE cash_drawer 
            SET current_cash = current_cash + ?, cash_in = cash_in + ?
            WHERE id = ?;
        """, (payload.amount, payload.amount, drawer["id"]))
    else:
        if drawer["current_cash"] < payload.amount:
            conn.close()
            raise HTTPException(status_code=400, detail="Insufficient cash in drawer for payout")
        cursor.execute("""
            UPDATE cash_drawer 
            SET current_cash = current_cash - ?, cash_out = cash_out + ?
            WHERE id = ?;
        """, (payload.amount, payload.amount, drawer["id"]))
        
    conn.commit()
    updated = cursor.execute("SELECT * FROM cash_drawer WHERE id = ?;", (drawer["id"],)).fetchone()
    conn.close()
    
    await notifier.broadcast("DRAWER_UPDATED", {"current_cash": updated["current_cash"]})
    return CashDrawerOut(
        id=updated["id"],
        terminal_id=updated["terminal_id"],
        staff_name=updated["staff_name"],
        starting_cash=updated["starting_cash"],
        current_cash=updated["current_cash"],
        cash_sales=updated["cash_sales"],
        cash_in=updated["cash_in"],
        cash_out=updated["cash_out"],
        opened_at=updated["opened_at"],
        closed_at=updated["closed_at"],
        status=updated["status"]
    )
