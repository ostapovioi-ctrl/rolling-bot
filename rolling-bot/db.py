import json
import secrets
from datetime import datetime
from config import get_spreadsheet, REQUIRED_SHEETS, OWNER_ID
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus

def init_sheets():
    sh = get_spreadsheet()
    for sheet_name, headers in REQUIRED_SHEETS.items():
        try:
            sh.worksheet(sheet_name)
        except:
            ws = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
            ws.append_row(headers)

async def get_user_role(user_id: int) -> str:
    if user_id == OWNER_ID:
        return "owner"
    try:
        sh = get_spreadsheet()
        users = sh.worksheet("Users")
        cell = users.find(str(user_id), in_column=1)
        if cell:
            row = users.row_values(cell.row)
            return row[3]
    except:
        pass
    return "user"

async def register_user(user_id, username, first_name):
    try:
        sh = get_spreadsheet()
        users = sh.worksheet("Users")
        if not users.find(str(user_id), in_column=1):
            users.append_row([
                str(user_id),
                username or "",
                first_name or "",
                "user",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])
    except Exception as e:
        pass

def generate_giveaway_id():
    return secrets.token_hex(8)

async def check_user_subscription(bot, user_id, channel_usernames):
    if not channel_usernames:
        return True, []
    not_subscribed = []
    for channel in channel_usernames:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                not_subscribed.append(channel)
        except:
            not_subscribed.append(channel)
    return len(not_subscribed) == 0, not_subscribed

async def save_bot_chat(chat_id, title, username, chat_type, added_by):
    try:
        sh = get_spreadsheet()
        chats = sh.worksheet("BotChats")
        if not chats.find(str(chat_id), in_column=1):
            chats.append_row([
                str(chat_id), title or "", username or "",
                chat_type, str(added_by), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])
    except:
        pass

async def check_shot_limit(user_id: int, max_shots: int = 15) -> bool:
    now = datetime.now()
    hour_key = now.strftime("%Y-%m-%d %H")
    try:
        sh = get_spreadsheet()
        limits = sh.worksheet("ShotLimits")
        cell = limits.find(str(user_id), in_column=1)
        if cell:
            row = limits.row_values(cell.row)
            if row[1] == hour_key:
                return int(row[2]) < max_shots
        return True
    except:
        return True

async def spend_shot_limit(user_id: int, shots: int = 1):
    now = datetime.now()
    hour_key = now.strftime("%Y-%m-%d %H")
    try:
        sh = get_spreadsheet()
        limits = sh.worksheet("ShotLimits")
        cell = limits.find(str(user_id), in_column=1)
        if cell:
            row = limits.row_values(cell.row)
            if row[1] == hour_key:
                current = int(row[2])
                limits.update(f"C{cell.row}", current + shots)
            else:
                limits.update(f"B{cell.row}:C{cell.row}", [[hour_key, shots]])
        else:
            limits.append_row([str(user_id), hour_key, shots])
    except Exception as e:
        pass

async def is_user_activated_bot(user_id, context):
    try:
        await context.bot.send_chat_action(chat_id=user_id, action="typing")
        return True
    except:
        return False

async def get_chat_id_from_username(bot, username: str):
    try:
        clean = username.strip().replace('@', '')
        if not clean:
            return None
        chat = await bot.get_chat(f"@{clean}")
        return chat.id
    except:
        return None