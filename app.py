import os
from flask import Flask, request
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application

load_dotenv()

app = Flask(__name__)

@app.route("/")
def health():
    return "Bot alive 🚀"

telegram_app = None

@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder() \
            .token(os.getenv("TELEGRAM_BOT_TOKEN")) \
            .build()

        from telegram_bot import register_handlers
        register_handlers(telegram_app)

        await telegram_app.initialize()

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)

    return "ok"
