import os

# توکن ربات که از BotFather گرفتید
BOT_TOKEN = os.getenv("BOT_TOKEN", "TOKEN_SHOMA")

# آیدی عددی شما که از userinfobot گرفتید
ADMIN_ID = int(os.getenv("ADMIN_ID", "ID_SHOMA"))

# تنظیمات هایپرلیکویید
HYPERLIQUID_API_URL = "https://api.hyperliquid.xyz/info"
CHECK_INTERVAL = 5
