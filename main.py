from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

import csv
import os
from dotenv import load_dotenv
import os
import threading
import time
import requests
from flask import Flask

# === CONFIGURATION ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 156878195  # Replace with your Telegram user ID
MENU_FILE = "menu.txt"

# === States ===
CHOOSING_FOOD, CHOOSING_QUANTITY, CHOOSING_DELIVERY, GETTING_NAME, GETTING_ADDRESS = range(5)

# === Start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 خوش آمدید! برای سفارش /order را وارد کنید.")

# === Start Order ===
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if not os.path.exists(MENU_FILE):
        await update.message.reply_text("❌ منو هنوز تنظیم نشده است.")
        return ConversationHandler.END

    with open(MENU_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    keyboard = [[InlineKeyboardButton(item.strip(), callback_data=item.strip())] for item in lines if item.strip()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🍴 لطفاً یک مورد از منو انتخاب کنید:", reply_markup=reply_markup)
    return CHOOSING_FOOD

# === Choose Food ===
async def choose_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["food"] = query.data

    keyboard = [
        [InlineKeyboardButton("1", callback_data="1"), InlineKeyboardButton("2", callback_data="2")],
        [InlineKeyboardButton("3", callback_data="3"), InlineKeyboardButton("بیشتر", callback_data="custom")]
    ]
    await query.edit_message_text("🔢 چند عدد می‌خواهید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_QUANTITY

# === Choose Quantity ===
async def choose_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "custom":
        await query.edit_message_text("🔢 لطفاً تعداد دلخواه را وارد کنید:")
        return CHOOSING_QUANTITY
    else:
        context.user_data["quantity"] = query.data

        keyboard = [
            [InlineKeyboardButton("تحویل حضوری", callback_data="pickup")],
            [InlineKeyboardButton("ارسال با پیک", callback_data="delivery")]
        ]
        await query.edit_message_text("🚚 نوع تحویل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_DELIVERY

# === Manual Quantity ===
async def manual_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quantity"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("تحویل حضوری", callback_data="pickup")],
        [InlineKeyboardButton("ارسال با پیک", callback_data="delivery")]
    ]
    await update.message.reply_text("🚚 نوع تحویل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_DELIVERY

# === Choose Delivery ===
async def choose_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["delivery"] = query.data
    await query.edit_message_text("📛 لطفاً نام خود را وارد کنید:")
    return GETTING_NAME

# === Get Name ===
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📍 لطفاً آدرس تحویل را وارد کنید:")
    return GETTING_ADDRESS

# === Get Address + Save ===
async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text

    with open("orders.csv", "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            update.message.from_user.username or "",
            context.user_data["name"],
            context.user_data["address"],
            context.user_data["food"],
            context.user_data["quantity"],
            context.user_data["delivery"]
        ])

    admin_msg = (
        f"📦 سفارش جدید:\n"
        f"👤 @{update.message.from_user.username or 'بدون نام'}\n"
        f"👤 نام: {context.user_data['name']}\n"
        f"📍 آدرس: {context.user_data['address']}\n"
        f"🍽 غذا: {context.user_data['food']}\n"
        f"🔢 تعداد: {context.user_data['quantity']}\n"
        f"🚚 تحویل: {context.user_data['delivery']}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)

    summary = (
        f"✅ *سفارش شما ثبت شد!*\n\n"
        f"🍽 {context.user_data['food']}\n"
        f"🔢 تعداد: {context.user_data['quantity']}\n"
        f"📍 آدرس: {context.user_data['address']}\n"
        f"🙏 با تشکر!"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")
    return ConversationHandler.END

# === Cancel ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ سفارش لغو شد.")
    return ConversationHandler.END

# === Show Orders ===
async def get_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط مدیر مجاز است.")
        return

    try:
        with open("orders.csv", "rb") as f:
            await update.message.reply_document(InputFile(f), filename="orders.csv")
    except FileNotFoundError:
        await update.message.reply_text("هیچ سفارشی ثبت نشده است.")

# === Add Flask Server ===
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)


def keep_alive():
    while True:
        requests.get("https://order-bot-h9de.onrender.com")  # Ping yourself
        time.sleep(300)  # Every 5 minutes

# === Main ===
def main():
    # Start Flask server in a thread (for Render)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    threading.Thread(target=keep_alive, daemon=True).start()
    # Start Telegram bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("order", start_order)],
        states={
            CHOOSING_FOOD: [CallbackQueryHandler(choose_food)],
            CHOOSING_QUANTITY: [
                CallbackQueryHandler(choose_quantity),
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_quantity)
            ],
            CHOOSING_DELIVERY: [CallbackQueryHandler(choose_delivery)],
            GETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GETTING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", get_orders))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
