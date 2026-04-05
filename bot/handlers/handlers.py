import datetime
import logging
import asyncio
from urllib.parse import urlencode

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import ContextTypes, ConversationHandler

from bot.constants import DATETIME, TXN_TYPE, AMOUNT, CATEGORY, TITLE, NOTE, ACCOUNT, CONFIG
from bot.ui.keyboards import build_keyboard, get_summary, remove_reply_keyboard
from bot.ui.date_time_picker import create_calendar, process_calendar_selection, create_time_keyboard, process_time_selection
from bot.services.sheets import get_sheet

logger = logging.getLogger(__name__)


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
            msg = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            msg = await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data['prompt_msg_id'] = msg.message_id
    return DATETIME


async def prompt_txn_type(update, context, edit=False):
    keyboard = build_keyboard(["Income", "Expense"], add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Select the transaction type:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        msg = await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data['prompt_msg_id'] = msg.message_id
    return TXN_TYPE


async def prompt_amount(update, context, edit=False):
    keyboard = build_keyboard([], add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Please type the exact amount (numbers only):"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        msg = await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data['prompt_msg_id'] = msg.message_id
    return AMOUNT


def _build_category_keyboard(categories):
    """ReplyKeyboard with all categories + Back/Cancel. No search button needed — inline search handles it."""
    keyboard = []
    for i in range(0, len(categories), 2):
        row = [KeyboardButton(cat) for cat in categories[i:i+2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton("🔙 Back"), KeyboardButton("❌ Cancel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


async def prompt_category(update, context, edit=False):
    categories = CONFIG['categories']
    chat_id = update.effective_chat.id

    # Clean up old search hint message if re-entering this step
    try: await context.bot.delete_message(chat_id, context.user_data.get('cat_search_msg_id'))
    except: pass

    if edit and update.callback_query:
        try: await update.callback_query.message.delete()
        except: pass

    # Main prompt with scrollable ReplyKeyboard
    text = get_summary(context.user_data) + "Select a Category 👇  _(or tap 🔍 below to search):_"
    if update.message:
        msg = await update.message.reply_text(text, reply_markup=_build_category_keyboard(categories), parse_mode="Markdown")
    else:
        msg = await context.bot.send_message(chat_id, text, reply_markup=_build_category_keyboard(categories), parse_mode="Markdown")
    context.user_data['prompt_msg_id'] = msg.message_id

    # Inline search button — tapping opens @bot in the text field for live autocomplete
    search_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Search Category (autocomplete)", switch_inline_query_current_chat="")
    ]])
    hint_msg = await context.bot.send_message(
        chat_id,
        "_Tip: Tap above to type and get instant suggestions_ ✨",
        reply_markup=search_markup,
        parse_mode="Markdown"
    )
    context.user_data['cat_search_msg_id'] = hint_msg.message_id
    return CATEGORY


async def prompt_title(update, context, edit=False):
    keyboard = build_keyboard([], add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Please type a Title for this transaction:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        msg = await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data['prompt_msg_id'] = msg.message_id
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
        msg = await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data['prompt_msg_id'] = msg.message_id
    return NOTE


async def prompt_account(update, context, edit=False):
    keyboard = build_keyboard(CONFIG['accounts'], columns=2, add_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = get_summary(context.user_data) + "Finally, select the Account:"
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        msg = await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data['prompt_msg_id'] = msg.message_id
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
    try: await update.message.delete()
    except: pass
    try: await context.bot.delete_message(update.effective_chat.id, context.user_data.get('prompt_msg_id'))
    except: pass
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
        try: await context.bot.delete_message(update.effective_chat.id, context.user_data.get('prompt_msg_id'))
        except: pass
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
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    if text == "❌ Cancel":
        await remove_reply_keyboard(update, context)
        try: await context.bot.delete_message(chat_id, context.user_data.get('cat_search_msg_id'))
        except: pass
        return await cancel(update, context)

    elif text == "🔙 Back":
        await remove_reply_keyboard(update, context)
        context.user_data.pop('amount', None)
        try: await update.message.delete()
        except: pass
        try: await context.bot.delete_message(chat_id, context.user_data.get('prompt_msg_id'))
        except: pass
        try: await context.bot.delete_message(chat_id, context.user_data.get('cat_search_msg_id'))
        except: pass
        return await prompt_amount(update, context, edit=False)

    if text not in CONFIG['categories']:
        await update.message.reply_text("❌ Please select a category from the menu.")
        return CATEGORY

    # ── Valid category selected ────────────────────────────────────────────
    context.user_data['category'] = text
    try: await update.message.delete()
    except: pass
    try: await context.bot.delete_message(chat_id, context.user_data.get('prompt_msg_id'))
    except: pass
    try: await context.bot.delete_message(chat_id, context.user_data.get('cat_search_msg_id'))
    except: pass

    await remove_reply_keyboard(update, context)
    return await prompt_title(update, context, edit=False)


async def category_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live autocomplete: fires as the user types after tapping the 🔍 Search button."""
    query = update.inline_query.query.strip().lower()
    categories = CONFIG['categories']

    # Show all categories when nothing typed yet, else filter
    if query:
        matches = [cat for cat in categories if query in cat.lower()]
    else:
        matches = categories  # show all as starting suggestions

    results = [
        InlineQueryResultArticle(
            id=str(i),
            title=cat,
            input_message_content=InputTextMessageContent(cat),
            description="Tap to select this category"
        )
        for i, cat in enumerate(matches[:20])  # Telegram inline max shown is ~15-20
    ]

    await update.inline_query.answer(results, cache_time=0, is_personal=True)


async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text.strip()
    try:
         await update.message.delete()
    except:
         pass
    try: await context.bot.delete_message(update.effective_chat.id, context.user_data.get('prompt_msg_id'))
    except: pass
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
    try: await context.bot.delete_message(update.effective_chat.id, context.user_data.get('prompt_msg_id'))
    except: pass
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
        if data.get('datetime_final'):
            # Cashew expects 'time' to be a full ISO 8601 string (e.g. YYYY-MM-DDTHH:MM:SS)
            iso_time = data.get('datetime_final').replace(' ', 'T') + ":00"
            params['time'] = iso_time
                
        if data.get('account'):
            params['account'] = data.get('account')
        if data.get('note'):
            params['notes'] = data.get('note')
            
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
