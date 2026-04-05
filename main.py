import os
import logging
import asyncio
from dotenv import load_dotenv

from aiohttp import web

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    TypeHandler,
    filters,
)

from bot.constants import DATETIME, TXN_TYPE, AMOUNT, CATEGORY, TITLE, NOTE, ACCOUNT
from bot.auth.auth import check_allowlist
from bot.handlers.handlers import (
    start, add_start, cancel,
    handle_datetime_callback, handle_custom_datetime,
    handle_txn_type,
    handle_amount, handle_amount_callback,
    handle_category,
    handle_title, handle_title_callback,
    handle_note, handle_note_callback,
    save_transaction,
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


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
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
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

    application.add_handler(TypeHandler(Update, check_allowlist), group=-1)
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
