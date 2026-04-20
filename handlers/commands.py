import random
import secrets
import asyncio
import json
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import MessageEntityType, ChatMemberStatus
from config import OWNER_ID, get_spreadsheet
from db import (
    get_user_role, register_user, check_user_subscription, is_user_activated_bot,
    check_shot_limit, spend_shot_limit, save_bot_chat, generate_giveaway_id,
    get_chat_id_from_username
)
from utils import generate_progress_bar

WIN_SCORE = 7
GAME_CONFIG = {
    'basketball': {'emoji': '🏀', 'hit_values': (4, 5), 'name': 'Баскетбол'},
    'darts': {'emoji': '🎯', 'hit_values': (6,), 'name': 'Дартс'},
    'football': {'emoji': '⚽', 'hit_values': (4, 5), 'name': 'Футбол'},
    'dice': {'emoji': '🎲', 'hit_values': (6,), 'name': 'Кубик'}
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    role = await get_user_role(user.id)
    keyboard = []
    if role in ["owner", "admin"]:
        keyboard.append([KeyboardButton("📢 Создать розыгрыш"), KeyboardButton("📋 Мои розыгрыши")])
        keyboard.append([KeyboardButton("🤝 Спонсоры"), KeyboardButton("😊 Эмодзи")])
    else:
        keyboard.append([KeyboardButton("🎁 Участвовать"), KeyboardButton("📊 Моя статистика")])
    keyboard.append([KeyboardButton("ℹ️ Помощь")])
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}! Твоя роль: {role}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    role = await get_user_role(user_id)
    if text == "📢 Создать розыгрыш" and role in ["owner", "admin"]:
        from handlers.conversations import start_giveaway_creation
        return await start_giveaway_creation(update, context)
    elif text == "😊 Эмодзи":
        await update.message.reply_text("Отправьте мне кастомный эмодзи, чтобы сохранить его.")
    elif text == "ℹ️ Помощь":
        await update.message.reply_text(
            "🎲 /roll [min] [max] — случайное число\n"
            "🎲 /dice — кубик\n"
            "🏀 /shot @user — баскетбол\n"
            "🎯 /darts @user — дартс\n"
            "⚽ /football @user — футбол\n"
            "🎲 /dice_duel @user — дуэль на кубиках\n"
            "/shoot — бросок в дуэли"
        )
    else:
        await update.message.reply_text("Используйте кнопки меню.")

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.args:
            min_v = int(context.args[0])
            max_v = int(context.args[1]) if len(context.args) > 1 else min_v
            result = random.randint(min(min_v, max_v), max(min_v, max_v))
        else:
            result = random.randint(1, 100)
        await update.message.reply_text(f"🎲 {result}")
    except:
        await update.message.reply_text("/roll [min] [max]")

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice(emoji="🎲")

async def find_user_id(context, username):
    sh = get_spreadsheet()
    users = sh.worksheet("Users")
    records = users.get_all_records()
    for rec in records:
        if rec.get('username', '').lower() == username.lower():
            return int(rec['user_id'])
    try:
        chat = await context.bot.get_chat(f"@{username}")
        return chat.id
    except:
        return None

async def start_duel(update, context, game_type, opponent_username):
    user = update.effective_user
    chat_id = update.effective_chat.id
    opponent_id = await find_user_id(context, opponent_username)
    if not opponent_id:
        await update.message.reply_text(f"❌ @{opponent_username} не найден")
        return
    if opponent_id == user.id:
        await update.message.reply_text("❌ Нельзя вызвать себя")
        return
    if not await check_shot_limit(user.id) or not await check_shot_limit(opponent_id):
        await update.message.reply_text("⏳ Лимит бросков исчерпан")
        return

    duel_id = secrets.token_hex(6)
    duel_data = {
        'duel_id': duel_id, 'game_type': game_type,
        'challenger': user.id, 'opponent': opponent_id,
        'score': {str(user.id): 0, str(opponent_id): 0},
        'next_player': user.id, 'chat_id': chat_id, 'message_id': None,
        'finished': False, 'shots_count': 0
    }
    context.bot_data[f'duel_{duel_id}'] = duel_data
    config = GAME_CONFIG[game_type]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{config['emoji']} Бросить", callback_data=f"duel_shoot_{duel_id}")],
        [InlineKeyboardButton("🏁 Завершить", callback_data=f"duel_end_{duel_id}")]
    ])
    msg = await update.message.reply_text(
        f"{config['emoji']} {config['name']} до {WIN_SCORE} очков\n"
        f"@{user.username} VS @{opponent_username}\n"
        f"Первым бросает @{user.username}",
        reply_markup=keyboard
    )
    duel_data['message_id'] = msg.message_id

async def shot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/shot @username")
        return
    raw = context.args[0]
    opp = raw.lstrip('@').split('@')[0]
    await start_duel(update, context, 'basketball', opp)

async def darts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/darts @username")
        return
    opp = context.args[0].lstrip('@').split('@')[0]
    await start_duel(update, context, 'darts', opp)

