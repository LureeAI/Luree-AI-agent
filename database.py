import os
import psycopg


def _connect():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is missing")
    return psycopg.connect(url, connect_timeout=10)


def _prepare(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shopify_connections (
            shop TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def save_shopify_connection(shop, access_token):
    with _connect() as conn:
        _prepare(conn)
        conn.execute("""
            INSERT INTO shopify_connections (shop, access_token)
            VALUES (%s, %s)
            ON CONFLICT (shop) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                updated_at = NOW()
        """, (shop, access_token))


def load_shopify_connection():
    shop = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip()
    shop = shop.replace("https://", "").replace("http://", "")
    shop = shop.rstrip("/")

    with _connect() as conn:
        _prepare(conn)
        row = conn.execute("""
            SELECT shop, access_token
            FROM shopify_connections
            WHERE shop = %s
        """, (shop,)).fetchone()

    return tuple(row) if row else (None, None)
