import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from config import BOT_TOKEN, ADMIN_ID
from database import init_db, add_wallet, remove_wallet, get_all_wallets
from tracker import track_wallets

GET_ADDRESS, GET_NAME = range(2)

def is_admin(update: Update) -> bool:
    if ADMIN_ID == 0:
        return True
    user = update.effective_user
    return user and user.id == ADMIN_ID

def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("➕ افزودن کیف پول", callback_data="btn_add"),
            InlineKeyboardButton("📋 لیست کیف پول‌ها", callback_data="btn_list")
        ],
        [
            InlineKeyboardButton("🗑️ حذف کیف پول", callback_data="btn_delete"),
            InlineKeyboardButton("🔄 بروزرسانی وضعیت", callback_data="btn_refresh")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ شما اجازه دسترسی به این ربات را ندارید.")
        return

    text = (
        "👋 <b>سلام! به ربات ردیاب هایپرلیکویید خوش آمدید.</b>\n\n"
        "این ربات تمام معاملات (اسپات، فیوچرز، خرید، فروش و تغییر اهرم) ولت‌های مشخص شده را به صورت لحظه‌ای اعلام می‌کند.\n\n"
        "👇 از دکمه‌های زیر برای مدیریت ربات استفاده کنید:"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode="HTML")

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        return

    data = query.data

    if data == "btn_main_menu":
        await query.edit_message_text(
            "👇 <b>منوی اصلی ربات:</b>",
            reply_markup=main_keyboard(),
            parse_mode="HTML"
        )

    elif data == "btn_list":
        wallets = await get_all_wallets()
        if not wallets:
            text = "📭 هیچ کیف پولی برای ردیابی ثبت نشده است."
        else:
            text = f"📋 <b>کیف پول‌های تحت نظر ({len(wallets)} مورد):</b>\n\n"
            for i, (addr, name, _) in enumerate(wallets, 1):
                text += f"{i}. 🏷 <b>{name}</b>\n   📫 <code>{addr}</code>\n\n"

        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="btn_main_menu")]])
        await query.edit_message_text(text, reply_markup=back_kb, parse_mode="HTML")

    elif data == "btn_delete":
        wallets = await get_all_wallets()
        if not wallets:
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="btn_main_menu")]])
            await query.edit_message_text("📭 هیچ ولتی برای حذف وجود ندارد.", reply_markup=back_kb)
            return

        buttons = []
        for addr, name, _ in wallets:
            buttons.append([InlineKeyboardButton(f"❌ {name} ({addr[:6]}...)", callback_data=f"del_{addr}")])
        buttons.append([InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="btn_main_menu")])

        await query.edit_message_text(
            "🗑️ <b>برای حذف، روی کیف پول مورد نظر کلیک کنید:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    elif data.startswith("del_"):
        addr_to_delete = data.replace("del_", "")
        await remove_wallet(addr_to_delete)
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="btn_main_menu")]])
        await query.edit_message_text(
            f"✅ ولت با آدرس <code>{addr_to_delete}</code> با موفقیت حذف شد.",
            reply_markup=back_kb,
            parse_mode="HTML"
        )

    elif data == "btn_refresh":
        wallets = await get_all_wallets()
        await query.edit_message_text(
            f"🟢 <b>وضعیت ربات فعال است.</b>\nتعداد ولت‌های در حال رصد: <b>{len(wallets)}</b>",
            reply_markup=main_keyboard(),
            parse_mode="HTML"
        )

async def start_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="btn_cancel_add")]])
    await query.edit_message_text(
        "📝 <b>مرحله اول:</b> لطفاً آدرس کیف پول Hyperliquid (اتریومی 0x...) را ارسال کنید:",
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    return GET_ADDRESS

async def receive_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()

    if not (address.startswith("0x") and len(address) == 42):
        await update.message.reply_text("⚠️ فرمت آدرس نامعتبر است! آدرس باید ۴۲ کاراکتر و با 0x شروع شود. دوباره بفرستید:")
        return GET_ADDRESS

    context.user_data["wallet_address"] = address
    await update.message.reply_text(
        f"✅ آدرس دریافت شد: <code>{address}</code>\n\n"
        f"🏷 <b>مرحله دوم:</b> حالا یک نام دلخواه برای این ولت ارسال کنید (مثلاً: نهنگ شماره ۱):",
        parse_mode="HTML"
    )
    return GET_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    address = context.user_data.get("wallet_address")

    await add_wallet(address, name)

    await update.message.reply_text(
        f"🎉 <b>کیف پول با موفقیت ثبت شد!</b>\n\n"
        f"🏷 <b>نام:</b> {name}\n"
        f"📫 <b>آدرس:</b> <code>{address}</code>\n\n"
        f"🛰️ ردیابی این ولت هم‌اکنون فعال شد.",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ عملیات افزودن لغو شد.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def post_init(application):
    await init_db()
    asyncio.create_task(track_wallets(application))

def main():
    if not BOT_TOKEN or BOT_TOKEN == "TOKEN_SHOMA":
        print("❌ لطفاً توکن ربات را تنظیم کنید!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    add_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_wallet, pattern="^btn_add$")],
        states={
            GET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_address)],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
        },
        fallbacks=[CallbackQueryHandler(cancel_add, pattern="^btn_cancel_add$")],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv_handler)
    app.add_handler(CallbackQueryHandler(menu_callback_handler))

    print("🤖 ربات با موفقیت روشن شد و در حال اجرا است...")
    app.run_polling()

if __name__ == "__main__":
    main()
