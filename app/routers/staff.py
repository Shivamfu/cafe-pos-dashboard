"""
Staff & Operator Management Endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.schemas.staff import StaffOut, StaffLoginRequest
from app.services.notifier import notifier

router = APIRouter(prefix="/api/staff", tags=["Staff & Operators"])

@router.get("", response_model=list[StaffOut])
async def list_staff():
    conn = get_connection()
    cursor = conn.cursor()
    rows = cursor.execute("SELECT id, name, role, employee_code, avatar_url, is_active FROM staff WHERE is_active = 1 ORDER BY employee_code ASC;").fetchall()
    conn.close()
    return [StaffOut(
        id=r["id"],
        name=r["name"],
        role=r["role"],
        employee_code=r["employee_code"],
        avatar_url=r["avatar_url"],
        is_active=bool(r["is_active"])
    ) for r in rows]

@router.post("/login", response_model=StaffOut)
async def login_staff(payload: StaffLoginRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    staff = cursor.execute("SELECT * FROM staff WHERE employee_code = ? AND is_active = 1;", (payload.employee_code,)).fetchone()
    if not staff:
        conn.close()
        raise HTTPException(status_code=404, detail="Employee not found with this ID")
        
    if payload.pin and staff["pin"] != payload.pin:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid 4-digit PIN for this staff member")
        
    # Update cash drawer staff name if open
    cursor.execute("UPDATE cash_drawer SET staff_name = ? WHERE status = 'OPEN';", (staff["name"],))
    conn.commit()
    conn.close()
    
    await notifier.broadcast("OPERATOR_SWITCHED", {
        "staff_id": staff["id"],
        "name": staff["name"],
        "role": staff["role"],
        "employee_code": staff["employee_code"]
    })
    
    return StaffOut(
        id=staff["id"],
        name=staff["name"],
        role=staff["role"],
        employee_code=staff["employee_code"],
        avatar_url=staff["avatar_url"],
        is_active=bool(staff["is_active"])
    )
