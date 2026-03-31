import os
import json
import logging
import datetime
from urllib.parse import urlencode
from dotenv import load_dotenv

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from aiohttp import web
import asyncio

from date_time_picker import create_calendar, process_calendar_selection, create_time_keyboard, process_time_selection

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DATETIME, TXN_TYPE, AMOUNT, CATEGORY, TITLE, NOTE, ACCOUNT = range(7)

def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

CONFIG = load_config()

def get_sheet():
    if not os.path.exists("credentials.json"):
        raise FileNotFoundError("credentials.json not found! Please add your Service Account JSON.")
    
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID not found in environment variables.")
    return client.open_by_key(sheet_id).sheet1

def build_keyboard(options, columns=2):
    keyboard = []
    for i in range(0, len(options), columns):
        row = [InlineKeyboardButton(opt, callback_data=opt) for opt in options[i:i+columns]]
        keyboard.append(row)
    return keyboard

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm your Cashew Expense Tracker bot.\n"
        "Type /add or /a to start logging a transaction.\n"
        "Type /cancel at any time to abort."
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    context.user_data['datetime'] = now_str
    
    keyboard = [
        [InlineKeyboardButton(f"Use Current: {now_str}", callback_data="CURRENT_DATE")],
        [InlineKeyboardButton("Custom Date", callback_data="CUSTOM_DATE")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "When did this transaction happen?"
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    
    return DATETIME

async def handle_datetime_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "CURRENT_DATE":
        keyboard = [
            [InlineKeyboardButton("Income", callback_data="Income"), InlineKeyboardButton("Expense", callback_data="Expense")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"Date: {context.user_data['datetime']}\n\nSelect the transaction type:", reply_markup=reply_markup)
        return TXN_TYPE
    
    elif data == "CUSTOM_DATE":
        await query.edit_message_text(text="Please select a date:", reply_markup=create_calendar())
        return DATETIME

    elif data.startswith("CAL-"):
        completed, date_str, new_markup = process_calendar_selection(query)
        if new_markup:
            await query.edit_message_text(text="Please select a date:", reply_markup=new_markup)
        elif completed:
            context.user_data['temp_date'] = date_str
            await query.edit_message_text(text=f"Date selected: {date_str}\n\nPlease select the hour:", reply_markup=create_time_keyboard())
        return DATETIME
        
    elif data.startswith("TIME-"):
        completed, time_str, new_markup = process_time_selection(query)
        if new_markup:
            await query.edit_message_text(text=f"Date selected: {context.user_data['temp_date']}\n\nPlease select the minute:", reply_markup=new_markup)
        elif completed:
            context.user_data['datetime'] = f"{context.user_data['temp_date']} {time_str}"
            keyboard = [
                [InlineKeyboardButton("Income", callback_data="Income"), InlineKeyboardButton("Expense", callback_data="Expense")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Date & Time saved: {context.user_data['datetime']}\n\nSelect the transaction type:", reply_markup=reply_markup)
            return TXN_TYPE
        return DATETIME

    elif data == "IGNORE":
        return DATETIME

async def handle_custom_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['datetime'] = update.message.text.strip()
    keyboard = [
        [InlineKeyboardButton("Income", callback_data="Income"), InlineKeyboardButton("Expense", callback_data="Expense")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Custom date saved!\n\nSelect the transaction type:", reply_markup=reply_markup)
    return TXN_TYPE

async def handle_txn_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['type'] = query.data
    await query.edit_message_text(text=f"Type: {query.data}\n\nPlease type the exact amount (numbers only):")
    return AMOUNT

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if context.user_data['type'] == 'Expense' and amount > 0:
            amount = -amount
        elif context.user_data['type'] == 'Income' and amount < 0:
            amount = abs(amount)
            
        context.user_data['amount'] = amount
        reply_markup = InlineKeyboardMarkup(build_keyboard(CONFIG['categories'], columns=3))
        await update.message.reply_text(f"Amount logged: {amount}\n\nSelect a Category:", reply_markup=reply_markup)
        return CATEGORY
    except ValueError:
        await update.message.reply_text("Invalid amount! Please enter a valid number (e.g. 50 or 50.5).")
        return AMOUNT

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['category'] = query.data
    await query.edit_message_text(f"Category: {query.data}\n\nPlease type a Title for this transaction:")
    return TITLE

async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text.strip()
    
    keyboard = [[InlineKeyboardButton("Skip Note", callback_data="SKIP_NOTE")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Title saved.\n\nPlease type a Note (description), or click Skip:", reply_markup=reply_markup)
    return NOTE

async def handle_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "SKIP_NOTE":
        context.user_data['note'] = ""
        reply_markup = InlineKeyboardMarkup(build_keyboard(CONFIG['accounts'], columns=2))
        await query.edit_message_text(f"Note skipped!\n\nFinally, select the Account:", reply_markup=reply_markup)
        return ACCOUNT

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['note'] = update.message.text.strip()
    
    reply_markup = InlineKeyboardMarkup(build_keyboard(CONFIG['accounts'], columns=2))
    await update.message.reply_text(f"Note saved!\n\nFinally, select the Account:", reply_markup=reply_markup)
    return ACCOUNT

async def save_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['account'] = query.data
    await query.edit_message_text("Processing your transaction... ")
    
    try:
        data = context.user_data
        # DateTime | Amount | Category | Title | Note | Account
        row = [
            data.get('datetime'),
            data.get('amount'),
            data.get('category'),
            data.get('title'),
            data.get('note', ''),
            data.get('account')
        ]
        
        loop = asyncio.get_event_loop()
        sheet = await loop.run_in_executor(None, get_sheet)
        await loop.run_in_executor(None, lambda: sheet.append_row(row))
        
        # Dark Link formulation
        params = {
            'amount': data.get('amount'),
            'title': data.get('title'),
            'category': data.get('category'),
        }
        if data.get('account'):
            params['account'] = data.get('account')
        if data.get('note'):
            params['note'] = data.get('note')
            
        qs = urlencode(params)
        cashew_link = f"https://cashewapp.web.app/addTransaction?{qs}"
        
        keyboard = [[InlineKeyboardButton("🎯 Open in Cashew", url=cashew_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        summary = (
            "✅ *Transaction Saved & Logged!* ✅\n\n"
            f"📅 *Date/Time:* {data.get('datetime')}\n"
            f"💰 *Amount:* {data.get('amount')}\n"
            f"🏷️ *Category:* {data.get('category')}\n"
            f"📝 *Title:* {data.get('title')}\n"
            f"🏦 *Account:* {data.get('account')}"
        )
        if data.get('note'):
            summary += f"\n🗒️ *Note:* {data.get('note')}"
            
        await query.edit_message_text(text=summary, reply_markup=reply_markup, parse_mode="Markdown")
        
    except FileNotFoundError as e:
         await query.edit_message_text(f"❌ Configuration Error: {str(e)}")
    except Exception as e:
        logger.error(f"Error saving transaction: {e}")
        await query.edit_message_text(f"❌ Failed to save transaction! Error: {str(e)}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Transaction cancelled.")
    else:
        await update.callback_query.message.reply_text("Transaction cancelled.")
    return ConversationHandler.END

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Dummy Web server started on port {port}")

async def main():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("No TELEGRAM_BOT_TOKEN environment variable found! Exiting.")
        return

    application = Application.builder().token(bot_token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start), 
            CommandHandler("a", add_start)
        ],
        states={
            DATETIME: [
                CallbackQueryHandler(handle_datetime_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_datetime)
            ],
            TXN_TYPE: [CallbackQueryHandler(handle_txn_type)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            CATEGORY: [CallbackQueryHandler(handle_category)],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title)],
            NOTE: [
                CallbackQueryHandler(handle_note_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)
            ],
            ACCOUNT: [CallbackQueryHandler(save_transaction)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    await start_web_server()
    
    logger.info("Bot is running...")
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped natively.")
