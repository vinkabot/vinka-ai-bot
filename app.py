from flask import Flask, request
from dotenv import load_dotenv
from pathlib import Path
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

from openai import OpenAI

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)

# -----------------------------
# ENV + BASE
# -----------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")

# -----------------------------
# APP + CLIENTS
# -----------------------------

app = Flask(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# DATABASE
# -----------------------------

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)

def init_db():
    with db_conn.cursor() as cur:

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    db_conn.commit()

init_db()

# -----------------------------
# MEMORY HELPERS
# -----------------------------

def save_message(user_id, role, content):
    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_memory (user_id, role, content)
        VALUES (%s, %s, %s)
        """, (user_id, role, content))
    db_conn.commit()

def get_memory(user_id, limit=12):
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT role, content
        FROM user_memory
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT %s
        """, (user_id, limit))

        rows = cur.fetchall()

    rows.reverse()
    return rows

# -----------------------------
# TELEGRAM HANDLERS
# -----------------------------

async def start(update, context):
    await update.message.reply_text("Bot alive 🚀")

async def help_command(update, context):
    await update.message.reply_text("Send me message and I remember context.")

async def handle_message(update, context):

    user_id = str(update.effective_user.id)
    text = update.message.text

    save_message(user_id, "user", text)

    memory = get_memory(user_id)

    messages = [
        {"role": "system", "content": "You are helpful assistant."}
    ] + memory

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    reply = response.choices[0].message.content

    save_message(user_id, "assistant", reply)

    await update.message.reply_text(reply)

# -----------------------------
# TELEGRAM APP
# -----------------------------

telegram_app = None

# -----------------------------
# WEBHOOK ROUTE
# -----------------------------

@app.route("/")
def health():
    return "Bot alive"

@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder().token(
            TELEGRAM_BOT_TOKEN
        ).build()

        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("help", help_command))
        telegram_app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        await telegram_app.initialize()

    update = Update.de_json(
        request.get_json(force=True),
        telegram_app.bot
    )

    await telegram_app.process_update(update)

    return "ok"
