from flask import Flask, request
from dotenv import load_dotenv
import os

from telegram import Update
from telegram.ext import Application

# Importamo SAMO handlere
from telegram_bot import start, help_command, reset, handle_message


# ---------------- ENV ----------------

load_dotenv()

app = Flask(__name__)


@app.route("/")
def health():
    return "Bot alive 🚀"


# ---------------- TELEGRAM APP ----------------

telegram_app = None


@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    # Ako app nije inicijaliziran -> napravi ga
    if telegram_app is None:
        telegram_app = Application.builder()\
            .token(os.getenv("TELEGRAM_BOT_TOKEN"))\
            .build()

        # Dodaj handlere
        from telegram.ext import CommandHandler, MessageHandler, filters

        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("help", help_command))
        telegram_app.add_handler(CommandHandler("reset", reset))
        telegram_app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        await telegram_app.initialize()

    # Process update
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)

    return "ok"
