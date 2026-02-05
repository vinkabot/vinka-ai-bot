from flask import Flask, request
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application

from telegram_bot import setup_handlers

load_dotenv()

app = Flask(__name__)

# ---------- TELEGRAM GLOBAL ----------
telegram_app = None


@app.route("/")
def health():
    return "Bot alive"


@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder().token(
            os.getenv("TELEGRAM_BOT_TOKEN")
        ).build()

        setup_handlers(telegram_app)

        await telegram_app.initialize()

    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)

    await telegram_app.process_update(update)

    return "ok"
