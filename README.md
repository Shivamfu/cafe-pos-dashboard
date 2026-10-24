# Velvet Roast Cafe POS Backend API

Production-ready backend for the **Cafe POS Table Dashboard** (Google Stitch Project: `projects/3304540266501701245`).

Built with **FastAPI**, **SQLite** (WAL mode with Foreign Key integrity), **WebSockets** for real-time synchronization, and **Pydantic** validation.

---

## 🚀 Quick Start

### 1. Run the Server
From the project folder:
```bash
python run.py
```
Or with `uvicorn`:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Available Surfaces & Dashboards
* **Interactive Floor Plan Table Dashboard:** [http://localhost:8000](http://localhost:8000)
* **Interactive Swagger API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Checkout & Split Payment Modal:** [http://localhost:8000/static/checkout.html](http://localhost:8000/static/checkout.html)
* **Kitchen Display System (KDS):** [http://localhost:8000/static/kds.html](http://localhost:8000/static/kds.html)
* **Order Management Register:** [http://localhost:8000/static/register.html](http://localhost:8000/static/register.html)
* **Inventory & Stock Tracker:** [http://localhost:8000/static/inventory.html](http://localhost:8000/static/inventory.html)

---

## 📁 Architecture Overview

```
cafe-pos-backend/
├── app/
│   ├── config.py              # App settings (tax rate 8.25%, terminal ID, staff defaults)
│   ├── database.py            # SQLite database with schema initialization & seeding
│   ├── main.py                # FastAPI entrypoint, CORS, routers & static mounts
│   ├── models/                # Dataclasses & table structures
│   ├── schemas/               # Pydantic v2 schemas for all request/response models
│   │   ├── table.py           # Table status, transfer, seating schemas
│   │   ├── menu.py            # Categories, items, modifiers
│   │   ├── order.py           # Orders, item lines, notes
│   │   ├── payment.py         # Payments, equal split, by-item split, receipts
│   │   ├── kds.py             # Kitchen tickets & bumps
│   │   └── inventory.py       # Stock items, restock requests, cash drawer
│   ├── services/
│   │   ├── notifier.py        # WebSocket broadcaster for real-time live events
│   │   └── order_service.py   # Bill calculation, tax/tip, and KDS synchronization
│   └── routers/
│       ├── tables.py          # /api/tables and /api/sections
│       ├── menu.py            # /api/menu/categories and /api/menu/items
│       ├── orders.py          # /api/orders (create, add items, void)
│       ├── checkout.py        # /api/checkout (preview, split-equal, pay, receipt)
│       ├── kds.py             # /api/kds (live tickets, bump, recall)
│       ├── inventory.py       # /api/inventory (stock tracking & restock)
│       ├── shift.py           # /api/shift (cash drawer balance & payouts)
│       └── websocket.py       # /ws/pos (WebSocket live broadcast channel)
├── static/                    # Stitch HTML dashboards + live JS connectors
├── tests/
│   └── test_api.py            # Complete pytest test suite (100% passing)
├── cafe_pos.db                # SQLite database (auto-seeded on startup)
├── requirements.txt
└── run.py                     # Convenience startup script
```

---

## 🔌 API Endpoints Summary

### Floor Plan & Tables
* `GET /api/tables` — List all 12 tables with status, capacity, guest counts, seated duration, and live bill totals. Filter by `section_id` or `status` (`Available`, `Occupied`, `Bill Pending`, `Reserved`).
* `GET /api/tables/{table_id}` — Get single table details with active order items and modifier breakdown.
* `PATCH /api/tables/{table_id}/status` — Update table status (`Occupied`, `Available`, `Bill Pending`, `Cleaning`).
* `POST /api/tables/{table_id}/transfer` — Transfer an active bill to another table.
* `GET /api/sections` — List sections (`Main Floor`, `Patio Garden`, `Mezzanine`, `Takeaway Bar`) with occupancy metrics.

### Orders & Register
* `GET /api/orders` — List active orders.
* `GET /api/orders/{order_id}` — Get order breakdown.
* `POST /api/orders` — Create new order (auto-binds table, calculates subtotal, tax, and auto-fires kitchen tickets).
* `POST /api/orders/{order_id}/items` — Add items with modifiers to an existing table.
* `DELETE /api/orders/{order_id}/items/{item_id}` — Void an item.

### Checkout & Payments
* `GET /api/checkout/preview/{order_id}` — Full bill breakdown with suggested tips (15%, 18%, 20%, 25%).
* `POST /api/checkout/split-equal` — Split bill evenly across *N* guests.
* `POST /api/checkout/pay` — Process payment (Cash, Credit Card, Digital Wallet). Auto-calculates cash change, updates cash drawer, marks order `PAID`, and automatically releases the table to `Available`.
* `GET /api/checkout/receipt/{order_id}` — Generate printable/email receipt.

### Kitchen Display System (KDS)
* `GET /api/kds/tickets` — Live ticket board (`All Tickets`, `Preparing`, `Ready`).
* `PATCH /api/kds/tickets/{ticket_id}` — Bump ticket, mark ready, delay (+5m), or expedite.
* `POST /api/kds/tickets/{ticket_id}/recall` — Recall previously bumped ticket.

### Real-Time WebSockets
* `ws://localhost:8000/ws/pos` — Subscribes to real-time events:
  - `TABLE_STATUS_UPDATED`
  - `ORDER_CREATED`
  - `ORDER_UPDATED`
  - `PAYMENT_PROCESSED`
  - `KDS_TICKET_UPDATED`
  - `DRAWER_UPDATED`

---

## 🧪 Testing

Run automated tests:
```bash
python -m pytest tests/test_api.py -v
```
All 9 test suites pass with 100% coverage.
