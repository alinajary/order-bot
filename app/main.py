from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from user_vendor_mapping import *
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
from bot_logger import BotLogger

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
MENU_FILE = os.path.join(BASE_DIR, "menu.txt")

log_path = os.path.join(LOGS_DIR, 'bot.log')
logger = BotLogger(log_path)

orders_csv = os.path.join(DATA_DIR, "orders.csv")
orders_xlsx = os.path.join(DATA_DIR, "orders.xlsx")
file_path = orders_xlsx

# === CONFIGURATION ===
load_dotenv()
# BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(ENV_PATH)

BOT_TOKEN = os.getenv("DEBUG_BOT_TOKEN")
ADMIN_ID = 156878195  # Replace with your Telegram user ID
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")  # e.g., "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Replace with your actual webhook URL
DEV_MODE = os.getenv("DEV_MODE")  # Set to "true" for local development

# === States ===
CHOOSING_SERVICE, CHOOSING_QUANTITY, CHOOSING_DELIVERY, GETTING_NAME, GETTING_TEL_NUM, GETTING_ADDRESS, CHOOSING_DATETIME = range(7)

# Initialize Flask app
app = Flask(__name__)

# Initialize the bot application
application = ApplicationBuilder().token(BOT_TOKEN).build()


# === Start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start by user {update.effective_user.id}")
    user = update.effective_user
    user_id = update.effective_user.id

    if context.args:
        vendor_id = context.args[0]
        save_user_vendor_mapping(user_id, vendor_id)
    else:
        vendor_id = get_vendor_id_for_user(user_id)

    # Get vendor_id from the link argument
    # vendor_id = context.args[0] if context.args else None

    if not vendor_id:
        await update.message.reply_text("❌ ورود شما غیر مجاز است. لطفاً از لینک صحیح استفاده کنید.")
        return

    # Save vendor ID to user context and persistent mapping
    context.user_data["vendor_id"] = vendor_id
    # save_user_vendor_mapping(user.id, vendor_id)

    # Load vendor-specific config
    vendor_config = load_vendor_config(vendor_id)
    if not vendor_config:
        logger.error(f"Vendor configuration is None for vendor_id: {vendor_id}")
        await update.message.reply_text("❌ پیکربندی فروشنده پیدا نشد. لطفاً با پشتیبانی تماس بگیرید.")
        return

    # Store config for use in the session
    context.user_data["vendor_config"] = vendor_config

    vendor_name = vendor_config.get("name", "فروشنده")

    await update.message.reply_text(f"👋 خوش آمدید به {vendor_name}!\nبرای ادامه /order را وارد کنید.")


