import os
import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import ContextTypes

from openai import OpenAI


# ---------------- OPENAI ----------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------- DATABASE ----------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL missing")


def get_conn():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


# ---------------- INIT DB ----------------

def init_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
    conn.commit()
    conn.close()


init_db()


# ---------------- MEMORY ----------------

def save_memory(user_id, text):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_memory (user_id, content) VALUES (%s, %s)",
            (user_id, text),
        )
    conn.commit()
    conn.close()


def load_memory(user_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content
            FROM user_memory
            WHERE user_id=%s
            ORDER BY id DESC
            LIMIT 5
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    conn.close()

    return [r["content"] for r in rows]


def clear_memory(user_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_memory WHERE user_id=%s",
            (user_id,),
        )
    conn.commit()
    conn.close()


# ---------------- AI ----------------

def ask_ai(user_id, user_text):

    memories = load_memory(user_id)

    memory_context = "\n".join(memories) if memories else "No memory yet."

    prompt = f"""
User memory:
{memory_context}

User message:
{user_text}

Answer naturally.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content


# ---------------- TELEGRAM ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\n"
        "Možeš pričati sa mnom normalno.\n"
        "Mogu zapamtiti stvari o tebi 💾"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Piši normalno.\n"
        "Primjer:\n"
        "👉 zapamti da volim crnu boju\n"
        "👉 što volim"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    clear_memory(user_id)
    await update.message.reply_text("Memory resetiran 🧹")


# ---------------- MESSAGE ----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        user_id = str(update.effective_user.id)
        text = update.message.text.lower()

        # SAVE MEMORY
        if "zapamti" in text:
            memory_text = text.replace("zapamti", "").strip()
            save_memory(user_id, memory_text)

            await update.message.reply_text("Zapamtila sam! 💾")
            return

        # ASK AI
        reply = ask_ai(user_id, text)

        await update.message
