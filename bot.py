import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Ты написал в POIZON LAB.\n"
        "Отправь ссылку или скрин товара — мы подберём цену и размер 👟🧥"
    )

async def forward_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != OWNER_ID:
        await context.bot.forward_message(
            chat_id=OWNER_ID,
            from_chat
