import os
import logging
from telegram import Update
from telegram.ext import ApplicationHandlerStop

logger = logging.getLogger(__name__)

async def check_allowlist(update: Update, context):
    """
    Middleware function that checks if the incoming update is from an allowed user.
    If ALLOWED_TELEGRAM_IDS environment variable is present, it will immediately halt
    handling if the user is missing from that list.
    """
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    allowed_ids_str = os.getenv("ALLOWED_TELEGRAM_IDS", "")
    
    if not allowed_ids_str:
        return # Missing or empty allowlist allows anyone.

    allowed_ids = [int(x.strip()) for x in allowed_ids_str.split(",") if x.strip().isdigit()]
    
    if allowed_ids and user_id not in allowed_ids:
        logger.warning(f"Unauthorized access attempt by user_id: {user_id}")
        if update.message:
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
        elif update.callback_query:
            await update.callback_query.answer("⛔ You are not authorized.", show_alert=True)
        raise ApplicationHandlerStop()
