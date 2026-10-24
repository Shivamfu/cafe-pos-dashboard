"""
Daily Analytics & Sales Performance Endpoints.
"""
from fastapi import APIRouter
from app.database import get_connection

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reports"])

@router.get("/summary")
async def get_analytics_summary():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Overall stats
    orders_stats = cursor.execute("""
        SELECT 
            COUNT(*) as total_orders,
            COALESCE(SUM(total), 0.0) as gross_revenue,
            COALESCE(AVG(total), 0.0) as avg_check,
            COALESCE(SUM(tip), 0.0) as total_tips
        FROM orders
        WHERE status = 'PAID';
    """).fetchone()
    
    # 2. Table occupancy
    table_stats = cursor.execute("""
        SELECT 
            COUNT(*) as total_tables,
            SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied_count,
            SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available_count,
            SUM(CASE WHEN status = 'Bill Pending' THEN 1 ELSE 0 END) as bill_pending_count
        FROM dining_tables;
    """).fetchone()
    
    # 3. Top selling items
    top_items = cursor.execute("""
        SELECT item_name, SUM(quantity) as units_sold, SUM(item_total) as total_sales
        FROM order_items
        WHERE status != 'CANCELLED'
        GROUP BY item_name
        ORDER BY units_sold DESC
        LIMIT 5;
    """).fetchall()
    
    # 4. Payment breakdown
    payments_breakdown = cursor.execute("""
        SELECT payment_method, COUNT(*) as tx_count, COALESCE(SUM(amount), 0.0) as total_amount
        FROM payments
        GROUP BY payment_method;
    """).fetchall()
    
    # 5. Recent paid transactions
    recent_transactions = cursor.execute("""
        SELECT o.id, o.order_number, dt.table_number, o.server_name, o.total, o.closed_at,
               (SELECT payment_method FROM payments p WHERE p.order_id = o.id LIMIT 1) as payment_method
        FROM orders o
        LEFT JOIN dining_tables dt ON o.table_id = dt.id
        WHERE o.status = 'PAID'
        ORDER BY o.closed_at DESC
        LIMIT 10;
    """).fetchall()
    
    # 6. Low stock alert count
    low_stock = cursor.execute("""
        SELECT COUNT(*) as low_count FROM inventory_items WHERE status IN ('LOW_STOCK', 'CRITICAL');
    """).fetchone()

    conn.close()
    
    return {
        "gross_revenue": round(orders_stats["gross_revenue"], 2),
        "total_orders": orders_stats["total_orders"],
        "avg_check": round(orders_stats["avg_check"], 2),
        "total_tips": round(orders_stats["total_tips"], 2),
        "tables": {
            "total": table_stats["total_tables"],
            "occupied": table_stats["occupied_count"] or 0,
            "available": table_stats["available_count"] or 0,
            "bill_pending": table_stats["bill_pending_count"] or 0,
        },
        "low_stock_count": low_stock["low_count"] or 0,
        "top_items": [dict(r) for r in top_items],
        "payment_breakdown": [dict(r) for r in payments_breakdown],
        "recent_transactions": [dict(r) for r in recent_transactions]
    }
