import asyncio
import os
from flask import Flask
from threading import Thread
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, Update
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)
from config import BOT_TOKEN, ADMIN_ID
from database import init_db, add_wallet, remove_wallet, get_all_wallets
from tracker import track_wallets

# ---- وب‌سرور برای بیدار ماندن در رندر ----
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web, daemon=True).start()
# ------------------------------------------

GET_ADDRESS, GET_NAME = range(2)

def is_admin(update: Update) -> bool:
    return ADMIN_ID == 0 or (update.effective_user and update.effective_user.id == ADMIN_ID)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن کیف پول", callback_data="btn_add"),
         InlineKeyboardButton("📋 لیست کیف پول‌ها", callback_data="btn_list")],
        [InlineKeyboardButton("🗑️ حذف کیف پول", callback_data="btn_delete"),
         InlineKeyboardButton("🔄 وضعیت ربات", callback_data="btn_refresh")]
    ])

def persistent_keyboard():
    """دکمه ثابت پایین صفحه چت"""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 منو")]],
        resize_keyboard=True
    )

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    await update.message.reply_text(
        "👇 <b>منوی مدیریت ربات:</b>",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ شما اجازه دسترسی ندارید.")
        return
    await update.message.reply_text(
        "🤖 <b>ربات ردیاب هایپرلیکویید فعال است.</b>\n"
        "با دکمه 🏠 منو در پایین صفحه، همیشه به تنظیمات دسترسی دارید.",
        reply_markup=persistent_keyboard(),
        parse_mode="HTML"
    )
    await update.message.reply_text(
        "👇 <b>منوی مدیریت:</b>",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        return

    data = query.data
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="btn_main_menu")]])

    if data == "btn_main_menu":
        await query.edit_message_text("👇 <b>منوی مدیریت:</b>", reply_markup=main_keyboard(), parse_mode="HTML")

    elif data == "btn_list":
        wallets = await get_all_wallets()
        if not wallets:
            text = "📭 هیچ کیف پولی ثبت نشده است."
        else:
            text = f"📋 <b>کیف پول‌های تحت نظر ({len(wallets)} مورد):</b>\n\n"
            for i, (addr, name, _) in enumerate(wallets, 1):
                text += f"{i}. 🏷 <b>{name}</b>\n   📫 <code>{addr}</code>\n\n"
        await query.edit_message_text(text, reply_markup=back_kb, parse_mode="HTML")

    elif data == "btn_delete":
        wallets = await get_all_wallets()
        if not wallets:
            await query.edit_message_text("📭 ولتی برای حذف نیست.", reply_markup=back_kb)
            return
        btns = [[InlineKeyboardButton(f"❌ {name} ({addr[:6]}...)", callback_data=f"del_{addr}")]
                for addr, name, _ in wallets]
        btns.append([InlineKeyboardButton("🔙 انصراف", callback_data="btn_main_menu")])
        await query.edit_message_text("🗑️ کدام حذف شود؟", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("del_"):
        await remove_wallet(data.replace("del_", ""))
        await query.edit_message_text("✅ ولت حذف شد.", reply_markup=back_kb)

    elif data == "btn_refresh":
        wallets = await get_all_wallets()
        await query.edit_message_text(
            f"🟢 <b>ربات فعال است.</b>\n"
            f"🗄 دیتابیس: دائمی (Neon) ✅\n"
            f"👁 ولت‌های در حال رصد: <b>{len(wallets)}</b>",
            reply_markup=main_keyboard(), parse_mode="HTML"
        )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        return ConversationHandler.END
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="btn_cancel")]])
    await query.edit_message_text("📝 آدرس کیف پول (0x...) را ارسال کنید:", reply_markup=cancel_kb)
    return GET_ADDRESS

async def got_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addr = update.message.text.strip()
    if addr == "🏠 منو":
        await show_menu(update, context)
        return ConversationHandler.END
    if not (addr.startswith("0x") and len(addr) == 42):
        await update.message.reply_text("⚠️ آدرس نامعتبر است (باید ۴۲ کاراکتر و با 0x باشد). دوباره بفرستید:")
        return GET_ADDRESS
    context.user_data["addr"] = addr
    await update.message.reply_text("✅ آدرس ثبت شد.\n🏷 حالا یک نام دلخواه بفرستید:")
    return GET_NAME

async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    addr = context.user_data.get("addr")
    if not addr:
        await update.message.reply_text("خطا رخ داد، دوباره تلاش کنید.", reply_markup=main_keyboard())
        return ConversationHandler.END
    await add_wallet(addr, name)
    await update.message.reply_text(
        f"🎉 <b>ثبت شد!</b>\n🏷 نام: {name}\n📫 <code>{addr}</code>\n\n🛰 ردیابی فعال شد.",
        reply_markup=main_keyboard(), parse_mode="HTML"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ لغو شد.", reply_markup=main_keyboard())
    return ConversationHandler.END

async def post_init(application):
    await init_db()
    asyncio.create_task(track_wallets(application))

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده است!")
        return

    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_start, pattern="^btn_add$")],
        states={
            GET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_address)],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^btn_cancel$"),
            CommandHandler("start", start),
        ],
        conversation_timeout=120,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^🏠 منو$"), show_menu))
    app.add_handler(CallbackQueryHandler(menu_handler))

    print("🤖 ربات روشن شد...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
