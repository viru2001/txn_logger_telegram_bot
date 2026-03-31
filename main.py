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

def build_keyboard(options, columns=2, add_back=True, add_cancel=True):
    keyboard = []
    for i in range(0, len(options), columns):
        row = [InlineKeyboardButton(opt, callback_data=opt) for opt in options[i:i+columns]]
        keyboard.append(row)
    
    nav_row = []
    if add_back:
        nav_row.append(InlineKeyboardButton("🔙 Back", callback_data="BACK"))
    if add_cancel:
        nav_row.append(InlineKeyboardButton("❌ Cancel", callback_data="CANCEL"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    return keyboard

def get_summary(user_data, is_final=False):
    if is_final:
        lines = ["✅ Transaction Saved & Logged! ✅\n"]
    else:
        lines = ["📝 Transaction Progress:\n"]
        
    if user_data.get('datetime_final'):
        lines.append(f"📅 Date/Time: {user_data['datetime_final']}")
    if user_data.get('type'):
        lines.append(f"🔄 Type: {user_data['type']}")
    if user_data.get('amount'):
        lines.append(f"💰 Amount: {user_data['amount']}")
    if user_data.get('category'):
        lines.append(f"🏷️ Category: {user_data['category']}")
    if user_data.get('title'):
        lines.append(f"📝 Title: {user_data['title']}")
    if 'note' in user_data and user_data['note']:
        lines.append(f"🗒️ Note: {user_data['note']}")
    if user_data.get('account'):
        lines.append(f"🏦 Account: {user_data['account']}")
        
    # Return joined lines, followed by a double newline if there's more text (which prompts will append)
    # But if is_final is True, we don't necessarily need prompt padding, though keeping it is harmless.
    return "\n".join(lines) + ("\n\n" if not is_final else "")

async def prompt_datetime(update, context, edit=False):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    context.user_data['datetime'] = now_str
    
    keyboard = [
        [InlineKeyboardButton(f"Use Current: {now_str}", callback_data="CURRENT_DATE")],
        [InlineKeyboardButton("Custom Date", callback_data="CUSTOM_DATE")],
        [InlineKeyboardButton("❌ Cancel", callback_data="CANCEL")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "When did this transaction happen?"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return DATETIME

async def prompt_txn_type(update, context, edit=False):
    keyboard = build_keyboard(["Income", "Expense"], add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Select the transaction type:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
    return TXN_TYPE

async def prompt_amount(update, context, edit=False):
    keyboard = build_keyboard([], add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Please type the exact amount (numbers only):"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
    return AMOUNT

async def prompt_category(update, context, edit=False):
    keyboard = build_keyboard(CONFIG['categories'], columns=3, add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Select a Category:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
    return CATEGORY

async def prompt_title(update, context, edit=False):
    keyboard = build_keyboard([], add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Please type a Title for this transaction:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
    return TITLE

async def prompt_note(update, context, edit=False):
    keyboard = [
        [InlineKeyboardButton("Skip Note", callback_data="SKIP_NOTE")],
        [InlineKeyboardButton("🔙 Back", callback_data="BACK"), InlineKeyboardButton("❌ Cancel", callback_data="CANCEL")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Please type a Note (description) or click Skip:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
    return NOTE

async def prompt_account(update, context, edit=False):
    keyboard = build_keyboard(CONFIG['accounts'], columns=2, add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Finally, select the Account:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
    return ACCOUNT

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm your Cashew Expense Tracker bot.\n"
        "Type /add or /a to start logging a transaction.\n"
        "Type /cancel at any time to abort."
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    return await prompt_datetime(update, context, edit=False)

async def handle_datetime_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "CANCEL":
        return await cancel(update, context)
        
    if data == "CURRENT_DATE":
        context.user_data['datetime_final'] = context.user_data['datetime']
        return await prompt_txn_type(update, context, edit=True)
    
    elif data == "CUSTOM_DATE" or data == "BACK_CALENDAR":
        text = get_summary(context.user_data) + "Please select a date:"
        await query.edit_message_text(text, reply_markup=create_calendar(), parse_mode="Markdown")
        return DATETIME

    elif data == "BACK_DATE_OPTIONS":
        return await prompt_datetime(update, context, edit=True)

    elif data.startswith("CAL-"):
        completed, date_str, new_markup = process_calendar_selection(query)
        if new_markup:
            text = get_summary(context.user_data) + "Please select a date:"
            await query.edit_message_text(text, reply_markup=new_markup, parse_mode="Markdown")
        elif completed:
            context.user_data['temp_date'] = date_str
            text = get_summary(context.user_data) + f"**{date_str}** selected.\n\nPlease select the hour:"
            await query.edit_message_text(text, reply_markup=create_time_keyboard(), parse_mode="Markdown")
        return DATETIME
        
    elif data.startswith("TIME-"):
        completed, time_str, new_markup = process_time_selection(query)
        if new_markup:
            text = get_summary(context.user_data) + f"**{context.user_data['temp_date']}** selected.\n\nPlease select the minute:"
            await query.edit_message_text(text, reply_markup=new_markup, parse_mode="Markdown")
        elif completed:
            context.user_data['datetime_final'] = f"{context.user_data['temp_date']} {time_str}"
            return await prompt_txn_type(update, context, edit=True)
        return DATETIME

    elif data == "IGNORE":
        return DATETIME

async def handle_custom_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['datetime_final'] = update.message.text.strip()
    return await prompt_txn_type(update, context, edit=False)

async def handle_txn_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "CANCEL":
        return await cancel(update, context)
    elif query.data == "BACK":
        context.user_data.pop('datetime_final', None)
        return await prompt_datetime(update, context, edit=True)
        
    context.user_data['type'] = query.data
    return await prompt_amount(update, context, edit=True)

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if context.user_data.get('type') == 'Expense' and amount > 0:
            amount = -amount
        elif context.user_data.get('type') == 'Income' and amount < 0:
            amount = abs(amount)
            
        context.user_data['amount'] = amount
        # Safe deletion of user input for cleaner chat, if possible. Not strict.
        try:
             await update.message.delete()
        except:
             pass
        return await prompt_category(update, context, edit=False)
    except ValueError:
        await update.message.reply_text("❌ Invalid amount! Please enter a valid number (e.g. 50 or 50.5).")
        return AMOUNT

async def handle_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "CANCEL":
        return await cancel(update, context)
    elif query.data == "BACK":
        context.user_data.pop('type', None)
        return await prompt_txn_type(update, context, edit=True)

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "CANCEL":
        return await cancel(update, context)
    elif query.data == "BACK":
        context.user_data.pop('amount', None)
        return await prompt_amount(update, context, edit=True)
        
    context.user_data['category'] = query.data
    return await prompt_title(update, context, edit=True)

async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text.strip()
    try:
         await update.message.delete()
    except:
         pass
    return await prompt_note(update, context, edit=False)

async def handle_title_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "CANCEL":
        return await cancel(update, context)
    elif query.data == "BACK":
        context.user_data.pop('category', None)
        return await prompt_category(update, context, edit=True)

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['note'] = update.message.text.strip()
    try:
         await update.message.delete()
    except:
         pass
    return await prompt_account(update, context, edit=False)

async def handle_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "CANCEL":
        return await cancel(update, context)
    elif query.data == "BACK":
        context.user_data.pop('title', None)
        return await prompt_title(update, context, edit=True)
    elif query.data == "SKIP_NOTE":
        context.user_data['note'] = ""
        return await prompt_account(update, context, edit=True)

async def save_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "CANCEL":
        return await cancel(update, context)
    elif query.data == "BACK":
        context.user_data.pop('note', None)
        return await prompt_note(update, context, edit=True)
        
    context.user_data['account'] = query.data
    await query.edit_message_text("🔄 Processing your transaction... ")
    
    try:
        data = context.user_data
        row = [
            data.get('datetime_final'),
            data.get('amount'),
            data.get('category'),
            data.get('title'),
            data.get('note', ''),
            data.get('account')
        ]
        
        loop = asyncio.get_event_loop()
        sheet = await loop.run_in_executor(None, get_sheet)
        await loop.run_in_executor(None, lambda: sheet.append_row(row))
        
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
        
        final_summary = get_summary(context.user_data, is_final=True)
        
        await query.edit_message_text(text=final_summary, reply_markup=reply_markup, parse_mode="Markdown")
        
    except FileNotFoundError as e:
         await query.edit_message_text(f"❌ Configuration Error: {str(e)}")
    except Exception as e:
        logger.error(f"Error saving transaction: {e}")
        await query.edit_message_text(f"❌ Failed to save transaction! Error: {str(e)}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Transaction cancelled.")
    elif update.callback_query:
        await update.callback_query.edit_message_text("❌ Transaction cancelled.")
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
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount),
                CallbackQueryHandler(handle_amount_callback)
            ],
            CATEGORY: [CallbackQueryHandler(handle_category)],
            TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title),
                CallbackQueryHandler(handle_title_callback)
            ],
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
