import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8716534172:AAG36_kS3WAJ5GjPMRzsUUQ9XITRHXAqaFw")
OWNER_ID = int(os.environ.get("OWNER_ID", "8789941675"))
GOOGLE_SHEETS_CREDS_JSON = os.environ.get("GOOGLE_SHEETS_CREDS", "{}")
SPREADSHEET_NAME = os.environ.get("SPREADSHEET_NAME", "TelegramBotData")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

_spreadsheet = None

def get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet
    try:
        creds_dict = json.loads(GOOGLE_SHEETS_CREDS_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets"
        ])
        gc = gspread.authorize(creds)
        try:
            _spreadsheet = gc.open(SPREADSHEET_NAME)
            logger.info(f"Таблица '{SPREADSHEET_NAME}' найдена.")
        except gspread.SpreadsheetNotFound:
            _spreadsheet = gc.create(SPREADSHEET_NAME)
            _spreadsheet.share(None, perm_type='anyone', role='writer')
            logger.info(f"Таблица '{SPREADSHEET_NAME}' создана.")
        return _spreadsheet
    except Exception as e:
        logger.error(f"Ошибка подключения к Google Sheets: {e}")
        raise

REQUIRED_SHEETS = {
    "Users": ["user_id", "username", "first_name", "role", "registered_at"],
    "Giveaways": ["giveaway_id", "chat_id", "message_id", "slots_total", "slots_taken", "winners_count", "prizes_data", "conditions", "status", "created_at", "sponsors_data"],
    "Participants": ["giveaway_id", "user_id", "username", "slot_number", "registered_at", "confirmed"],
    "Sponsors": ["sponsor_id", "name", "username", "logo_file_id", "added_by", "total_giveaways"],
    "CustomEmojis": ["alias", "custom_emoji_id", "added_by", "added_at"],
    "GiveawayWinners": ["giveaway_id", "user_id", "slot_number", "prize_description", "status", "selected_at"],
    "UserStats": ["user_id", "shots_total", "shots_made", "last_shot_at"],
    "BotChats": ["chat_id", "title", "username", "type", "added_by", "added_at"],
    "Duels": ["duel_id", "game_type", "challenger_id", "opponent_id", "status", "shots_count", "score_challenger", "score_opponent", "created_at"],
    "ShotLimits": ["user_id", "date_hour", "shots_count"]
}