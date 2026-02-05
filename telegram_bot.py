import os
import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

from openai import OpenAI

# =========================
# OPENAI
# =========================

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# DATABASE
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)
db_conn.autocommit = True


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


init_db()

# =========================
# MEMORY HELPERS
# =========================

def save_memory(user_id, role, content):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_memory (user_id, role, content)
            VALUES (%s,%s,%s)
            """,
            (user_id, role, content)
        )


def load_memory(user_id, limit=10):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT role, content
            FROM user_memory
            WHERE user_id=%s
            ORDER BY id DESC
            LIMIT %s
            """,
            (user_id, limit)
        )
        rows = cur.fetchall()

    return list(reversed(rows))

# =========================
# TELEGRAM COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\nMogu zapamtiti stvari o tebi 💾"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_memory WHERE user_id=%s",
            (user_id,)
        )

    await update.message.reply_text("Memory resetiran ✅")


# =========================
# OPENAI CHAT
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.effective_user.id)
        user_text = update.message.text

        memory = load_memory(user_id)

        messages = [
            {"role": "system", "content": "Ti si prijateljski AI asistent."}
        ]

        messages.extend(memory)
        messages.append({"role": "user", "content": user_text})

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages
        )

        reply = response.choices[0].message.content

        save_memory(user_id, "user", user_text)
        save_memory(user_id, "assistant", reply)

        await update.message.reply_text(reply)

    except Exception as e:
        print("OPENAI ERROR:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")


# =========================
# REGISTER HANDLERS
# =========================

def setup_handlers(app):

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
