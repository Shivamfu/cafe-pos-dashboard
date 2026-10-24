"""
Automated Integration Tests for Velvet Roast Cafe POS Backend.
"""
import pytest
from fastapi.testclient import TestClient
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
# Use a fresh test database for test runs
settings.DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cafe_pos.db")

from app.database import get_connection, seed_data, init_db
from app.main import app

client = TestClient(app)

def setup_module():
    if os.path.exists(settings.DATABASE_PATH):
        try:
            os.remove(settings.DATABASE_PATH)
        except Exception:
            pass
    init_db()

def teardown_module():
    if os.path.exists(settings.DATABASE_PATH):
        try:
            os.remove(settings.DATABASE_PATH)
        except Exception:
            pass

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["cafe_name"] == "Velvet Roast Cafe"

def test_list_tables():
    res = client.get("/api/tables")
    assert res.status_code == 200
    tables = res.json()
    assert len(tables) >= 12
    t1 = next(t for t in tables if t["table_number"] == "Table 01")
    assert t1["capacity"] == 2
    assert t1["status"] in ["Occupied", "Available", "Bill Pending"]

def test_list_sections():
    res = client.get("/api/sections")
    assert res.status_code == 200
    sections = res.json()
    assert len(sections) == 4
    names = [s["name"] for s in sections]
    assert "Main Floor" in names
    assert "Patio Garden" in names

def test_get_menu():
    res = client.get("/api/menu/categories")
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) >= 3
    coffee_cat = next(c for c in cats if "Coffee" in c["name"])
    item_names = [i["name"] for i in coffee_cat["items"]]
    assert "Caramel Macchiato" in item_names
    assert "Iced Spanish Latte" in item_names

def test_create_order_and_recalculate():
    menu_res = client.get("/api/menu/items")
    items = menu_res.json()
    croissant = next(i for i in items if "Croissant" in i["name"])
    
    payload = {
        "table_id": "tbl-02",
        "order_type": "DINE_IN",
        "guest_count": 2,
        "server_name": "Sarah Jenkins",
        "special_instructions": "Peanut allergy alert - clean board",
        "items": [
            {
                "item_id": croissant["id"],
                "quantity": 2,
                "notes": "Extra warm please",
                "seat_number": 1,
                "modifiers": []
            }
        ]
    }
    res = client.post("/api/orders", json=payload)
    assert res.status_code == 200
    order = res.json()
    assert order["guest_count"] == 2
    assert order["special_instructions"] == "Peanut allergy alert - clean board"
    assert order["items"][0]["notes"] == "Extra warm please"
    assert order["subtotal"] == round(croissant["price"] * 2, 2)
    assert order["total"] > order["subtotal"]
    
    tbl_res = client.get("/api/tables/tbl-02")
    assert tbl_res.status_code == 200
    assert tbl_res.json()["table"]["status"] == "Occupied"

def test_checkout_preview_and_split():
    res = client.get("/api/checkout/preview/ord-04")
    assert res.status_code == 200
    preview = res.json()
    assert preview["table_number"] == "Table 04"
    assert preview["balance_due"] > 0
    assert len(preview["items"]) >= 3

    split_res = client.post("/api/checkout/split-equal", json={"order_id": "ord-04", "split_count": 2})
    assert split_res.status_code == 200
    split_data = split_res.json()
    assert split_data["split_count"] == 2
    assert len(split_data["shares"]) == 2
    assert round(split_data["per_person_amount"] * 2, 1) == round(preview["total"], 1)

def test_payment_and_table_release():
    preview = client.get("/api/checkout/preview/ord-04").json()
    due = preview["balance_due"]
    
    pay_res = client.post("/api/checkout/pay", json={
        "order_id": "ord-04",
        "payment_method": "CREDIT_CARD",
        "amount": due,
        "tip": 5.00,
        "card_brand": "Visa",
        "card_last4": "1234"
    })
    assert pay_res.status_code == 200
    payment = pay_res.json()
    assert payment["amount"] == due
    assert payment["tip"] == 5.00
    assert payment["total_paid"] == round(due + 5.00, 2)
    
    tbl_res = client.get("/api/tables/tbl-04")
    assert tbl_res.json()["table"]["status"] == "Available"
    assert tbl_res.json()["table"]["current_order_id"] is None

def test_kds_tickets():
    res = client.get("/api/kds/tickets")
    assert res.status_code == 200
    tickets = res.json()
    assert len(tickets) >= 1
    t = tickets[0]
    assert t["status"] in ["PREPARING", "READY"]
    
    bump_res = client.patch(f"/api/kds/tickets/{t['id']}", json={"status": "BUMPED"})
    assert bump_res.status_code == 200
    assert bump_res.json()["status"] == "BUMPED"

def test_inventory_and_drawer():
    inv_res = client.get("/api/inventory")
    assert inv_res.status_code == 200
    items = inv_res.json()
    assert len(items) >= 10
    first_item = items[0]
    initial_stock = first_item["current_stock"]

    # Test decrease stock by 1 (-)
    dec_res = client.post(f"/api/inventory/{first_item['id']}/adjust", json={"delta": -1.0})
    assert dec_res.status_code == 200
    assert dec_res.json()["current_stock"] == round(initial_stock - 1.0, 2)

    # Test increase stock by 2 (+)
    inc_res = client.post(f"/api/inventory/{first_item['id']}/adjust", json={"delta": 2.0})
    assert inc_res.status_code == 200
    assert inc_res.json()["current_stock"] == round(initial_stock + 1.0, 2)
    
    drawer_res = client.get("/api/shift/drawer")
    assert drawer_res.status_code == 200
    drawer = drawer_res.json()
    assert drawer["terminal_id"] == "TERM-01"
    assert drawer["starting_cash"] == 15000.00

def test_analytics_summary():
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "gross_revenue" in data
    assert "total_orders" in data
    assert "tables" in data
    assert "top_items" in data
