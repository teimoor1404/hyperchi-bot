import aiosqlite

DB_NAME = "tracker.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                last_seen_time INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen_trades (
                trade_id TEXT PRIMARY KEY,
                created_at INTEGER
            )
        """)
        await db.commit()

async def add_wallet(address: str, name: str):
    address = address.strip().lower()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO wallets (address, name, last_seen_time) VALUES (?, ?, ?)", (address, name, 0))
        await db.commit()

async def remove_wallet(address: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM wallets WHERE address = ?", (address.lower(),))
        await db.commit()

async def get_all_wallets():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT address, name, last_seen_time FROM wallets") as cursor:
            return await cursor.fetchall()

async def update_wallet_time(address: str, timestamp: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE wallets SET last_seen_time = ? WHERE address = ?", (timestamp, address.lower()))
        await db.commit()

async def is_trade_seen(trade_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM seen_trades WHERE trade_id = ?", (trade_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def mark_trade_as_seen(trade_id: str, timestamp: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO seen_trades (trade_id, created_at) VALUES (?, ?)", (trade_id, timestamp))
        await db.commit()
