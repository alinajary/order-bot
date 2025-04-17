from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

import csv
import asyncio
import os
import sys
from dotenv import load_dotenv
import threading
import time
import requests
from flask import Flask, request
from csv2excel import csv2excel
# === CONFIGURATION ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 156878195  # Replace with your Telegram user ID
MENU_FILE = "menu.txt"
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")  # e.g., "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Replace with your actual webhook URL
DEV_MODE = os.getenv("DEV_MOD")  # Set to "true" for local development

# === States ===
CHOOSING_FOOD, CHOOSING_QUANTITY, CHOOSING_DELIVERY, GETTING_NAME, GETTING_TEL_NUM, GETTING_ADDRESS, CHOOSING_DATETIME = range(7)

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot application
application = ApplicationBuilder().token(BOT_TOKEN).build()


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
    await update.message.reply_text("📍 لطفاً شماره تماس خود را وارد کنید:")
    return GETTING_TEL_NUM

async def get_telephone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["telephone"] = update.message.text
    await update.message.reply_text("📍 لطفاً آدرس تحویل را وارد کنید:")
    return GETTING_ADDRESS
# === Get Address + Save ===
async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text("📅 لطفاً تاریخ و زمان تحویل را وارد کنید (مثال: 1402/02/01 ساعت 14:00):")
    return CHOOSING_DATETIME

# === Get Date and Time ===
async def get_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["datetime"] = update.message.text

    # Generate order number
    counter_file = "order_counter.txt"
    if not os.path.exists(counter_file):
        with open(counter_file, "w") as f:
            f.write("101")  # Initialize the counter

    with open(counter_file, "r") as f:
        order_number = int(f.read().strip())

    # Increment and save the new order number
    with open(counter_file, "w") as f:
        f.write(str(order_number + 1))

    # Save order to CSV
    with open("orders.csv", "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            order_number,  # Add order number
            update.message.from_user.username or "",
            context.user_data["name"],
            context.user_data["address"],
            context.user_data["food"],
            context.user_data["quantity"],
            context.user_data["delivery"],
            context.user_data["datetime"],  # Save date and time
            "pending"  # Default state
        ])

    # Notify Admin
    csv_file = "orders.csv"
    csv2excel_file = csv2excel(csv_file, "orders.xlsx")
    csv2excel_file.convert()
    admin_msg = (
        f"📦 سفارش جدید (شماره سفارش: {order_number}):\n"
        f"👤 @{update.message.from_user.username or 'بدون نام'}\n"
        f"👤 نام: {context.user_data['name']}\n"
        f"📍 آدرس: {context.user_data['address']}\n"
        f"🍽 غذا: {context.user_data['food']}\n"
        f"🔢 تعداد: {context.user_data['quantity']}\n"
        f"🚚 تحویل: {context.user_data['delivery']}\n"
        f"📅 تاریخ و زمان: {context.user_data['datetime']}\n"
        f"📌 وضعیت: pending"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)

    # Send Confirmation to User
    summary = (
        f"✅ *سفارش شما ثبت شد!*\n\n"
        f"📦 *شماره سفارش:* {order_number}\n"
        f"🍽 {context.user_data['food']}\n"
        f"🔢 تعداد: {context.user_data['quantity']}\n"
        f"📍 آدرس: {context.user_data['address']}\n"
        f"📅 تاریخ و زمان: {context.user_data['datetime']}\n"
        f"📌 وضعیت: pending\n"
        f"🙏 با تشکر!"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")
    return ConversationHandler.END
# === Cancel ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
# Clear user data
    context.user_data.clear()

    # Notify the user
    await update.message.reply_text("❌ سفارش لغو شد. اگر نیاز به کمک دارید، دستور /start را وارد کنید.")
    return ConversationHandler.END

# === Show Orders ===
async def get_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط مدیر مجاز است.")
        return

    try:
        with open("orders.xlsx", "rb") as f:
            await update.message.reply_document(InputFile(f), filename="orders.xlsx")
    except FileNotFoundError:
        await update.message.reply_text("هیچ سفارشی ثبت نشده است.")

# === Update Order State ===
async def update_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط مدیر مجاز است.")
        return

    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❌ دستور نامعتبر است. استفاده کنید: /update_order <شماره سفارش> <وضعیت جدید>")
            return

        order_number = args[0]
        new_state = args[1].lower()

        if new_state not in ["pending", "approved", "in progress", "delivered"]:
            await update.message.reply_text("❌ وضعیت نامعتبر است. وضعیت‌های معتبر: pending, approved, in progress, delivered")
            return

        # Update the order in the CSV file
        updated = False
        rows = []
        with open("orders.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == order_number:
                    row[-1] = new_state  # Update the state
                    updated = True
                rows.append(row)

        if updated:
            with open("orders.csv", "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            await update.message.reply_text(f"✅ وضعیت سفارش {order_number} به {new_state} تغییر یافت.")
        else:
            await update.message.reply_text(f"❌ سفارش با شماره {order_number} یافت نشد.")

    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

# === Check Order Status ===
async def order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) != 1:
            await update.message.reply_text("❌ دستور نامعتبر است. استفاده کنید: /order_status <شماره سفارش>")
            return

        order_number = args[0]

        # Find the order in the CSV file
        with open("orders.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == order_number:
                    state = row[-1]
                    await update.message.reply_text(f"📦 وضعیت سفارش {order_number}: {state}")
                    return

        await update.message.reply_text(f"❌ سفارش با شماره {order_number} یافت نشد.")

    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

# === Add Flask Server ===
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

async def delete_webhook(app):
    await app.bot.delete_webhook()
    print("✅ Webhook deleted successfully.")

# === Main ===
# def main():
#     # Start Flask server in a thread (for Render)
#     flask_thread = threading.Thread(target=run_flask)
#     flask_thread.daemon = True
#     flask_thread.start()
#     # Start Telegram bot
#     app = ApplicationBuilder().token(BOT_TOKEN).build()

#     conv_handler = ConversationHandler(
#         entry_points=[CommandHandler("order", start_order)],
#         states={
#             CHOOSING_FOOD: [CallbackQueryHandler(choose_food)],
#             CHOOSING_QUANTITY: [
#                 CallbackQueryHandler(choose_quantity),
#                 MessageHandler(filters.TEXT & ~filters.COMMAND, manual_quantity)
#             ],
#             CHOOSING_DELIVERY: [CallbackQueryHandler(choose_delivery)],
#             GETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
#             GETTING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
#         },
#         fallbacks=[CommandHandler("cancel", cancel)],
#     )

#     app.add_handler(conv_handler)
#     app.add_handler(CommandHandler("start", start))
#     app.add_handler(CommandHandler("orders", get_orders))
#     print("🤖 Bot is running...")
#     app.run_polling()

def main():
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
            GETTING_TEL_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_telephone)],
            GETTING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
            CHOOSING_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_datetime)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", get_orders))
    app.add_handler(CommandHandler("update_order", update_order))
    app.add_handler(CommandHandler("order_status", order_status))

    print("🤖 Bot is running...")

    if DEV_MODE == "true":
        app.run_polling()
    else:
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            webhook_url=WEBHOOK_URL,
            url_path=WEBHOOK_PATH
        )

if __name__ == "__main__":
    main()