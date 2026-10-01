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



def store_key():
    return os.environ.get('SHOPIFY_STORE_DOMAIN', '').strip().replace('https://', '').replace('http://', '').rstrip('/')


def _prepare_memory(conn):
    conn.execute('SELECT pg_advisory_xact_lock(7432101)')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent_messages (
        id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, role TEXT NOT NULL,
        content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    conn.execute('CREATE INDEX IF NOT EXISTS agent_messages_shop_id ON agent_messages(shop, id)')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent_preferences (
        shop TEXT PRIMARY KEY, instructions TEXT NOT NULL DEFAULT '')''')


def load_messages(limit=20):
    with _connect() as conn:
        _prepare_memory(conn)
        rows = conn.execute('''SELECT id, role, content FROM (
            SELECT id, role, content FROM agent_messages WHERE shop=%s
            ORDER BY id DESC LIMIT %s) recent ORDER BY id''', (store_key(), limit)).fetchall()
    return [{'id': row[0], 'role': row[1], 'content': row[2]} for row in rows]


def save_exchange(message, answer):
    with _connect() as conn:
        _prepare_memory(conn)
        conn.cursor().executemany('INSERT INTO agent_messages(shop,role,content) VALUES (%s,%s,%s)',
                         [(store_key(), 'user', message), (store_key(), 'assistant', answer)])


def get_preferences():
    with _connect() as conn:
        _prepare_memory(conn)
        row = conn.execute('SELECT instructions FROM agent_preferences WHERE shop=%s', (store_key(),)).fetchone()
    return row[0] if row else ''


def set_preferences(instructions):
    with _connect() as conn:
        _prepare_memory(conn)
        conn.execute('''INSERT INTO agent_preferences(shop,instructions) VALUES (%s,%s)
            ON CONFLICT(shop) DO UPDATE SET instructions=EXCLUDED.instructions''', (store_key(), instructions))


def _prepare_login(conn):
    conn.execute('SELECT pg_advisory_xact_lock(7432102)')
    conn.execute('''CREATE TABLE IF NOT EXISTS agent_login_failures (
        attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    conn.execute("DELETE FROM agent_login_failures WHERE attempted_at < NOW() - INTERVAL '5 minutes'")


def login_allowed():
    with _connect() as conn:
        _prepare_login(conn)
        return conn.execute('SELECT COUNT(*) FROM agent_login_failures').fetchone()[0] < 5


def record_login_failure():
    with _connect() as conn:
        _prepare_login(conn)
        conn.execute('INSERT INTO agent_login_failures DEFAULT VALUES')


def clear_login_failures():
    with _connect() as conn:
        _prepare_login(conn)
        conn.execute('DELETE FROM agent_login_failures')