async def football(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/football @username")
        return
    opp = context.args[0].lstrip('@').split('@')[0]
    await start_duel(update, context, 'football', opp)

async def dice_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("/dice_duel @username")
        return
    opp = context.args[0].lstrip('@').split('@')[0]
    await start_duel(update, context, 'dice', opp)

def find_active_duel(context, user_id, check_turn=False):
    for key, duel in context.bot_data.items():
        if key.startswith('duel_') and not duel.get('finished'):
            if user_id in (duel['challenger'], duel['opponent']):
                if check_turn and duel['next_player'] != user_id:
                    continue
                return duel, key.split('_')[1]
    return None, None

async def process_shot(chat_id, user, context, duel_id, duel, dice_message=None):
    config = GAME_CONFIG[duel['game_type']]
    if not dice_message:
        dice_msg = await context.bot.send_dice(chat_id, emoji=config['emoji'])
        await asyncio.sleep(3)
    else:
        dice_msg = dice_message

    made = dice_msg.dice.value in config['hit_values']
    if made:
        duel['score'][str(user.id)] += 1
        result = "✅ Попадание!"
    else:
        result = "❌ Мимо"

    duel['shots_count'] += 1
    await spend_shot_limit(user.id, 1)

    winner_id = None
    if duel['score'][str(user.id)] >= WIN_SCORE:
        winner_id = user.id
    else:
        other = duel['opponent'] if user.id == duel['challenger'] else duel['challenger']
        if duel['score'][str(other)] >= WIN_SCORE:
            winner_id = other

    if winner_id:
        await finish_duel(context, duel_id, duel, winner_id)
        return

    duel['next_player'] = duel['opponent'] if user.id == duel['challenger'] else duel['challenger']
    next_user = await context.bot.get_chat(duel['next_player'])
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{config['emoji']} Бросить", callback_data=f"duel_shoot_{duel_id}")],
        [InlineKeyboardButton("🏁 Завершить", callback_data=f"duel_end_{duel_id}")]
    ])
    await context.bot.edit_message_text(
        chat_id=chat_id, message_id=duel['message_id'],
        text=(
            f"{config['emoji']} {config['name']} до {WIN_SCORE}\n"
            f"Счёт: {duel['score'][str(duel['challenger'])]} : {duel['score'][str(duel['opponent'])]}\n"
            f"Бросает @{next_user.username}\n{result}"
        ),
        reply_markup=keyboard
    )

async def finish_duel(context, duel_id, duel, winner_id):
    duel['finished'] = True
    winner = await context.bot.get_chat(winner_id)
    loser_id = duel['opponent'] if winner_id == duel['challenger'] else duel['challenger']
    await context.bot.edit_message_reply_markup(
        chat_id=duel['chat_id'], message_id=duel['message_id'], reply_markup=None
    )
    await context.bot.send_message(
        duel['chat_id'],
        f"🏆 Победитель: @{winner.username} со счётом {duel['score'][str(winner_id)]}:{duel['score'][str(loser_id)]}"
    )
    del context.bot_data[f'duel_{duel_id}']

async def shoot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    duel, duel_id = find_active_duel(context, user.id, check_turn=True)
    if not duel:
        await update.message.reply_text("❌ Не ваша очередь или нет дуэли")
        return
    await process_shot(update.effective_chat.id, user, context, duel_id, duel)

async def handle_duel_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.dice:
        return
    emoji = update.message.dice.emoji
    game_type = None
    for gt, cfg in GAME_CONFIG.items():
        if cfg['emoji'] == emoji:
            game_type = gt
            break
    if not game_type:
        return
    user = update.effective_user
    duel, duel_id = find_active_duel(context, user.id, game_type=game_type, check_turn=True)
    if not duel:
        return
    await process_shot(update.effective_chat.id, user, context, duel_id, duel, dice_message=update.message)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Админ-панель в разработке")

async def list_custom_emojis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sh = get_spreadsheet()
    em = sh.worksheet("CustomEmojis")
    records = em.get_all_records()
    if not records:
        await update.message.reply_text("Нет сохранённых эмодзи")
        return
    text = "Сохранённые эмодзи:\n"
    for r in records[:20]:
        text += f":{r['alias']}: — `{r['custom_emoji_id']}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def save_custom_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = await get_user_role(user_id)
    if role not in ["owner", "admin"]:
        return
    emoji_id = None
    for entity in update.message.entities:
        if entity.type == MessageEntityType.CUSTOM_EMOJI and entity.custom_emoji_id:
            emoji_id = entity.custom_emoji_id
            break
    if not emoji_id:
        await update.message.reply_text("Это не кастомный эмодзи")
        return
    context.user_data['temp_emoji_id'] = emoji_id
    await update.message.reply_text("Введите alias (например, fire):")
    context.user_data['awaiting_emoji_alias'] = True

async def handle_emoji_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_emoji_alias'):
        return
    alias = update.message.text.strip().lower()
    emoji_id = context.user_data.pop('temp_emoji_id')
    user = update.effective_user
    sh = get_spreadsheet()
    em = sh.worksheet("CustomEmojis")
    em.append_row([alias, emoji_id, str(user.id), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    await update.message.reply_text(f"✅ Эмодзи сохранён как :{alias}:")
    context.user_data['awaiting_emoji_alias'] = False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено")
    return ConversationHandler.END
