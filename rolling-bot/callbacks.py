from telegram import Update
from telegram.ext import ContextTypes
from handlers.commands import find_active_duel, process_shot, finish_duel

async def giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Функция розыгрышей в разработке")

async def duel_shoot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duel_id = query.data.split('_')[2]
    duel = context.bot_data.get(f'duel_{duel_id}')
    if not duel or duel.get('finished'):
        await query.edit_message_text("Дуэль завершена")
        return
    user = query.from_user
    if user.id != duel['next_player']:
        await query.answer("Не ваш ход", show_alert=True)
        return
    await process_shot(duel['chat_id'], user, context, duel_id, duel)

async def duel_end_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duel_id = query.data.split('_')[2]
    duel = context.bot_data.get(f'duel_{duel_id}')
    if duel:
        duel['finished'] = True
        await query.edit_message_text("⏹ Дуэль остановлена")
        del context.bot_data[f'duel_{duel_id}']