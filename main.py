#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
import os
import json
import random
import secrets
import re
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from telegram.constants import MessageEntityType, ChatMemberStatus

# ========== НАСТРОЙКИ ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
GOOGLE_SHEETS_CREDS = os.environ.get("GOOGLE_SHEETS_CREDS")
SPREADSHEET_NAME = "TelegramBotData"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

# ========== GOOGLE SHEETS ==========
def get_spreadsheet():
    if not GOOGLE_SHEETS_CREDS:
        return None
    try:
        creds_dict = json.loads(GOOGLE_SHEETS_CREDS)
        creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc = gspread.authorize(creds)
        try:
            return gc.open(SPREADSHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = gc.create(SPREADSHEET_NAME)
            sh.share(None, perm_type='anyone', role='writer')
            return sh
    except Exception as e:
        logger.error(f"Google Sheets error: {e}")
        return None

spreadsheet = get_spreadsheet()

if spreadsheet:
    sheets = {
        "Users": ["user_id", "username", "first_name", "role", "registered_at"],
        "Giveaways": ["giveaway_id", "chat_id", "message_id", "slots_total", "slots_taken", "winners_count", "prizes_data", "conditions", "status", "created_at"],
        "Participants": ["giveaway_id", "user_id", "username", "slot_number", "registered_at"],
        "Sponsors": ["sponsor_id", "name", "username", "logo_file_id", "added_by"],
        "CustomEmojis": ["alias", "custom_emoji_id", "added_by", "added_at"],
        "UserStats": ["user_id", "shots_total", "shots_made", "last_shot_at"],
        "BotChats": ["chat_id", "title", "username", "type", "added_by"],
        "Duels": ["duel_id", "game_type", "challenger_id", "opponent_id", "status", "score_challenger", "score_opponent", "created_at"],
        "ShotLimits": ["user_id", "date_hour", "shots_count"]
    }
    for name, headers in sheets.items():
        try:
            spreadsheet.worksheet(name)
        except:
            ws = spreadsheet.add_worksheet(title=name, rows="100", cols="20")
            ws.append_row(headers)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def get_user_role(user_id: int) -> str:
    if user_id == OWNER_ID:
        return "owner"
    if not spreadsheet:
        return "user"
    try:
        users = spreadsheet.worksheet("Users")
        cell = users.find(str(user_id), in_column=1)
        if cell:
            return users.row_values(cell.row)[3]
    except:
        pass
    return "user"

async def register_user(user_id, username, first_name):
    if not spreadsheet:
        return
    try:
        users = spreadsheet.worksheet("Users")
        if not users.find(str(user_id), in_column=1):
            users.append_row([str(user_id), username or "", first_name or "", "user", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    except:
        pass

def generate_giveaway_id():
    return secrets.token_hex(8)

def generate_progress_bar(filled, total, style="█▒"):
    if style == "█▒":
        return f"{'█' * filled}{'▒' * (total - filled)}"
    return f"{filled}/{total}"

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await register_user(user.id, user.username, user.first_name)
    role = await get_user_role(user.id)
    kb = [[KeyboardButton("/roll"), KeyboardButton("/dice")]]
    if role in ("owner", "admin"):
        kb.append([KeyboardButton("/giveaway")])
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}! Роль: {role}",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    try:
        if args:
            a, b = int(args[0]), int(args[1]) if len(args) > 1 else int(args[0])
            res = random.randint(min(a, b), max(a, b))
        else:
            res = random.randint(1, 100)
        await update.message.reply_text(f"🎲 {res}")
    except:
        await update.message.reply_text("Использование: /roll [min] [max]")

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_dice(emoji="🎲")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Команды: /start, /roll, /dice, /giveaway (админ)")

# ========== ЗАПУСК ==========
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("dice", dice))
    app.add_handler(CommandHandler("help", help_cmd))
    logger.info("Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
