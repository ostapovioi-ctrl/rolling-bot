import os
import asyncio
from telegram.ext import Application

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    print("Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
