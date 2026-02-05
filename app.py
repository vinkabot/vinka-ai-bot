from flask import Flask, request
from dotenv import load_dotenv
from pathlib import Path
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

# Telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --------------------------------------------------
# ENV SETUP
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

app = Flask(__name__)

# --------------------------------------------------
# OPENAI
# --------------------------------------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)

# --------------------------------------------------
# INIT DATABASE
# --------------------------------------------------

def init_db():
    with db_conn.cursor() as cur:

        # Normal memory table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Vector table (bez vector tipa zasad)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vector_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            content TEXT,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    db_conn.commit()


init_db()

# --------------------------------------------------
# EMBEDDINGS
# --------------------------------------------------

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

# --------------------------------------------------
# TELEGRAM BOT HANDLERS
# --------------------------------------------------

async def start(update, context):
    await update.message.reply_text("Hello! Bot is alive 🚀")

async def help_command(update, context):
    await update.message.reply_text("Send me a message 🙂")

async def reset(update, context):
    await update.message.reply_text("Memory reset (not implemented yet)")

async def handle_message(update, context):
    text = update.message.text
    user_id = str(update.effective_user.id)

    # Save message in DB
    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_memory (user_id, role, content)
        VALUES (%s, %s, %s)
        """, (user_id, "user", text))
    db_conn.commit()

    # Simple echo for now
    await update.message.reply_text(f"You said: {text}")

# --------------------------------------------------
# TELEGRAM WEBHOOK
# --------------------------------------------------

telegram_app = None

@app.route("/")
def health():
    return "Bot alive"

@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder() \
            .token(os.getenv("TELEGRAM_BOT_TOKEN")) \
            .build()

        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("help", help_command))
        telegram_app.add_handler(CommandHandler("reset", reset))
        telegram_app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        await telegram_app.initialize()

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)

    return "ok"