# === Start Order ===
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Start order by user {user_id}")

    if context.args:
        vendor_id = context.args[0]
        save_user_vendor_mapping(user_id, vendor_id)
    else:
        vendor_id = get_vendor_id_for_user(user_id)
    vendor_config = load_vendor_config(vendor_id)
    if not vendor_config:
        logger.error(f"Vendor configuration is None for vendor_id: {vendor_id}")
        await update.message.reply_text("❌ پیکربندی فروشنده پیدا نشد. لطفاً با پشتیبانی تماس بگیرید.")
        return

    # Store config for use in the session
    context.user_data["vendor_config"] = vendor_config

    # Clear only order-related data, keep vendor info
    # vendor_id = context.user_data.get("vendor_id")
    # vendor_config = context.user_data.get("vendor_config")

    if not vendor_id or not vendor_config:
        await update.message.reply_text("❌ Vendor information not found. Please start again using the correct link.")
        return ConversationHandler.END

    # Reset previous order info, but preserve vendor config
    context.user_data["order"] = {}

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    # Load vendor-specific menu or class list
    item_list = load_vendor_config(vendor_id).get("services", [])

    if not item_list:
        await update.message.reply_text("❌ آیتمی برای انتخاب موجود نیست. لطفاً با فروشنده تماس بگیرید.")
        return ConversationHandler.END

    # Generate dynamic keyboard
    keyboard = [
        [InlineKeyboardButton(item, callback_data=item)]
        for item in item_list if item.strip()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Choose prompt based on type
    prompt = "🍴 لطفاً یک مورد را انتخاب کنید:"
    
    await update.message.reply_text(prompt, reply_markup=reply_markup)
    return CHOOSING_SERVICE


# === Choose Food ===
async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Choose service by user {update.effective_user.id}")
    query = update.callback_query
    await query.answer()
    context.user_data["service"] = query.data

    vendor_config = context.user_data.get("vendor_config", {})

    if vendor_config.get("ask_quantity", True):  # default: True
        keyboard = [
            [InlineKeyboardButton("1", callback_data="1"), InlineKeyboardButton("2", callback_data="2")],
            [InlineKeyboardButton("3", callback_data="3"), InlineKeyboardButton("بیشتر", callback_data="custom")]
        ]
        await query.edit_message_text("🔢 چند عدد می‌خواهید؟", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_QUANTITY
    else:
        context.user_data["quantity"] = 1  # default quantity
        return await choose_delivery(update, context)

# === Choose Quantity ===
async def choose_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Choose quantity by user {update.effective_user.id}")
    query = update.callback_query
    await query.answer()

    if query.data == "custom":
        await query.edit_message_text("🔢 لطفاً تعداد دلخواه را وارد کنید:")
        return CHOOSING_QUANTITY
    else:
        context.user_data["quantity"] = query.data

        vendor_config = context.user_data.get("vendor_config", {})
        if vendor_config.get("ask_delivery", True):  # default is True
            keyboard = [
                [InlineKeyboardButton("تحویل حضوری", callback_data="pickup")],
                [InlineKeyboardButton("ارسال با پیک", callback_data="delivery")]
            ]
            await query.edit_message_text("🚚 نوع تحویل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
            return CHOOSING_DELIVERY
        else:
            context.user_data["delivery"] = "pickup"  # or use a default or skip
            return await get_name(update, context)

# === Manual Quantity ===
async def manual_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Manual quantity by user {update.effective_user.id}")
    context.user_data["quantity"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("تحویل حضوری", callback_data="pickup")],
        [InlineKeyboardButton("ارسال با پیک", callback_data="delivery")]
    ]
    await update.message.reply_text("🚚 نوع تحویل را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_DELIVERY

# === Choose Delivery ===
async def choose_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Choose delivery by user {update.effective_user.id}")
    query = update.callback_query
    await query.answer()

    context.user_data["delivery"] = query.data
    await query.edit_message_text("📛 لطفاً نام خود را وارد کنید:")
    return GETTING_NAME

# === Get Name ===
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Get name by user {update.effective_user.id}")
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📍 لطفاً شماره تماس خود را وارد کنید:")
    return GETTING_TEL_NUM

async def get_telephone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Get telephone by user {update.effective_user.id}")
    context.user_data["telephone"] = update.message.text
    await update.message.reply_text("📍 لطفاً آدرس تحویل را وارد کنید:")
    return GETTING_ADDRESS
# === Get Address + Save ===
async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Get address by user {update.effective_user.id}")
    context.user_data["address"] = update.message.text
    await update.message.reply_text("📅 لطفاً تاریخ و زمان تحویل را وارد کنید (مثال: 1402/02/01 ساعت 14:00):")
    return CHOOSING_DATETIME

# === Get Date and Time ===
async def get_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Get datetime by user {update.effective_user.id}")
    context.user_data["datetime"] = update.message.text

    vendor_config = context.user_data.get("vendor_config", {})
    vendor_name = vendor_config.get("name", "Unknown Vendor")

    os.makedirs(DATA_DIR, exist_ok=True)
    counter_file = os.path.join(DATA_DIR, f"{vendor_name}_order_counter.txt")
    order_file = os.path.join(DATA_DIR, f"{vendor_name}_orders.csv")

    if not os.path.exists(counter_file):
        with open(counter_file, "w") as f:
            f.write("101")

    with open(counter_file, "r") as f:
        order_number = int(f.read().strip())

    with open(counter_file, "w") as f:
        f.write(str(order_number + 1))

    # Use vendor-specific CSV file
    with open(order_file, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            order_number,
            update.message.from_user.username or "",
            context.user_data.get("name", ""),
            context.user_data.get("address", ""),
            context.user_data.get("food", ""),
            context.user_data.get("quantity", ""),
            context.user_data.get("delivery", ""),
            context.user_data.get("datetime", ""),
            "pending"
        ])

    # Notify the vendor's admin (dynamic admin ID from config)
    admins = vendor_config.get("admins")
    for admin in admins:
        admin_id = admin.get("id")
        if admin_id:
            msg = (
                f"📦 سفارش جدید از *{vendor_name}* (سفارش #{order_number}):\n"
                f"👤 @{update.message.from_user.username or 'بدون نام'}\n"
                f"👤 نام: {context.user_data.get('name')}\n"
                f"📍 آدرس: {context.user_data.get('address')}\n"
                f"🍽 غذا: {context.user_data.get('service')}\n"
                f"🔢 تعداد: {context.user_data.get('quantity')}\n"
                f"🚚 تحویل: {context.user_data.get('delivery')}\n"
                f"📅 تاریخ و زمان: {context.user_data.get('datetime')}\n"
                f"📌 وضعیت: pending"
            )
            await context.bot.send_message(chat_id=admin_id, text=msg)

    # Send confirmation to user
    summary = (
        f"✅ *سفارش شما با موفقیت ثبت شد!*\n\n"
        f"📦 *شماره سفارش:* {order_number}\n"
        f"🍽 {context.user_data.get('service')}\n"
        f"🔢 تعداد: {context.user_data.get('quantity')}\n"
        f"📍 آدرس: {context.user_data.get('address')}\n"
        f"📅 تاریخ و زمان: {context.user_data.get('datetime')}\n"
        f"📌 وضعیت: pending\n"
        f"🙏 با تشکر از سفارش شما از *{vendor_name}*"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")

    return ConversationHandler.END

# === Cancel ===
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Cancel by user {update.effective_user.id}")

    # Clear conversation-related user data
    context.user_data.clear()

    # Reply safely (handle both command and button-based cancel)
    if update.message:
        await update.message.reply_text("❌ سفارش لغو شد. اگر نیاز به کمک دارید، دستور /start را وارد کنید.")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("❌ سفارش لغو شد. اگر نیاز به کمک دارید، دستور /start را وارد کنید.")

    return ConversationHandler.END


# === Show Orders ===
async def get_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Get orders by user {update.effective_user.id}")

    # Only the admin can access this
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط مدیر مجاز است.")
        return

    # Attempt to send the orders file
    if not os.path.exists(file_path):
        await update.message.reply_text("هیچ سفارشی ثبت نشده است.")
        return

    try:
        with open(file_path, "rb") as f:
            await update.message.reply_document(InputFile(f), filename="orders.xlsx")
    except Exception as e:
        logger.error(f"Error sending orders file: {e}")
        await update.message.reply_text("❌ خطا در ارسال فایل سفارش‌ها.")


# === Update Order State ===
async def update_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Update order by user {update.effective_user.id}")

    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ فقط مدیر مجاز است.")
        return

    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❌ دستور نامعتبر است.\nاستفاده صحیح:\n`/update_order <شماره سفارش> <وضعیت جدید>`", parse_mode="Markdown")
            return

        order_number, new_state = args[0], args[1].lower()

        valid_states = ["pending", "approved", "in progress", "delivered"]
        if new_state not in valid_states:
            await update.message.reply_text(
                f"❌ وضعیت نامعتبر است.\nوضعیت‌های مجاز:\n{', '.join(valid_states)}"
            )
            return

        updated = False
        rows = []

        with open(orders_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == order_number:
                    row[-1] = new_state
                    updated = True
                rows.append(row)

        if updated:
            with open(orders_csv, "w", newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)

            # Optional: also regenerate Excel if you're keeping that updated
            csv2excel_file = csv2excel(orders_csv, orders_xlsx)
            csv2excel_file.convert()

            await update.message.reply_text(f"✅ وضعیت سفارش {order_number} با موفقیت به `{new_state}` تغییر کرد.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ سفارش با شماره `{order_number}` یافت نشد.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in update_order: {e}")
        await update.message.reply_text(f"❌ خطا هنگام بروزرسانی سفارش:\n{e}")


# === Check Order Status ===
async def order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Order status requested by user {update.effective_user.id}")

    try:
        args = context.args
        if len(args) != 1:
            await update.message.reply_text(
                "❌ دستور نامعتبر است.\nاستفاده صحیح:\n`/order_status <شماره سفارش>`",
                parse_mode="Markdown"
            )
            return

        order_number = args[0]

        # Search the order in the CSV
        with open(orders_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0] == order_number:
                    status = row[-1]
                    await update.message.reply_text(
                        f"📦 *وضعیت سفارش* `{order_number}`: `{status}`",
                        parse_mode="Markdown"
                    )
                    return

        await update.message.reply_text(
            f"❌ سفارش با شماره `{order_number}` یافت نشد.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in order_status: {e}")
        await update.message.reply_text(f"❌ خطا هنگام بررسی وضعیت سفارش:\n{e}")


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

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("order", start_order)],
        states={
            CHOOSING_SERVICE: [CallbackQueryHandler(choose_service)],
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
        logger.info("Running in development mode")
    else:
        logger.info("Running in production mode")
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            webhook_url=WEBHOOK_URL,
            url_path=WEBHOOK_PATH
        )

if __name__ == "__main__":
    main()