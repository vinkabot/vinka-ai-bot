import os
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor

# --------------------
# CLIENT
# --------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL")

# --------------------
# DB HELPERS
# --------------------

def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )

def save_memory(user_id, role, content):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_memory (user_id, role, content)
                VALUES (%s, %s, %s)
            """, (user_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print("SAVE MEMORY ERROR:", e)

def load_memory(user_id):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, content
                FROM user_memory
                WHERE user_id=%s
                ORDER BY id DESC
                LIMIT 10
            """, (user_id,))
            rows = cur.fetchall()

        conn.close()
        rows.reverse()
        return rows

    except Exception as e:
        print("LOAD MEMORY ERROR:", e)
        return []

# --------------------
# COMMANDS
# --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\nMogu zapamtiti stvari o tebi 💾"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_memory WHERE user_id=%s",
                (str(update.effective_user.id),)
            )
        conn.commit()
        conn.close()

        await update.message.reply_text("Memorija resetirana ✅")

    except Exception as e:
        print(e)
        await update.message.reply_text("Reset error")

# --------------------
# CHAT
# --------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text

        history = load_memory(user_id)

        messages = [
            {"role": "system", "content": "You are friendly assistant."}
        ]

        messages += history
        messages.append({"role": "user", "content": text})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        reply = response.choices[0].message.content

        save_memory(user_id, "user", text)
        save_memory(user_id, "assistant", reply)

        await update.message.reply_text(reply)

    except Exception as e:
        print("CHAT ERROR:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")

# --------------------
# REGISTER
# --------------------

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
