import os

# توکن ربات که از BotFather گرفتید
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# آیدی عددی شما که از userinfobot گرفتید
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# آدرس دیتابیس دائمی (Neon Postgres)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# تنظیمات هایپرلیکویید
HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz/info"

# فاصله زمانی چک کردن ولت‌ها (ثانیه)
CHECK_INTERVAL =15

# پنجره زمانی ادغام معاملات تکه‌تکه (ثانیه)
AGGREGATION_WINDOW = 8
