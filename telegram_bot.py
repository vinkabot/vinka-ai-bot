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

        # MEMORY TABLE
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            importance FLOAT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # CLIENT TABLE
        cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_code TEXT PRIMARY KEY,
            name TEXT,
            prompt TEXT
        );
        """)

init_db()

# --------------------------------------------------
# IMPORTANCE DETECTION
# --------------------------------------------------

def detect_importance(text: str) -> float:
    text = text.lower()

    if any(x in text for x in ["zovem se", "ja sam", "moje ime"]):
        return 5

    if any(x in text for x in ["volim", "obožavam", "najdraže"]):
        return 3

    return 1

# --------------------------------------------------
# MEMORY
# --------------------------------------------------

def save_memory(user_id, role, content):
    importance = detect_importance(content)

    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_memory (user_id, role, content, importance)
        VALUES (%s, %s, %s, %s)
        """, (user_id, role, content, importance))


def get_memory_context(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT content
        FROM user_memory
        WHERE user_id = %s
        ORDER BY importance DESC, created_at DESC
        LIMIT 5
        """, (user_id,))

        rows = cur.fetchall()

    return "\n".join([r["content"] for r in rows])

def reset_memory(user_id):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM user_memory WHERE user_id=%s", (user_id,))

# --------------------------------------------------
# CLIENT SYSTEM
# --------------------------------------------------

def get_client_prompt(client_code):
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT prompt FROM clients WHERE client_code=%s",
            (client_code,)
        )
        row = cur.fetchone()

    if row and row["prompt"]:
        return row["prompt"]

    return "Ti si AI asistent."

# --------------------------------------------------
# OPENAI REPLY
# --------------------------------------------------

def ask_openai(user_text, memory_context, client_prompt):

    system_prompt = f"""
{client_prompt}

Koristi memory ako postoji.

Memory:
{memory_context}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        temperature=0.7
    )

    return response.choices[0].message.content

# --------------------------------------------------
# COMMANDS
# --------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    client_code = None

    if context.args:
        client_code = context.args[0]
        context.user_data["client_code"] = client_code

    await update.message.reply_text("Bot aktiviran.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    reset_memory(user_id)
    await update.message.reply_text("Memory resetiran.")


async def add_client(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        code = context.args[0]
        name = " ".join(context.args[1:])

        with db_conn.cursor() as cur:
            cur.execute("""
            INSERT INTO clients (client_code, name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """, (code, name))

        await update.message.reply_text("Client dodan.")

    except:
        await update.message.reply_text("Format: /add_client code Name")


async def set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        code = context.args[0]
        prompt = " ".join(context.args[1:])

        with db_conn.cursor() as cur:
            cur.execute("""
            UPDATE clients SET prompt=%s WHERE client_code=%s
            """, (prompt, code))

        await update.message.reply_text("Prompt postavljen.")

    except:
        await update.message.reply_text("Format: /set_prompt code prompt")

# --------------------------------------------------
# MESSAGE HANDLER
# --------------------------------------------------

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)
    text = update.message.text

    client_code = context.user_data.get("client_code", "default")

    client_prompt = get_client_prompt(client_code)

    try:
        save_memory(user_id, "user", text)

        memory = get_memory_context(user_id)

        reply = ask_openai(text, memory, client_prompt)

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

    app.add_handler(CommandHandler("add_client", add_client))
    app.add_handler(CommandHandler("set_prompt", set_prompt))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
