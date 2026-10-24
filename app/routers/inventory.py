"""
Inventory & Stock Tracker Endpoints.
"""
from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.schemas.inventory import InventoryItemOut, RestockRequest, StockAdjustRequest
from app.services.notifier import notifier

router = APIRouter(prefix="/api/inventory", tags=["Inventory & Stock"])

@router.get("", response_model=list[InventoryItemOut])
async def list_inventory():
    conn = get_connection()
    cursor = conn.cursor()
    
    rows = cursor.execute("SELECT * FROM inventory_items ORDER BY name ASC;").fetchall()
    results = [InventoryItemOut(
        id=r["id"],
        name=r["name"],
        category=r["category"],
        current_stock=r["current_stock"],
        unit=r["unit"],
        reorder_threshold=r["reorder_threshold"],
        cost_per_unit=r["cost_per_unit"],
        status=r["status"]
    ) for r in rows]
    
    conn.close()
    return results

@router.post("/{item_id}/adjust", response_model=InventoryItemOut)
async def adjust_stock(item_id: str, payload: StockAdjustRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    item = cursor.execute("SELECT * FROM inventory_items WHERE id = ?;", (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
        
    new_stock = max(0.0, round(item["current_stock"] + payload.delta, 2))
    if new_stock == 0:
        new_status = "CRITICAL"
    elif new_stock <= item["reorder_threshold"]:
        new_status = "LOW_STOCK"
    else:
        new_status = "OK"
        
    cursor.execute("""
        UPDATE inventory_items 
        SET current_stock = ?, status = ?
        WHERE id = ?;
    """, (new_stock, new_status, item_id))
    
    conn.commit()
    updated = cursor.execute("SELECT * FROM inventory_items WHERE id = ?;", (item_id,)).fetchone()
    conn.close()
    
    await notifier.broadcast("INVENTORY_UPDATED", {
        "item_id": item_id,
        "name": updated["name"],
        "new_stock": new_stock,
        "status": new_status
    })
    
    return InventoryItemOut(
        id=updated["id"],
        name=updated["name"],
        category=updated["category"],
        current_stock=updated["current_stock"],
        unit=updated["unit"],
        reorder_threshold=updated["reorder_threshold"],
        cost_per_unit=updated["cost_per_unit"],
        status=updated["status"]
    )

@router.post("/{item_id}/restock", response_model=InventoryItemOut)
async def restock_item(item_id: str, payload: RestockRequest):
    conn = get_connection()
    cursor = conn.cursor()
    
    item = cursor.execute("SELECT * FROM inventory_items WHERE id = ?;", (item_id,)).fetchone()
    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")
        
    new_stock = round(item["current_stock"] + payload.quantity_added, 2)
    new_status = "OK" if new_stock > item["reorder_threshold"] else "LOW_STOCK"
    
    cursor.execute("""
        UPDATE inventory_items 
        SET current_stock = ?, status = ?
        WHERE id = ?;
    """, (new_stock, new_status, item_id))
    
    conn.commit()
    updated = cursor.execute("SELECT * FROM inventory_items WHERE id = ?;", (item_id,)).fetchone()
    conn.close()

    await notifier.broadcast("INVENTORY_UPDATED", {
        "item_id": item_id,
        "name": updated["name"],
        "new_stock": new_stock,
        "status": new_status
    })
    
    return InventoryItemOut(
        id=updated["id"],
        name=updated["name"],
        category=updated["category"],
        current_stock=updated["current_stock"],
        unit=updated["unit"],
        reorder_threshold=updated["reorder_threshold"],
        cost_per_unit=updated["cost_per_unit"],
        status=updated["status"]
    )
