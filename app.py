import os
from flask import Flask, request

from telegram import Update
from telegram.ext import Application

from telegram_bot import setup_handlers

app = Flask(__name__)

telegram_app = None


@app.route("/")
def health():
    return "Bot alive 🚀"


@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder().token(
            os.getenv("TELEGRAM_BOT_TOKEN")
        ).build()

        setup_handlers(telegram_app)

        await telegram_app.initialize()

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)

    return "ok"
