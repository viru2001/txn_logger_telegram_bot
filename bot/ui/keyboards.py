from telegram import InlineKeyboardButton, ReplyKeyboardRemove


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


async def remove_reply_keyboard(update, context):
    try:
        msg = await context.bot.send_message(update.effective_chat.id, "...", reply_markup=ReplyKeyboardRemove())
        await msg.delete()
    except Exception:
        pass


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
