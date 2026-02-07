import os
import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from openai import OpenAI


# --------------------------------------------------
# OPENAI
# --------------------------------------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)

db_conn.autocommit = True


# --------------------------------------------------
# DB INIT
# --------------------------------------------------

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

        cur.execute("""
        CREATE EXTENSION IF NOT EXISTS vector;
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS vector_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            content TEXT,
            embedding VECTOR(1536),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


init_db()


# --------------------------------------------------
# IMPORTANCE DETECTION
# --------------------------------------------------

def detect_importance(text: str) -> float:
    text = text.lower()

    if any(x in text for x in ["zovem se", "moje ime", "ja sam"]):
        return 5

    if any(x in text for x in ["volim", "obožavam", "najdraže"]):
        return 3

    return 1


# --------------------------------------------------
# PROFILE FACT EXTRACTION
# --------------------------------------------------

def extract_profile_fact(text: str):
    t = text.lower()

    if "zovem se" in t:
        return ("name", text.split("zovem se")[-1].strip())

    if "živim u" in t:
        return ("city", text.split("živim u")[-1].strip())

    if "volim pizzu" in t:
        return ("favorite_food", "pizza")

    if "volim crnu" in t:
        return ("favorite_color", "crna")

    return None


# --------------------------------------------------
# MEMORY HELPERS
# --------------------------------------------------

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
        cur.execute("DELETE FROM user_memory WHERE user_id = %s", (user_id,))


# --------------------------------------------------
# PROFILE HELPERS
# --------------------------------------------------

def save_profile_fact(user_id: str, field: str, value: str):
    with db_conn.cursor() as cur:
        cur.execute(f"""
        INSERT INTO user_profile (user_id, {field})
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            {field} = EXCLUDED.{field},
            updated_at = CURRENT_TIMESTAMP
        """, (user_id, value))


def get_profile_context(user_id: str) -> str:
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT *
        FROM user_profile
        WHERE user_id = %s
        """, (user_id,))

        row = cur.fetchone()

    if not row:
        return ""

    lines = []

    if row["name"]:
        lines.append(f"Ime: {row['name']}")
    if row["city"]:
        lines.append(f"Grad: {row['city']}")
    if row["favorite_food"]:
        lines.append(f"Omiljena hrana: {row['favorite_food']}")
    if row["favorite_color"]:
        lines.append(f"Omiljena boja: {row['favorite_color']}")

    return "\n".join(lines)


# --------------------------------------------------
# OPENAI REPLY
# --------------------------------------------------

def ask_openai(user_text: str, context: str) -> str:
    try:
        messages = [
            {
                "role": "system",
                "content": f"""
Ti si Vinka AI — Telegram AI asistent.

Koristi memory i profile ako postoje.

CONTEXT:
{context}
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


# --------------------------------------------------
# TELEGRAM HANDLERS
# --------------------------------------------------

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
        # Save chat memory
        save_memory(user_id, "user", user_text)

        # Save profile fact if detected
        fact = extract_profile_fact(user_text)
        if fact:
            field, value = fact
            save_profile_fact(user_id, field, value)

        memory_context = get_memory_context(user_id)
        profile_context = get_profile_context(user_id)

        full_context = f"""
PROFILE:
{profile_context}

MEMORY:
{memory_context}
"""

        reply = ask_openai(user_text, full_context)

        save_memory(user_id, "assistant", reply)

        await update.message.reply_text(reply)

    except Exception as e:
        print("Handler error:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
