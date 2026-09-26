import asyncpg
from config import DATABASE_URL

_pool = None

async def get_pool():
    """ساخت یا برگرداندن استخر اتصال به دیتابیس"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
            ssl="require"
        )
    return _pool

async def init_db():
    """ساخت جداول در اولین اجرا"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                last_seen_time BIGINT DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_trades (
                trade_id TEXT PRIMARY KEY,
                created_at BIGINT
            )
        """)
        # پاک کردن رکوردهای خیلی قدیمی برای سبک ماندن دیتابیس
        await conn.execute("""
            DELETE FROM seen_trades
            WHERE created_at < (EXTRACT(EPOCH FROM NOW()) * 1000 - 604800000)
        """)
    print("✅ دیتابیس دائمی متصل و آماده شد.")

async def add_wallet(address: str, name: str):
    address = address.strip().lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wallets (address, name, last_seen_time)
            VALUES ($1, $2, 0)
            ON CONFLICT (address) DO UPDATE SET name = EXCLUDED.name
        """, address, name)

async def remove_wallet(address: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM wallets WHERE address = $1", address.lower())

async def get_all_wallets():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT address, name, last_seen_time FROM wallets ORDER BY name")
        return [(r["address"], r["name"], r["last_seen_time"]) for r in rows]

async def update_wallet_time(address: str, timestamp: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE wallets SET last_seen_time = $1 WHERE address = $2",
            int(timestamp), address.lower()
        )

async def is_trade_seen(trade_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM seen_trades WHERE trade_id = $1", trade_id)
        return row is not None

async def mark_trade_as_seen(trade_id: str, timestamp: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO seen_trades (trade_id, created_at)
            VALUES ($1, $2)
            ON CONFLICT (trade_id) DO NOTHING
        """, trade_id, int(timestamp))
