import os
from flask import Flask, request

from telegram import Update
from telegram.ext import Application

from telegram_bot import register_handlers

# -------------------------------------------------
# Flask app
# -------------------------------------------------

app = Flask(__name__)

telegram_app = None


@app.route("/")
def health():
    return "Bot alive"


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder().token(
            os.getenv("TELEGRAM_BOT_TOKEN")
        ).build()

        register_handlers(telegram_app)

        import asyncio
        asyncio.run(telegram_app.initialize())

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)

    import asyncio
    asyncio.run(telegram_app.process_update(update))

    return "ok"
