import asyncio
from datetime import datetime
import pytz
from config import CHECK_INTERVAL, ADMIN_ID
from database import get_all_wallets, update_wallet_time, is_trade_seen, mark_trade_as_seen
from hyperliquid import get_user_fills, get_clearinghouse_state

def format_number(val):
    try:
        f = float(val)
        return f"{f:,.4f}".rstrip('0').rstrip('.')
    except:
        return str(val)

def format_trade_message(wallet_name: str, address: str, fill: dict, leverage_info: str = "نامشخص") -> str:
    side_raw = fill.get("side", "")
    direction = fill.get("dir", "")
    coin = fill.get("coin", "UNKNOWN")
    price = float(fill.get("px", 0))
    size = float(fill.get("sz", 0))
    usd_value = price * size
    fee = float(fill.get("fee", 0))
    timestamp = fill.get("time", 0) / 1000.0

    tehran_tz = pytz.timezone('Asia/Tehran')
    trade_time = datetime.fromtimestamp(timestamp, tehran_tz).strftime('%H:%M:%S - %Y/%m/%d')

    is_buy = (side_raw == "B")
    is_spot = ("@" in coin or "/" in coin)

    if "Open Long" in direction or (is_buy and not direction):
        action = "🟢 خرید / Open Long"
    elif "Open Short" in direction or (not is_buy and not direction):
        action = "🔴 فروش / Open Short"
    elif "Close Long" in direction:
        action = "🟠 بستن لانگ / Close Long"
    elif "Close Short" in direction:
        action = "🔵 بستن شورت / Close Short"
    else:
        action = f"⚡ {direction or ('خرید' if is_buy else 'فروش')}"

    market_type = "🪙 اسپات (Spot)" if is_spot else "📈 فیوچرز (Perpetual)"

    msg = (
        f"🚨 <b>معامله جدید ثبت شد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>نام ولت:</b> {wallet_name}\n"
        f"📫 <b>آدرس:</b> <code>{address[:6]}...{address[-4:]}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>نوع معامله:</b> {action}\n"
        f"💎 <b>ارز:</b> <code>{coin}</code>\n"
        f"🌐 <b>مارکت:</b> {market_type}\n"
        f"🔧 <b>اهرم:</b> {leverage_info}\n"
        f"📦 <b>حجم:</b> <code>{format_number(size)} {coin}</code>\n"
        f"💵 <b>قیمت:</b> <code>${format_number(price)}</code>\n"
        f"💰 <b>ارزش معامله:</b> <code>${format_number(usd_value)}</code>\n"
        f"💸 <b>کارمزد:</b> <code>${format_number(fee)}</code>\n"
        f"🕐 <b>زمان (تهران):</b> {trade_time}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='https://app.hyperliquid.xyz/explorer/address/{address}'>مشاهده در مرورگر Hyperliquid</a>"
    )
    return msg

async def track_wallets(bot_app):
    while True:
        try:
            wallets = await get_all_wallets()
            for address, name, last_seen in wallets:
                fills = await get_user_fills(address)
                if not fills:
                    continue

                if last_seen == 0:
                    latest_fill_time = max(f.get("time", 0) for f in fills) if fills else 0
                    await update_wallet_time(address, latest_fill_time)
                    for f in fills:
                        t_id = f"{address}_{f.get('tid', f.get('time'))}"
                        await mark_trade_as_seen(t_id, f.get('time', 0))
                    continue

                state = await get_clearinghouse_state(address)
                leverage_map = {}
                if state and "assetPositions" in state:
                    for pos in state["assetPositions"]:
                        p = pos.get("position", {})
                        c = p.get("coin")
                        lev = p.get("leverage", {})
                        if c:
                            lev_type = lev.get("type", "cross")
                            lev_val = lev.get("value", 1)
                            leverage_map[c] = f"×{lev_val} ({lev_type})"

                new_max_time = last_seen
                for fill in reversed(fills):
                    fill_time = fill.get("time", 0)
                    trade_id = f"{address}_{fill.get('tid', fill_time)}"

                    if fill_time > last_seen and not (await is_trade_seen(trade_id)):
                        coin = fill.get("coin", "")
                        leverage_str = leverage_map.get(coin, "×1 یا اسپات")

                        msg = format_trade_message(name, address, fill, leverage_str)

                        if ADMIN_ID != 0:
                            try:
                                await bot_app.bot.send_message(
                                    chat_id=ADMIN_ID,
                                    text=msg,
                                    parse_mode="HTML",
                                    disable_web_page_preview=True
                                )
                            except Exception as err:
                                print(f"Failed to send alert to Telegram: {err}")

                        await mark_trade_as_seen(trade_id, fill_time)
                        if fill_time > new_max_time:
                            new_max_time = fill_time

                if new_max_time > last_seen:
                    await update_wallet_time(address, new_max_time)

        except Exception as e:
            print(f"Error in tracker loop: {e}")

        await asyncio.sleep(CHECK_INTERVAL)
