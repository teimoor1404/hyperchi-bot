import asyncio
from datetime import datetime
import pytz
from config import CHECK_INTERVAL, ADMIN_ID, AGGREGATION_WINDOW
from database import get_all_wallets, update_wallet_time, is_trade_seen, mark_trade_as_seen
from hyperliquid import get_user_fills, get_clearinghouse_state

def fmt_usd(val):
    """فرمت دلاری با ۲ رقم اعشار"""
    try:
        return f"{float(val):,.2f}"
    except:
        return str(val)

def fmt_size(val):
    """فرمت حجم بدون صفرهای اضافی"""
    try:
        f = float(val)
        s = f"{f:,.6f}".rstrip('0').rstrip('.')
        return s if s else "0"
    except:
        return str(val)

def aggregate_fills(fills):
    """ادغام معاملات تکه‌تکه یک سفارش در یک گروه"""
    groups = []
    for fill in sorted(fills, key=lambda x: x.get("time", 0)):
        coin = fill.get("coin", "")
        direction = fill.get("dir", "")
        side = fill.get("side", "")
        ftime = fill.get("time", 0)
        sz = float(fill.get("sz", 0))
        px = float(fill.get("px", 0))
        fee = float(fill.get("fee", 0))
        pnl = float(fill.get("closedPnl", 0) or 0)

        placed = False
        for g in groups:
            same = (g["coin"] == coin and g["dir"] == direction and g["side"] == side)
            in_window = abs(ftime - g["last_time"]) <= AGGREGATION_WINDOW * 1000
            if same and in_window:
                g["size"] += sz
                g["notional"] += sz * px
                g["fee"] += fee
                g["pnl"] += pnl
                g["count"] += 1
                g["last_time"] = max(g["last_time"], ftime)
                g["ids"].append(fill.get("tid", ftime))
                placed = True
                break

        if not placed:
            groups.append({
                "coin": coin, "dir": direction, "side": side,
                "size": sz, "notional": sz * px, "fee": fee, "pnl": pnl,
                "count": 1, "last_time": ftime,
                "ids": [fill.get("tid", ftime)]
            })
    return groups

def build_message(wallet_name, address, g, leverage_info, position_info):
    coin = g["coin"]
    direction = g["dir"]
    is_buy = (g["side"] == "B")
    size = g["size"]
    avg_price = g["notional"] / size if size else 0
    is_spot = ("@" in coin or "/" in coin)

    if "Open Long" in direction:
        action = "🟢 خرید / Open Long"
    elif "Open Short" in direction:
        action = "🔴 فروش / Open Short"
    elif "Close Long" in direction:
        action = "🟠 بستن لانگ / Close Long"
    elif "Close Short" in direction:
        action = "🔵 بستن شورت / Close Short"
    elif direction:
        action = f"⚡ {direction}"
    else:
        action = "🟢 خرید (Buy)" if is_buy else "🔴 فروش (Sell)"

    market_type = "🪙 اسپات (Spot)" if is_spot else "📈 فیوچرز (Perpetual)"
    tehran = pytz.timezone('Asia/Tehran')
    ttime = datetime.fromtimestamp(g["last_time"] / 1000.0, tehran).strftime('%H:%M:%S - %Y/%m/%d')

    merge_note = f"  <i>(ادغام {g['count']} سفارش)</i>" if g["count"] > 1 else ""

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
        f"📦 <b>حجم:</b> <code>{fmt_size(size)} {coin}</code>{merge_note}\n"
        f"💵 <b>میانگین قیمت:</b> <code>${fmt_usd(avg_price)}</code>\n"
        f"💰 <b>ارزش معامله:</b> <code>${fmt_usd(g['notional'])}</code>\n"
    )

    if abs(g["pnl"]) > 0.009:
        emoji = "💹" if g["pnl"] > 0 else "📉"
        sign = "+" if g["pnl"] > 0 else "-"
        msg += f"{emoji} <b>سود/زیان:</b> <code>{sign}${fmt_usd(abs(g['pnl']))}</code>\n"

    msg += f"💸 <b>کارمزد:</b> <code>${fmt_usd(g['fee'])}</code>\n"

    if position_info:
        msg += f"📌 <b>پوزیشن فعلی:</b> {position_info}\n"

    msg += (
        f"🕐 <b>زمان (تهران):</b> {ttime}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='https://app.hyperliquid.xyz/explorer/address/{address}'>مشاهده در Hyperliquid</a>"
    )
    return msg

async def track_wallets(bot_app):
    print("🛰️ موتور ردیابی شروع به کار کرد...")
    while True:
        try:
            wallets = await get_all_wallets()
            for address, name, last_seen in wallets:
                fills = await get_user_fills(address)
                if not fills:
                    continue

                # ولت تازه اضافه شده: فقط زمان را ثبت کن، پیام قدیمی نفرست
                if not last_seen or last_seen == 0:
                    latest = max(f.get("time", 0) for f in fills)
                    await update_wallet_time(address, latest)
                    for f in fills[:50]:
                        await mark_trade_as_seen(f"{address}_{f.get('tid', f.get('time'))}", f.get("time", 0))
                    continue

                # فقط معاملات جدید
                new_fills = []
                for f in fills:
                    ftime = f.get("time", 0)
                    tid = f"{address}_{f.get('tid', ftime)}"
                    if ftime > last_seen and not await is_trade_seen(tid):
                        new_fills.append(f)

                if not new_fills:
                    continue

                # وضعیت پوزیشن‌ها برای اهرم
                state = await get_clearinghouse_state(address)
                lev_map, pos_map = {}, {}
                if state and "assetPositions" in state:
                    for item in state["assetPositions"]:
                        p = item.get("position", {})
                        c = p.get("coin")
                        if not c:
                            continue
                        lev = p.get("leverage", {})
                        lev_map[c] = f"×{lev.get('value', 1)} ({lev.get('type', 'cross')})"
                        szi = float(p.get("szi", 0))
                        if abs(szi) > 0:
                            side_txt = "لانگ 🟢" if szi > 0 else "شورت 🔴"
                            pos_map[c] = f"{side_txt} {fmt_size(abs(szi))} {c}"

                # ادغام و ارسال
                groups = aggregate_fills(new_fills)
                max_time = last_seen
                for g in groups:
                    lev = lev_map.get(g["coin"], "×1 یا اسپات")
                    pos = pos_map.get(g["coin"], "بسته شد / ندارد")
                    msg = build_message(name, address, g, lev, pos)

                    if ADMIN_ID != 0:
                        try:
                            await bot_app.bot.send_message(
                                chat_id=ADMIN_ID, text=msg,
                                parse_mode="HTML", disable_web_page_preview=True
                            )
                        except Exception as err:
                            print(f"❌ خطا در ارسال پیام: {err}")

                    for tid in g["ids"]:
                        await mark_trade_as_seen(f"{address}_{tid}", g["last_time"])
                    max_time = max(max_time, g["last_time"])
                    await asyncio.sleep(0.4)

                if max_time > last_seen:
                    await update_wallet_time(address, max_time)

        except Exception as e:
            print(f"⚠️ خطا در حلقه ردیابی: {e}")

        await asyncio.sleep(CHECK_INTERVAL)
