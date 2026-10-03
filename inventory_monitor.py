"""Persistent product-level inventory alerts; no paid model calls."""
from datetime import datetime, timezone
from urllib.parse import urlencode
from database import _connect, store_key
from shopify_service import get_products

THRESHOLD = 50

def stock_state(product):
    quantity = product.get('totalInventory')
    if product.get('status') != 'ACTIVE' or type(quantity) is not int:
        return 'ignored'
    return 'out' if quantity <= 0 else 'low' if quantity <= THRESHOLD else 'ok'

def should_alert(previous, current):
    return current in ('low', 'out') and current != previous

def prepare(conn):
    conn.execute("SELECT pg_advisory_xact_lock(7432103)")
    conn.execute("""CREATE TABLE IF NOT EXISTS inventory_monitor (
        shop TEXT PRIMARY KEY, checked_at TIMESTAMPTZ)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS inventory_snapshots (
        shop TEXT NOT NULL, product_id TEXT NOT NULL, state TEXT NOT NULL,
        PRIMARY KEY(shop,product_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS inventory_alerts (
        id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, product_id TEXT NOT NULL,
        title TEXT NOT NULL, quantity INTEGER NOT NULL, state TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), acknowledged BOOLEAN NOT NULL DEFAULT FALSE)""")
    conn.execute("CREATE INDEX IF NOT EXISTS inventory_alerts_shop_id ON inventory_alerts(shop,id)")

def scan_inventory():
    shop = store_key()
    if not shop:
        raise RuntimeError('SHOPIFY_STORE_DOMAIN is missing')
    with _connect() as conn:
        # Held across the complete read: concurrent workers cannot duplicate transitions.
        prepare(conn)
        conn.execute("INSERT INTO inventory_monitor(shop) VALUES (%s) ON CONFLICT DO NOTHING", (shop,))
        checked = conn.execute("SELECT checked_at FROM inventory_monitor WHERE shop=%s", (shop,)).fetchone()[0]
        if checked and (datetime.now(timezone.utc) - checked).total_seconds() < 900:
            return False
        products = get_products()
        # Validate complete input before writing anything; unknown counts never mean zero.
        ids = [p.get('id') for p in products]
        if any(not i for i in ids) or len(set(ids)) != len(ids):
            raise RuntimeError('Invalid product identifiers')
        previous = dict(conn.execute("SELECT product_id,state FROM inventory_snapshots WHERE shop=%s", (shop,)).fetchall())
        for product in products:
            pid = product['id']
            state = stock_state(product)
            if should_alert(previous.get(pid), state):
                conn.execute("""INSERT INTO inventory_alerts(shop,product_id,title,quantity,state)
                    VALUES (%s,%s,%s,%s,%s)""",
                    (shop,pid,product.get('title') or pid,product['totalInventory'],state))
            conn.execute("""INSERT INTO inventory_snapshots(shop,product_id,state) VALUES (%s,%s,%s)
                ON CONFLICT(shop,product_id) DO UPDATE SET state=EXCLUDED.state""", (shop,pid,state))
        conn.execute("DELETE FROM inventory_snapshots WHERE shop=%s AND NOT (product_id=ANY(%s))", (shop,ids))
        conn.execute("UPDATE inventory_monitor SET checked_at=NOW() WHERE shop=%s", (shop,))
    return True

def read_alerts():
    with _connect() as conn:
        prepare(conn)
        rows = conn.execute("""SELECT id,title,quantity,state,created_at,acknowledged
            FROM inventory_alerts WHERE shop=%s ORDER BY id DESC LIMIT 100""", (store_key(),)).fetchall()
        row = conn.execute("SELECT checked_at FROM inventory_monitor WHERE shop=%s", (store_key(),)).fetchone()
    alerts = []
    for aid,title,quantity,state,created,ack in rows:
        alerts.append(dict(id=aid,title=title,quantity=quantity,state=state,
            created_at=created.isoformat(),acknowledged=ack,
            supplier_search_url='https://www.aliexpress.com/wholesale?' + urlencode({'SearchText':title})))
    return dict(threshold=THRESHOLD,checked_at=row[0].isoformat() if row and row[0] else None,alerts=alerts)

def acknowledge_alert(aid):
    with _connect() as conn:
        prepare(conn)
        return conn.execute("UPDATE inventory_alerts SET acknowledged=TRUE WHERE shop=%s AND id=%s RETURNING id",
            (store_key(),aid)).fetchone() is not None

