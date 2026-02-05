import os
from flask import Flask, request
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import Application

# --------------------
# ENV
# --------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# --------------------
# FLASK
# --------------------

app = Flask(__name__)

@app.route("/")
def health():
    return "Bot alive 🚀"

# --------------------
# DB
# --------------------

db_conn = None

def get_db():
    global db_conn
    if db_conn is None:
        db_conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )
        db_conn.autocommit = True
    return db_conn

def init_db():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        print("DB READY")
    except Exception as e:
        print("DB INIT ERROR:", e)

init_db()

# --------------------
# TELEGRAM APP
# --------------------

telegram_app = None

def get_telegram_app():
    global telegram_app
    if telegram_app is None:
        telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

        from telegram_bot import register_handlers
        register_handlers(telegram_app)

    return telegram_app

# --------------------
# WEBHOOK
# --------------------

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    try:
        app_tg = get_telegram_app()

        update = Update.de_json(
            request.get_json(force=True),
            app_tg.bot
        )

        import asyncio
        asyncio.run(app_tg.process_update(update))

        return "ok"

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return "error"

# --------------------
# LOCAL RUN
# --------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
