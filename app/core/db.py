import asyncpg
import os
from urllib.parse import quote, urlparse

def _build_database_url() -> str:
    existing = os.getenv("DATABASE_URL")
    if existing:
        return existing

    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "Aryan2006%")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "gateway_telemetry")
    safe_password = quote(password, safe="")
    return f"postgresql://{user}:{safe_password}@{host}:{port}/{name}"

DATABASE_URL = _build_database_url()
db_pool=None
# we initialise the pool when the server starts

def _get_database_name(dsn: str) -> str:
    parsed = urlparse(dsn)
    if parsed.scheme and parsed.path:
        db_name = parsed.path.lstrip("/")
        if db_name:
            return db_name

    for key in ("dbname=", "database="):
        if key in dsn:
            for part in dsn.split():
                if part.startswith(key):
                    return part.split("=", 1)[1]

    raise ValueError("DATABASE_URL must include a database name.")

def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'

async def _ensure_database_exists():
    db_name = _get_database_name(DATABASE_URL)
    admin_conn = await asyncpg.connect(dsn=DATABASE_URL, database="postgres")
    try:
        exists = await admin_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name
        )
        if not exists:
            await admin_conn.execute(f"CREATE DATABASE {_quote_ident(db_name)}")
            print(f'Database "{db_name}" created successfully')
    finally:
        await admin_conn.close()

async def init_db_pool():
    """creates a pool of persistent connections"""
    global db_pool

    try:
        db_pool=await asyncpg.create_pool(DATABASE_URL)
    except asyncpg.InvalidCatalogNameError:
        print("Database does not exist. Creating it now.")
        await _ensure_database_exists()
        db_pool=await asyncpg.create_pool(DATABASE_URL)
    except Exception as e:
        print(f"Error creating database connection pool: {e}")
        raise

    print("Database connection pool created successfully")

    async with db_pool.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                id SERIAL PRIMARY KEY,
                primary_provider VARCHAR(50),
                routed_provider VARCHAR(50),
                latency_ms FLOAT,
                status_code INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

async def close_db_pool():
    """closes the connection pool on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("Database connection pool closed")