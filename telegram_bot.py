import os
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters

from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor


# -------------------------------------------------
# OpenAI
# -------------------------------------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# -------------------------------------------------
# Database
# -------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)


# -------------------------------------------------
# Commands
# -------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\nMožeš pričati sa mnom normalno.\nMogu zapamtiti stvari o tebi 💾"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM user_memory WHERE user_id = %s",
                    (str(update.effective_user.id),))
        db_conn.commit()

    await update.message.reply_text("Memory resetiran.")


# -------------------------------------------------
# AI Chat
# -------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text

        # Save memory
        with db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_memory (user_id, role, content)
                VALUES (%s,%s,%s)
            """, (user_id, "user", text))
            db_conn.commit()

        # Load memory
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT role, content
                FROM user_memory
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 10
            """, (user_id,))
            rows = cur.fetchall()

        messages = [
            {"role": r["role"], "content": r["content"]}
            for r in reversed(rows)
        ]

        messages.insert(0, {
            "role": "system",
            "content": "You are a friendly AI assistant."
        })

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages
        )

        reply = response.choices[0].message.content

        # Save AI reply
        with db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_memory (user_id, role, content)
                VALUES (%s,%s,%s)
            """, (user_id, "assistant", reply))
            db_conn.commit()

        await update.message.reply_text(reply)

    except Exception as e:
        print("AI ERROR:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")


# -------------------------------------------------
# Register handlers
# -------------------------------------------------

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
