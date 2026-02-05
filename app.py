import os
import json
from flask import Flask, request
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from openai import OpenAI


# --------------------------------------------------
# ENV
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")


# --------------------------------------------------
# CLIENTS
# --------------------------------------------------

client = OpenAI(api_key=OPENAI_API_KEY)

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)
db_conn.autocommit = True


# --------------------------------------------------
# FLASK
# --------------------------------------------------

app = Flask(__name__)


@app.route("/")
def health():
    return "Bot alive 🚀"


# --------------------------------------------------
# DB INIT
# --------------------------------------------------

def init_db():
    with db_conn.cursor() as cur:

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_facts (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            fact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


init_db()


# --------------------------------------------------
# MEMORY FUNCTIONS
# --------------------------------------------------

def save_message(user_id, role, content):
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_memory (user_id, role, content) VALUES (%s, %s, %s)",
            (user_id, role, content)
        )


def get_memory(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT role, content
            FROM user_memory
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 10
        """, (user_id,))
        return cur.fetchall()


# --------------------------------------------------
# FACTS
# --------------------------------------------------

def save_fact(user_id, fact):
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_facts (user_id, fact) VALUES (%s, %s)",
            (user_id, fact)
        )


def get_facts(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT fact FROM user_facts
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT 10
        """, (user_id,))
        return [r["fact"] for r in cur.fetchall()]


# --------------------------------------------------
# SIMPLE FACT DETECTION
# --------------------------------------------------

def detect_fact(text):
    t = text.lower()

    if "volim" in t:
        return text

    if "moje ime je" in t:
        return text

    return None


# --------------------------------------------------
# AI CHAT
# --------------------------------------------------

def chat_with_ai(user_id, text):

    save_message(user_id, "user", text)

    fact = detect_fact(text)
    if fact:
        save_fact(user_id, fact)

    memory = get_memory(user_id)
    facts = get_facts(user_id)

    messages = []

    if facts:
        messages.append({
            "role": "system",
            "content": "User facts: " + "; ".join(facts)
        })

    for m in reversed(memory):
        messages.append({
            "role": m["role"],
            "content": m["content"]
        })

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages
    )

    reply = response.choices[0].message.content

    save_message(user_id, "assistant", reply)

    return reply


# --------------------------------------------------
# TELEGRAM WEBHOOK
# --------------------------------------------------

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram_bot import start, help_command, reset, handle_message

telegram_app = None


@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

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
