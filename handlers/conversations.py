import re
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from config import get_spreadsheet
from db import save_bot_chat, generate_giveaway_id, get_chat_id_from_username
from utils import generate_progress_bar
from telegram.constants import ChatMemberStatus

SELECT_CHAT, ENTER_DESCRIPTION, ADD_MEDIA, SET_SLOTS, SET_WINNERS, SET_PRIZES, SET_CONDITIONS, PREVIEW = range(8)

async def start_giveaway_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sh = get_spreadsheet()
    chats = sh.worksheet("BotChats").get_all_records()
    if not chats:
        await update.message.reply_text("Нет сохранённых чатов. Добавьте бота админом в канал.")
        return ConversationHandler.END
    keyboard = []
    for c in chats[:15]:
        keyboard.append([InlineKeyboardButton(c['title'], callback_data=f"saved_chat_{c['chat_id']}")])
    keyboard.append([InlineKeyboardButton("Другой способ", callback_data="other_method")])
    await update.message.reply_text("Выберите чат:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_CHAT

async def select_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("saved_chat_"):
        chat_id = int(data.split("_")[2])
        context.user_data['giveaway_chat_id'] = chat_id
        await query.edit_message_text("✅ Чат выбран. Введите текст поста:")
        return ENTER_DESCRIPTION
    elif data == "other_method":
        await query.edit_message_text("Перешлите сообщение из чата или введите @username:")
        return SELECT_CHAT

async def select_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = None
    if update.message.forward_from_chat:
        chat_id = update.message.forward_from_chat.id
    elif update.message.text:
        chat_id = await get_chat_id_from_username(context.bot, update.message.text)
    if not chat_id:
        await update.message.reply_text("Не удалось определить чат")
        return SELECT_CHAT
    context.user_data['giveaway_chat_id'] = chat_id
    await save_bot_chat(chat_id, "", "", "channel", update.effective_user.id)
    await update.message.reply_text("✅ Чат выбран. Введите текст поста:")
    return ENTER_DESCRIPTION

async def enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['giveaway_text'] = update.message.text
    await update.message.reply_text("Прикрепите медиа или /skip")
    return ADD_MEDIA

async def add_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['giveaway_media'] = update.message.photo[-1].file_id
    elif update.message.video:
        context.user_data['giveaway_media'] = update.message.video.file_id
    elif update.message.text == '/skip':
        context.user_data['giveaway_media'] = None
    else:
        await update.message.reply_text("Отправьте медиа или /skip")
        return ADD_MEDIA
    await update.message.reply_text("Количество слотов (1-100):")
    return SET_SLOTS

async def set_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        slots = int(update.message.text)
        if not 1 <= slots <= 100:
            raise ValueError
    except:
        await update.message.reply_text("Число от 1 до 100")
        return SET_SLOTS
    context.user_data['slots'] = slots
    await update.message.reply_text(f"Количество победителей (1-{slots}):")
    return SET_WINNERS

async def set_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        winners = int(update.message.text)
        if not 1 <= winners <= context.user_data['slots']:
            raise ValueError
    except:
        await update.message.reply_text(f"От 1 до {context.user_data['slots']}")
        return SET_WINNERS
    context.user_data['winners'] = winners
    await update.message.reply_text("Призы через две пустые строки (Enter Enter):")
    return SET_PRIZES

async def set_prizes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    prizes = [p.strip() for p in text.split('\n\n') if p.strip()]
    if not prizes:
        await update.message.reply_text("Введите хотя бы один приз")
        return SET_PRIZES
    context.user_data['prizes'] = prizes
    await update.message.reply_text("Обязательные каналы (@username через пробел) или /skip:")
    return SET_CONDITIONS

async def set_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == '/skip':
        context.user_data['required_channels'] = []
    else:
        context.user_data['required_channels'] = re.findall(r'@\w+', update.message.text)
    # Предпросмотр
    text = context.user_data['giveaway_text']
    slots = context.user_data['slots']
    prizes = context.user_data['prizes']
    preview = f"*ПРЕДПРОСМОТР*\n\n{text}\n\n*Призы:*\n"
    for i, p in enumerate(prizes, 1):
        preview += f"{i}. {p}\n"
    preview += f"\nСлотов: {slots} | Победителей: {context.user_data['winners']}\n"
    preview += f"Заполнено: {generate_progress_bar(0, slots)} 0/{slots}\n\nСписок:\n"
    for i in range(1, slots+1):
        preview += f"{i}. ➖ Свободно\n"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Опубликовать", callback_data="publish_giveaway")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_giveaway")]
    ])
    await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=keyboard)
    return PREVIEW

async def preview_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "publish_giveaway":
        await publish_giveaway(query, context)
    else:
        await query.edit_message_text("Отменено")
    return ConversationHandler.END

async def publish_giveaway(query, context):
    data = context.user_data
    chat_id = data['giveaway_chat_id']
    text = data['giveaway_text']
    slots = data['slots']
    winners = data['winners']
    prizes = data['prizes']
    channels = data.get('required_channels', [])
    media = data.get('giveaway_media')
    giveaway_id = generate_giveaway_id()

    post_text = f"{text}\n\n*Призы:*\n"
    for i, p in enumerate(prizes, 1):
        post_text += f"{i}. {p}\n"
    post_text += f"\nЗаполнено: {generate_progress_bar(0, slots)} 0/{slots}\n\nСписок:\n"
    for i in range(1, slots+1):
        post_text += f"{i}. ➖ Свободно\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Записаться", callback_data=f"join_{giveaway_id}"),
         InlineKeyboardButton("📋 Проверить", callback_data=f"check_{giveaway_id}")]
    ])
    try:
        if media:
            msg = await context.bot.send_photo(chat_id, media, caption=post_text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            msg = await context.bot.send_message(chat_id, post_text, reply_markup=keyboard, parse_mode="Markdown")
        await context.bot.pin_chat_message(chat_id, msg.message_id)
    except Exception as e:
        await query.edit_message_text(f"Ошибка: {e}")
        return ConversationHandler.END

    sh = get_spreadsheet()
    sh.worksheet("Giveaways").append_row([
        giveaway_id, str(chat_id), str(msg.message_id), slots, 0, winners,
        json.dumps(prizes), json.dumps(channels), "active",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""
    ])
    await query.edit_message_text("✅ Розыгрыш опубликован!")

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("📢 Создать розыгрыш"), start_giveaway_creation)],
    states={
        SELECT_CHAT: [
            CallbackQueryHandler(select_chat_callback, pattern='^(saved_chat_|other_method)'),
            MessageHandler(filters.ALL, select_chat)
        ],
        ENTER_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description)],
        ADD_MEDIA: [MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & filters.Regex('^/skip$')), add_media)],
        SET_SLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_slots)],
        SET_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_winners)],
        SET_PRIZES: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_prizes)],
        SET_CONDITIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_conditions)],
        PREVIEW: [CallbackQueryHandler(preview_callback, pattern='^(publish_giveaway|cancel_giveaway)')],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
)