import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:securepassword123@localhost:5432/gateway_telemetry")
db_pool=None
# we initialise the pool when the server starts

async def init_db_pool():
    """creates a pool of persistent connections"""
    global db_pool

    try:
        db_pool=await asyncpg.create_pool(DATABASE_URL)
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

    except Exception as e:
        print(f"Error creating database connection pool: {e}")

async def close_db_pool():
    """closes the connection pool on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print("Database connection pool closed")