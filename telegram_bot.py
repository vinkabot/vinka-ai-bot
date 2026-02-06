import os
import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from openai import OpenAI


# =========================================================
# OPENAI
# =========================================================

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL")

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)

db_conn.autocommit = True


# =========================================================
# DB INIT
# =========================================================

def init_db():
    with db_conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        try:
            cur.execute("""
                ALTER TABLE user_memory
                ADD COLUMN IF NOT EXISTS importance INTEGER DEFAULT 1;
            """)
        except Exception:
            pass

init_db()


# =========================================================
# IMPORTANCE DETECTION
# =========================================================

def detect_importance(text: str) -> int:
    text = text.lower()

    if any(x in text for x in [
        "zovem se",
        "moje ime je",
        "ja sam"
    ]):
        return 4

    if any(x in text for x in [
        "volim",
        "obožavam",
        "najdraže"
    ]):
        return 3

    return 1


# =========================================================
# MEMORY HELPERS
# =========================================================

def save_memory(user_id: str, role: str, content: str):
    importance = detect_importance(content)

    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_memory (user_id, role, content, importance)
        VALUES (%s, %s, %s, %s)
        """, (user_id, role, content, importance))


def get_memory_context(user_id: str) -> str:
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT content
        FROM user_memory
        WHERE user_id = %s
        ORDER BY importance DESC, created_at DESC
        LIMIT 5
        """, (user_id,))

        rows = cur.fetchall()

    if not rows:
        return ""

    return "\n".join([r["content"] for r in rows])


def reset_memory(user_id: str):
    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_memory WHERE user_id = %s",
            (user_id,)
        )


# =========================================================
# OPENAI REPLY
# =========================================================

def ask_openai(user_text: str, memory_context: str) -> str:
    try:
        messages = [
            {
                "role": "system",
                "content": f"""
Ti si Vinka AI, pametan Telegram AI asistent.
Koristi memory ako postoji.

Memory:
{memory_context}
"""
            },
            {"role": "user", "content": user_text}
        ]

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        print("OpenAI error:", e)
        return "Ups 😅 AI server je malo spor, probaj opet."


# =========================================================
# TELEGRAM HANDLERS
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\nMogu pamtiti stvari o tebi 🧠"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    reset_memory(user_id)
    await update.message.reply_text("Memory resetiran.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_text = update.message.text

    try:
        save_memory(user_id, "user", user_text)

        memory_context = get_memory_context(user_id)

        reply = ask_openai(user_text, memory_context)

        save_memory(user_id, "assistant", reply)

        await update.message.reply_text(reply)

    except Exception as e:
        print("Handler error:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")


# =========================================================
# REGISTER HANDLERS
# =========================================================

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
