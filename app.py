from flask import Flask, request
from dotenv import load_dotenv
import os

from openai import OpenAI

import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters


# --------------------------------------------------
# ENV
# --------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")


# --------------------------------------------------
# APP + CLIENTS
# --------------------------------------------------

app = Flask(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)


# --------------------------------------------------
# DB CONNECTION
# --------------------------------------------------

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

        # Enable vector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

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

        # Vector memory table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vector_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            content TEXT,
            embedding vector(1536),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

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
# TELEGRAM GLOBAL
# --------------------------------------------------

telegram_app = None


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/")
def health():
    return "Bot alive"


# --------------------------------------------------
# TELEGRAM HANDLERS
# --------------------------------------------------

async def start(update, context):
    await update.message.reply_text("Hello! I'm Vinka AI.")


async def handle_message(update, context):
    user_id = str(update.effective_user.id)
    message = update.message.text


    # ---------------- NORMAL MEMORY LOAD ----------------

    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT role, content
        FROM user_memory
        WHERE user_id = %s
        ORDER BY created_at ASC
        LIMIT 12
        """, (user_id,))

        history = cur.fetchall()


    messages = [{"role": "system", "content": "You are Vinka AI assistant."}]

    for row in history:
        messages.append({
            "role": row["role"],
            "content": row["content"]
        })

    messages.append({"role": "user", "content": message})


    # ---------------- OPENAI CHAT ----------------

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    reply = response.choices[0].message.content


    # ---------------- SAVE NORMAL MEMORY ----------------

    with db_conn.cursor() as cur:

        cur.execute("""
        INSERT INTO user_memory (user_id, role, content)
        VALUES (%s, %s, %s)
        """, (user_id, "user", message))

        cur.execute("""
        INSERT INTO user_memory (user_id, role, content)
        VALUES (%s, %s, %s)
        """, (user_id, "assistant", reply))


        # ---------------- VECTOR MEMORY SAVE ----------------

        embedding = get_embedding(message)

        cur.execute("""
        INSERT INTO vector_memory (user_id, content, embedding)
        VALUES (%s, %s, %s)
        """, (user_id, message, embedding))


    await update.message.reply_text(reply)


# --------------------------------------------------
# WEBHOOK
# --------------------------------------------------

@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app

    if telegram_app is None:
        telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        await telegram_app.initialize()

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)

    await telegram_app.process_update(update)

    return "ok"


# --------------------------------------------------
# LOCAL RUN
# --------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
