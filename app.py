import os
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import Application

from telegram_bot import register_handlers


# -------------------------------------------------
# Flask app
# -------------------------------------------------

app = Flask(__name__)

telegram_app = None


# -------------------------------------------------
# Health check (Railway koristi ovo)
# -------------------------------------------------

@app.route("/")
def health():
    return "Bot alive"


# -------------------------------------------------
# Telegram webhook
# -------------------------------------------------

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    global telegram_app

    try:
        if telegram_app is None:
            telegram_app = (
                Application.builder()
                .token(os.getenv("TELEGRAM_BOT_TOKEN"))
                .build()
            )

            register_handlers(telegram_app)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(telegram_app.initialize())

        update = Update.de_json(request.get_json(force=True), telegram_app.bot)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.process_update(update))

        return "ok"

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return "error", 500


# -------------------------------------------------
# Local run
# -------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
