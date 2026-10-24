"""
Database layer using SQLite with WAL mode, foreign keys, and automatic seeding.
All monetary amounts in Indian Rupees (₹).
"""
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from app.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    -- Sections
    CREATE TABLE IF NOT EXISTS sections (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        display_order INTEGER NOT NULL DEFAULT 0
    );

    -- Dining Tables
    CREATE TABLE IF NOT EXISTS dining_tables (
        id TEXT PRIMARY KEY,
        table_number TEXT NOT NULL UNIQUE,
        section_id TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Available', 'Occupied', 'Bill Pending', 'Reserved', 'Cleaning')),
        guest_count INTEGER NOT NULL DEFAULT 0,
        seated_at TEXT,
        current_order_id TEXT,
        x_pos INTEGER DEFAULT 0,
        y_pos INTEGER DEFAULT 0,
        reservation_note TEXT,
        FOREIGN KEY (section_id) REFERENCES sections(id)
    );

    -- Menu Categories
    CREATE TABLE IF NOT EXISTS menu_categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        icon TEXT,
        display_order INTEGER NOT NULL DEFAULT 0
    );

    -- Menu Items
    CREATE TABLE IF NOT EXISTS menu_items (
        id TEXT PRIMARY KEY,
        category_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        is_available INTEGER NOT NULL DEFAULT 1,
        is_kitchen_item INTEGER NOT NULL DEFAULT 0,
        allergen_tags TEXT,
        prep_time_mins INTEGER NOT NULL DEFAULT 5,
        FOREIGN KEY (category_id) REFERENCES menu_categories(id)
    );

    -- Modifier Groups
    CREATE TABLE IF NOT EXISTS modifier_groups (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        min_select INTEGER DEFAULT 0,
        max_select INTEGER DEFAULT 1,
        is_required INTEGER DEFAULT 0
    );

    -- Modifiers
    CREATE TABLE IF NOT EXISTS modifiers (
        id TEXT PRIMARY KEY,
        group_id TEXT NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (group_id) REFERENCES modifier_groups(id)
    );

    -- Item to Modifier Group Mapping
    CREATE TABLE IF NOT EXISTS item_modifier_groups (
        item_id TEXT NOT NULL,
        group_id TEXT NOT NULL,
        PRIMARY KEY (item_id, group_id),
        FOREIGN KEY (item_id) REFERENCES menu_items(id),
        FOREIGN KEY (group_id) REFERENCES modifier_groups(id)
    );

    -- Orders
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        order_number INTEGER NOT NULL,
        table_id TEXT,
        order_type TEXT NOT NULL CHECK(order_type IN ('DINE_IN', 'TAKEAWAY')),
        status TEXT NOT NULL CHECK(status IN ('OPEN', 'SENT_TO_KITCHEN', 'READY', 'BILL_PRINTED', 'PAID', 'CANCELLED')),
        guest_count INTEGER NOT NULL DEFAULT 1,
        server_name TEXT NOT NULL,
        subtotal REAL NOT NULL DEFAULT 0.0,
        tax REAL NOT NULL DEFAULT 0.0,
        discount REAL NOT NULL DEFAULT 0.0,
        tip REAL NOT NULL DEFAULT 0.0,
        total REAL NOT NULL DEFAULT 0.0,
        special_instructions TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        closed_at TEXT,
        FOREIGN KEY (table_id) REFERENCES dining_tables(id)
    );

    -- Order Items
    CREATE TABLE IF NOT EXISTS order_items (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        item_name TEXT NOT NULL,
        unit_price REAL NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        item_total REAL NOT NULL,
        notes TEXT,
        seat_number INTEGER DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'COOKING', 'READY', 'SERVED', 'CANCELLED')),
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES menu_items(id)
    );

    -- Order Item Modifiers
    CREATE TABLE IF NOT EXISTS order_item_modifiers (
        id TEXT PRIMARY KEY,
        order_item_id TEXT NOT NULL,
        modifier_name TEXT NOT NULL,
        price REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
    );

    -- Payments & Transactions
    CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        payment_method TEXT NOT NULL CHECK(payment_method IN ('CASH', 'CREDIT_CARD', 'DIGITAL_WALLET', 'GIFT_CARD')),
        amount REAL NOT NULL,
        tip REAL NOT NULL DEFAULT 0.0,
        total_paid REAL NOT NULL,
        tendered_amount REAL,
        change_amount REAL,
        card_brand TEXT,
        card_last4 TEXT,
        split_type TEXT DEFAULT 'FULL' CHECK(split_type IN ('FULL', 'EQUAL', 'BY_ITEM')),
        seat_number INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    );

    -- Kitchen Display System Tickets
    CREATE TABLE IF NOT EXISTS kitchen_tickets (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        table_number TEXT NOT NULL,
        order_number INTEGER NOT NULL,
        server_name TEXT NOT NULL,
        special_instructions TEXT,
        status TEXT NOT NULL DEFAULT 'PREPARING' CHECK(status IN ('PREPARING', 'READY', 'BUMPED', 'RECALLED')),
        is_expedited INTEGER NOT NULL DEFAULT 0,
        delay_minutes INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        bumped_at TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    );

    -- Kitchen Ticket Items
    CREATE TABLE IF NOT EXISTS kitchen_ticket_items (
        id TEXT PRIMARY KEY,
        ticket_id TEXT NOT NULL,
        order_item_id TEXT NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        modifiers_text TEXT,
        notes TEXT,
        is_completed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (ticket_id) REFERENCES kitchen_tickets(id) ON DELETE CASCADE
    );

    -- Inventory Items
    CREATE TABLE IF NOT EXISTS inventory_items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL,
        current_stock REAL NOT NULL,
        unit TEXT NOT NULL,
        reorder_threshold REAL NOT NULL,
        cost_per_unit REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'OK' CHECK(status IN ('OK', 'LOW_STOCK', 'CRITICAL', 'OUT_OF_STOCK'))
    );

    -- Cash Drawer Balance & Shifts
    CREATE TABLE IF NOT EXISTS cash_drawer (
        id TEXT PRIMARY KEY,
        terminal_id TEXT NOT NULL,
        staff_name TEXT NOT NULL,
        starting_cash REAL NOT NULL,
        current_cash REAL NOT NULL,
        cash_sales REAL NOT NULL DEFAULT 0.0,
        cash_in REAL NOT NULL DEFAULT 0.0,
        cash_out REAL NOT NULL DEFAULT 0.0,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN', 'CLOSED'))
    );
    """)
    conn.commit()

    # Ensure schema migrations for existing DB
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN special_instructions TEXT;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE kitchen_tickets ADD COLUMN special_instructions TEXT;")
    except Exception:
        pass
    conn.commit()

    check = cursor.execute("SELECT COUNT(*) as count FROM sections;").fetchone()
    if check["count"] == 0:
        seed_data(conn)

    conn.close()

def seed_data(conn: sqlite3.Connection):
    cursor = conn.cursor()
    now_utc = datetime.now(timezone.utc)

    # 1. Sections
    sections = [
        ("sec-main", "Main Floor", 1),
        ("sec-patio", "Patio Garden", 2),
        ("sec-mezz", "Mezzanine", 3),
        ("sec-bar", "Takeaway Bar", 4),
    ]
    cursor.executemany("INSERT INTO sections (id, name, display_order) VALUES (?, ?, ?);", sections)

    # 2. Dining Tables
    tables = [
        ("tbl-01", "Table 01", "sec-main", 2, "Occupied", 2, (now_utc - timedelta(minutes=14)).isoformat(), "ord-01", 100, 100, None),
        ("tbl-02", "Table 02", "sec-main", 2, "Available", 0, None, None, 250, 100, None),
        ("tbl-03", "Table 03", "sec-main", 4, "Occupied", 4, (now_utc - timedelta(minutes=28)).isoformat(), "ord-03", 400, 100, None),
        ("tbl-04", "Table 04", "sec-main", 4, "Bill Pending", 4, (now_utc - timedelta(minutes=45)).isoformat(), "ord-04", 100, 250, None),
        ("tbl-05", "Table 05", "sec-main", 6, "Occupied", 5, (now_utc - timedelta(minutes=19)).isoformat(), "ord-05", 250, 250, None),
        ("tbl-06", "Table 06", "sec-main", 2, "Available", 0, None, None, 400, 250, None),
        ("tbl-07", "Table 07", "sec-patio", 4, "Available", 0, None, None, 100, 400, None),
        ("tbl-08", "Table 08", "sec-patio", 4, "Occupied", 3, (now_utc - timedelta(minutes=22)).isoformat(), "ord-08", 250, 400, None),
        ("tbl-09", "Table 09", "sec-patio", 2, "Available", 0, None, None, 400, 400, None),
        ("tbl-10", "Table 10", "sec-mezz", 4, "Bill Pending", 4, (now_utc - timedelta(minutes=39)).isoformat(), "ord-10", 100, 550, None),
        ("tbl-11", "Table 11", "sec-mezz", 6, "Reserved", 0, None, None, 250, 550, "Party of 6 - Reservation at 1:30 PM"),
        ("tbl-12", "Table 12", "sec-bar", 2, "Available", 0, None, None, 400, 550, None),
    ]
    cursor.executemany("""
        INSERT INTO dining_tables 
        (id, table_number, section_id, capacity, status, guest_count, seated_at, current_order_id, x_pos, y_pos, reservation_note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, tables)

    # 3. Menu Categories
    categories = [
        ("cat-coffee", "Coffee & Espresso", "local_cafe", 1),
        ("cat-bakery", "Bakery & Pastries", "bakery_dining", 2),
        ("cat-brunch", "Brunch & Kitchen", "brunch_dining", 3),
        ("cat-specials", "Seasonal Specials", "award_star", 4),
    ]
    cursor.executemany("INSERT INTO menu_categories (id, name, icon, display_order) VALUES (?, ?, ?, ?);", categories)

    # 4. Menu Items (Realistic Indian Rupee Pricing)
    items = [
        ("itm-01", "cat-coffee", "Caramel Macchiato", "Rich espresso layered with creamy vanilla steamed milk and artisan caramel drizzle", 280.00, 1, 0, "Dairy", 4),
        ("itm-02", "cat-coffee", "Iced Spanish Latte", "Double shot house espresso with sweet condensed milk over crystal ice", 310.00, 1, 0, "Dairy", 3),
        ("itm-03", "cat-coffee", "Cold Brew Reserve", "18-hour single origin Ethiopian slow brew served black over slow-melting clear ice", 260.00, 1, 0, "None", 2),
        ("itm-04", "cat-coffee", "Velvet Flat White", "Double ristretto poured with velvety micro-foam texture", 240.00, 1, 0, "Dairy", 3),
        ("itm-05", "cat-coffee", "Matcha Ceremonial Latte", "Pure organic Uji matcha hand-whisked with creamy oat milk", 340.00, 1, 0, "None", 4),
        ("itm-06", "cat-bakery", "Artisan Croissant", "Triple-laminated French butter pastry, baked golden and crisp", 210.00, 1, 0, "Gluten, Dairy", 1),
        ("itm-07", "cat-bakery", "Almond Pain au Chocolat", "Double-baked chocolate croissant filled with rich almond frangipane", 260.00, 1, 0, "Nuts, Gluten, Dairy", 2),
        ("itm-08", "cat-brunch", "Avocado Sourdough", "Smashed Hass avocado, soft poached pasture egg, feta & chili crunch on sourdough", 420.00, 1, 1, "Gluten, Eggs, Dairy", 10),
        ("itm-09", "cat-brunch", "Truffle Benedict", "Poached farm eggs, prosciutto di Parma, black truffle hollandaise on brioche", 540.00, 1, 1, "Gluten, Eggs, Dairy", 12),
        ("itm-10", "cat-brunch", "Brioche French Toast", "Caramelized banana, whipped mascarpone, candied pecans and pure maple syrup", 390.00, 1, 1, "Gluten, Eggs, Dairy, Nuts", 11),
    ]
    cursor.executemany("""
        INSERT INTO menu_items 
        (id, category_id, name, description, price, is_available, is_kitchen_item, allergen_tags, prep_time_mins)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, items)

    # 5. Modifiers
    mod_groups = [
        ("grp-milk", "Milk Alternative", 0, 1, 0),
        ("grp-shot", "Espresso Shot", 0, 2, 0),
        ("grp-syrup", "Flavored Syrup", 0, 3, 0),
    ]
    cursor.executemany("INSERT INTO modifier_groups (id, name, min_select, max_select, is_required) VALUES (?, ?, ?, ?, ?);", mod_groups)

    modifiers = [
        ("mod-oat", "grp-milk", "Oat Milk", 50.00),
        ("mod-almond", "grp-milk", "Almond Milk", 50.00),
        ("mod-soy", "grp-milk", "Soy Milk", 40.00),
        ("mod-shot-extra", "grp-shot", "Extra Shot", 60.00),
        ("mod-decaf", "grp-shot", "Decaf Blend", 40.00),
        ("mod-vanilla", "grp-syrup", "Vanilla Syrup", 40.00),
        ("mod-caramel", "grp-syrup", "Caramel Drizzle", 40.00),
        ("mod-lavender", "grp-syrup", "Lavender Blossom", 50.00),
    ]
    cursor.executemany("INSERT INTO modifiers (id, group_id, name, price) VALUES (?, ?, ?, ?);", modifiers)

    for itm_id in ["itm-01", "itm-02", "itm-03", "itm-04", "itm-05"]:
        for grp_id in ["grp-milk", "grp-shot", "grp-syrup"]:
            cursor.execute("INSERT OR IGNORE INTO item_modifier_groups (item_id, group_id) VALUES (?, ?);", (itm_id, grp_id))

    # ================= 6. PRE-SEEDED PAID ORDERS (FOR REALISTIC DAILY ANALYTICS) =================
    # Order #95 - Table 02 (Paid via Credit Card)
    p1_time = (now_utc - timedelta(hours=3, minutes=45)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at, closed_at)
        VALUES ('ord-p1', 95, 'tbl-02', 'DINE_IN', 'PAID', 2, 'Sarah Jenkins', 960.00, 48.00, 0.0, 50.00, 1058.00, ?, ?, ?);
    """, (p1_time, p1_time, p1_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oip-11', 'ord-p1', 'itm-08', 'Avocado Sourdough', 420.00, 1, 420.00, '', 1, 'SERVED'),
        ('oip-12', 'ord-p1', 'itm-09', 'Truffle Benedict', 540.00, 1, 540.00, '', 2, 'SERVED');
    """)
    cursor.execute("""
        INSERT INTO payments (id, order_id, payment_method, amount, tip, total_paid, card_brand, card_last4, split_type, created_at)
        VALUES ('pay-p1', 'ord-p1', 'CREDIT_CARD', 1008.00, 50.00, 1058.00, 'Visa', '4242', 'FULL', ?);
    """, (p1_time,))

    # Order #96 - Takeaway (Paid via UPI / Digital Wallet)
    p2_time = (now_utc - timedelta(hours=3, minutes=10)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at, closed_at)
        VALUES ('ord-p2', 96, NULL, 'TAKEAWAY', 'PAID', 1, 'Sarah Jenkins', 590.00, 29.50, 0.0, 30.00, 649.50, ?, ?, ?);
    """, (p2_time, p2_time, p2_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oip-21', 'ord-p2', 'itm-01', 'Caramel Macchiato', 280.00, 1, 280.00, 'Extra caramel', 1, 'SERVED'),
        ('oip-22', 'ord-p2', 'itm-02', 'Iced Spanish Latte', 310.00, 1, 310.00, 'Less sweet', 1, 'SERVED');
    """)
    cursor.execute("""
        INSERT INTO payments (id, order_id, payment_method, amount, tip, total_paid, card_brand, card_last4, split_type, created_at)
        VALUES ('pay-p2', 'ord-p2', 'DIGITAL_WALLET', 619.50, 30.00, 649.50, 'UPI / GPay', '9841', 'FULL', ?);
    """, (p2_time,))

    # Order #97 - Table 06 (Paid via Cash)
    p3_time = (now_utc - timedelta(hours=2, minutes=30)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at, closed_at)
        VALUES ('ord-p3', 97, 'tbl-06', 'DINE_IN', 'PAID', 3, 'Sarah Jenkins', 1780.00, 89.00, 0.0, 100.00, 1969.00, ?, ?, ?);
    """, (p3_time, p3_time, p3_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oip-31', 'ord-p3', 'itm-09', 'Truffle Benedict', 540.00, 2, 1080.00, 'Prosciutto crisp', 1, 'SERVED'),
        ('oip-32', 'ord-p3', 'itm-10', 'Brioche French Toast', 390.00, 1, 390.00, '', 2, 'SERVED'),
        ('oip-33', 'ord-p3', 'itm-02', 'Iced Spanish Latte', 310.00, 1, 310.00, '', 3, 'SERVED');
    """)
    cursor.execute("""
        INSERT INTO payments (id, order_id, payment_method, amount, tip, total_paid, tendered_amount, change_amount, split_type, created_at)
        VALUES ('pay-p3', 'ord-p3', 'CASH', 1869.00, 100.00, 1969.00, 2000.00, 31.00, 'FULL', ?);
    """, (p3_time,))

    # Order #98 - Table 09 (Paid via UPI)
    p4_time = (now_utc - timedelta(hours=1, minutes=50)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at, closed_at)
        VALUES ('ord-p4', 98, 'tbl-09', 'DINE_IN', 'PAID', 2, 'Sarah Jenkins', 1280.00, 64.00, 0.0, 60.00, 1404.00, ?, ?, ?);
    """, (p4_time, p4_time, p4_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oip-41', 'ord-p4', 'itm-08', 'Avocado Sourdough', 420.00, 2, 840.00, '', 1, 'SERVED'),
        ('oip-42', 'ord-p4', 'itm-04', 'Velvet Flat White', 240.00, 1, 240.00, '', 2, 'SERVED'),
        ('oip-43', 'ord-p4', 'itm-01', 'Caramel Macchiato', 280.00, 1, 280.00, '', 2, 'SERVED');
    """)
    cursor.execute("""
        INSERT INTO payments (id, order_id, payment_method, amount, tip, total_paid, card_brand, card_last4, split_type, created_at)
        VALUES ('pay-p4', 'ord-p4', 'DIGITAL_WALLET', 1344.00, 60.00, 1404.00, 'PhonePe UPI', '7732', 'FULL', ?);
    """, (p4_time,))

    # Order #99 - Table 07 (Paid via Card)
    p5_time = (now_utc - timedelta(hours=1, minutes=15)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at, closed_at)
        VALUES ('ord-p5', 99, 'tbl-07', 'DINE_IN', 'PAID', 4, 'Sarah Jenkins', 2140.00, 107.00, 0.0, 120.00, 2367.00, ?, ?, ?);
    """, (p5_time, p5_time, p5_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oip-51', 'ord-p5', 'itm-09', 'Truffle Benedict', 540.00, 2, 1080.00, '', 1, 'SERVED'),
        ('oip-52', 'ord-p5', 'itm-10', 'Brioche French Toast', 390.00, 1, 390.00, '', 2, 'SERVED'),
        ('oip-53', 'ord-p5', 'itm-06', 'Artisan Croissant', 210.00, 2, 420.00, '', 3, 'SERVED'),
        ('oip-54', 'ord-p5', 'itm-03', 'Cold Brew Reserve', 260.00, 1, 260.00, '', 4, 'SERVED');
    """)
    cursor.execute("""
        INSERT INTO payments (id, order_id, payment_method, amount, tip, total_paid, card_brand, card_last4, split_type, created_at)
        VALUES ('pay-p5', 'ord-p5', 'CREDIT_CARD', 2247.00, 120.00, 2367.00, 'Mastercard', '9912', 'FULL', ?);
    """, (p5_time,))

    # Order #100 - Table 12 (Paid via UPI)
    p6_time = (now_utc - timedelta(minutes=40)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at, closed_at)
        VALUES ('ord-p6', 100, 'tbl-12', 'DINE_IN', 'PAID', 2, 'Sarah Jenkins', 920.00, 46.00, 0.0, 50.00, 1016.00, ?, ?, ?);
    """, (p6_time, p6_time, p6_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oip-61', 'ord-p6', 'itm-01', 'Caramel Macchiato', 280.00, 2, 560.00, '', 1, 'SERVED'),
        ('oip-62', 'ord-p6', 'itm-07', 'Almond Pain au Chocolat', 260.00, 1, 260.00, '', 2, 'SERVED'),
        ('oip-63', 'ord-p6', 'itm-04', 'Velvet Flat White', 240.00, 1, 240.00, '', 2, 'SERVED');
    """)
    cursor.execute("""
        INSERT INTO payments (id, order_id, payment_method, amount, tip, total_paid, card_brand, card_last4, split_type, created_at)
        VALUES ('pay-p6', 'ord-p6', 'DIGITAL_WALLET', 966.00, 50.00, 1016.00, 'Paytm UPI', '3341', 'FULL', ?);
    """, (p6_time,))

    # ================= 7. ACTIVE ORDERS (FOR FLOOR PLAN & CHECKOUT) =================
    # Table 01 (Occupied: 2 guests, ₹745.50)
    t1_time = (now_utc - timedelta(minutes=14)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at)
        VALUES ('ord-01', 101, 'tbl-01', 'DINE_IN', 'SENT_TO_KITCHEN', 2, 'Sarah Jenkins', 710.00, 35.50, 0.0, 0.0, 745.50, ?, ?);
    """, (t1_time, t1_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oi-11', 'ord-01', 'itm-08', 'Avocado Sourdough', 420.00, 1, 420.00, 'No chili flakes', 1, 'COOKING'),
        ('oi-12', 'ord-01', 'itm-04', 'Velvet Flat White', 240.00, 1, 290.00, 'Oat Milk', 2, 'COOKING');
    """)
    cursor.execute("INSERT INTO order_item_modifiers (id, order_item_id, modifier_name, price) VALUES ('oim-1', 'oi-12', 'Oat Milk', 50.00);")

    # Table 03 (Occupied: 4 guests, ₹1,438.50)
    t3_time = (now_utc - timedelta(minutes=28)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at)
        VALUES ('ord-03', 103, 'tbl-03', 'DINE_IN', 'SENT_TO_KITCHEN', 4, 'Sarah Jenkins', 1370.00, 68.50, 0.0, 0.0, 1438.50, ?, ?);
    """, (t3_time, t3_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oi-31', 'ord-03', 'itm-07', 'Almond Pain au Chocolat', 260.00, 2, 520.00, 'Warm please', 1, 'COOKING'),
        ('oi-32', 'ord-03', 'itm-01', 'Caramel Macchiato', 280.00, 2, 560.00, 'Extra caramel drizzle', 2, 'COOKING'),
        ('oi-33', 'ord-03', 'itm-02', 'Iced Spanish Latte', 310.00, 1, 290.00, 'Less ice', 3, 'COOKING');
    """)

    # Table 04 (Bill Pending: 4 guests, ₹1,879.50)
    t4_time = (now_utc - timedelta(minutes=45)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at)
        VALUES ('ord-04', 104, 'tbl-04', 'DINE_IN', 'BILL_PRINTED', 4, 'Sarah Jenkins', 1790.00, 89.50, 0.0, 0.0, 1879.50, ?, ?);
    """, (t4_time, t4_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oi-41', 'ord-04', 'itm-09', 'Truffle Benedict', 540.00, 2, 1080.00, 'Extra crispy prosciutto', 1, 'SERVED'),
        ('oi-42', 'ord-04', 'itm-01', 'Caramel Macchiato', 280.00, 1, 280.00, '', 2, 'SERVED'),
        ('oi-43', 'ord-04', 'itm-08', 'Avocado Sourdough', 420.00, 1, 420.00, '', 3, 'SERVED');
    """)

    # Table 05 (Occupied: 5 guests, ₹2,352.00)
    t5_time = (now_utc - timedelta(minutes=19)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at)
        VALUES ('ord-05', 105, 'tbl-05', 'DINE_IN', 'READY', 5, 'Sarah Jenkins', 2240.00, 112.00, 0.0, 0.0, 2352.00, ?, ?);
    """, (t5_time, t5_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oi-51', 'ord-05', 'itm-10', 'Brioche French Toast', 390.00, 2, 780.00, 'Maple on the side', 1, 'READY'),
        ('oi-52', 'ord-05', 'itm-08', 'Avocado Sourdough', 420.00, 2, 840.00, '', 2, 'READY'),
        ('oi-53', 'ord-05', 'itm-05', 'Matcha Ceremonial Latte', 340.00, 2, 680.00, 'Oat Milk', 3, 'READY');
    """)

    # Table 08 (Occupied: 3 guests, ₹1,039.50)
    t8_time = (now_utc - timedelta(minutes=22)).isoformat()
    cursor.execute("""
        INSERT INTO orders (id, order_number, table_id, order_type, status, guest_count, server_name, subtotal, tax, discount, tip, total, created_at, updated_at)
        VALUES ('ord-08', 108, 'tbl-08', 'DINE_IN', 'SENT_TO_KITCHEN', 3, 'Sarah Jenkins', 990.00, 49.50, 0.0, 0.0, 1039.50, ?, ?);
    """, (t8_time, t8_time))
    cursor.execute("""
        INSERT INTO order_items (id, order_id, item_id, item_name, unit_price, quantity, item_total, notes, seat_number, status)
        VALUES 
        ('oi-81', 'ord-08', 'itm-08', 'Avocado Sourdough', 420.00, 1, 420.00, '', 1, 'COOKING'),
        ('oi-82', 'ord-08', 'itm-03', 'Cold Brew Reserve', 260.00, 1, 260.00, '', 2, 'COOKING'),
        ('oi-83', 'ord-08', 'itm-02', 'Iced Spanish Latte', 310.00, 1, 310.00, '', 3, 'COOKING');
    """)

    # ================= 8. PRE-SEEDED KITCHEN DISPLAY SYSTEM TICKETS =================
    # Ticket 1: Table 01 (PREPARING)
    cursor.execute("""
        INSERT INTO kitchen_tickets (id, order_id, table_number, order_number, server_name, status, is_expedited, delay_minutes, created_at)
        VALUES ('kds-01', 'ord-01', 'Table 01', 101, 'Sarah Jenkins', 'PREPARING', 0, 0, ?);
    """, (t1_time,))
    cursor.execute("""
        INSERT INTO kitchen_ticket_items (id, ticket_id, order_item_id, item_name, quantity, modifiers_text, notes, is_completed)
        VALUES 
        ('kti-01', 'kds-01', 'oi-11', 'Avocado Sourdough', 1, '', 'No chili flakes', 0),
        ('kti-02', 'kds-01', 'oi-12', 'Velvet Flat White', 1, 'Oat Milk', '', 0);
    """)

    # Ticket 2: Table 03 (PREPARING - 28m)
    cursor.execute("""
        INSERT INTO kitchen_tickets (id, order_id, table_number, order_number, server_name, status, is_expedited, delay_minutes, created_at)
        VALUES ('kds-02', 'ord-03', 'Table 03', 103, 'Sarah Jenkins', 'PREPARING', 0, 0, ?);
    """, (t3_time,))
    cursor.execute("""
        INSERT INTO kitchen_ticket_items (id, ticket_id, order_item_id, item_name, quantity, modifiers_text, notes, is_completed)
        VALUES 
        ('kti-03', 'kds-02', 'oi-31', 'Almond Pain au Chocolat', 2, '', 'Warm please', 0),
        ('kti-04', 'kds-02', 'oi-32', 'Caramel Macchiato', 2, 'Caramel Drizzle', 'Extra caramel drizzle', 0),
        ('kti-05', 'kds-02', 'oi-33', 'Iced Spanish Latte', 1, '', 'Less ice', 0);
    """)

    # Ticket 3: Table 05 (READY FOR RUNNER)
    cursor.execute("""
        INSERT INTO kitchen_tickets (id, order_id, table_number, order_number, server_name, status, is_expedited, delay_minutes, created_at)
        VALUES ('kds-03', 'ord-05', 'Table 05', 105, 'Sarah Jenkins', 'READY', 0, 0, ?);
    """, (t5_time,))
    cursor.execute("""
        INSERT INTO kitchen_ticket_items (id, ticket_id, order_item_id, item_name, quantity, modifiers_text, notes, is_completed)
        VALUES 
        ('kti-06', 'kds-03', 'oi-51', 'Brioche French Toast', 2, '', 'Maple on the side', 1),
        ('kti-07', 'kds-03', 'oi-52', 'Avocado Sourdough', 2, '', '', 1),
        ('kti-08', 'kds-03', 'oi-53', 'Matcha Ceremonial Latte', 2, 'Oat Milk', '', 1);
    """)

    # Ticket 4: Takeaway (EXPEDITED)
    tk_time = (now_utc - timedelta(minutes=5)).isoformat()
    cursor.execute("""
        INSERT INTO kitchen_tickets (id, order_id, table_number, order_number, server_name, status, is_expedited, delay_minutes, created_at)
        VALUES ('kds-04', 'ord-08', 'Takeaway Bar', 108, 'Sarah Jenkins', 'PREPARING', 1, 0, ?);
    """, (tk_time,))
    cursor.execute("""
        INSERT INTO kitchen_ticket_items (id, ticket_id, order_item_id, item_name, quantity, modifiers_text, notes, is_completed)
        VALUES 
        ('kti-09', 'kds-04', 'oi-82', 'Cold Brew Reserve', 1, '', 'Large clear ice cube', 0),
        ('kti-10', 'kds-04', 'oi-83', 'Iced Spanish Latte', 1, '', '', 0);
    """)

    # 9. Inventory Items (with Indian Rupee Costs)
    inventory = [
        ("inv-01", "Espresso Beans (Single Origin Roast)", "Coffee", 18.5, "kg", 5.0, 1400.00, "OK"),
        ("inv-02", "Whole Milk (Farm Fresh 4.0%)", "Dairy", 32.0, "L", 10.0, 68.00, "OK"),
        ("inv-03", "Oat Milk (Barista Blend)", "Dairy Alt", 24.0, "L", 8.0, 195.00, "OK"),
        ("inv-04", "Almond Milk (Unsweetened)", "Dairy Alt", 5.0, "L", 8.0, 220.00, "LOW_STOCK"),
        ("inv-05", "Fresh Hass Avocados", "Produce", 45.0, "units", 20.0, 95.00, "OK"),
        ("inv-06", "Free-Range Farm Eggs", "Produce", 120.0, "units", 50.0, 12.00, "OK"),
        ("inv-07", "Artisan Sourdough Loaves", "Bakery", 14.0, "loaves", 5.0, 180.00, "OK"),
        ("inv-08", "Pure Butter Croissants", "Bakery", 4.0, "units", 15.0, 90.00, "CRITICAL"),
        ("inv-09", "Madagascar Vanilla Syrup", "Syrups", 5.5, "L", 2.0, 850.00, "OK"),
        ("inv-10", "Artisan Salted Caramel Sauce", "Syrups", 4.0, "L", 2.0, 920.00, "OK"),
    ]
    cursor.executemany("""
        INSERT INTO inventory_items (id, name, category, current_stock, unit, reorder_threshold, cost_per_unit, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, inventory)

    # 10. Cash Drawer Balance (Opening Float: ₹15,000 + Cash Sales: ₹1,869 = ₹16,869)
    cursor.execute("""
        INSERT INTO cash_drawer 
        (id, terminal_id, staff_name, starting_cash, current_cash, cash_sales, cash_in, cash_out, opened_at, status)
        VALUES ('draw-01', 'TERM-01', 'Sarah Jenkins', 15000.00, 16869.00, 1869.00, 0.0, 0.0, ?, 'OPEN');
    """, (now_utc.isoformat(),))

    conn.commit()
