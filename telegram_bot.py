import os
import json
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

# -------------------------------------------------
# OPENAI
# -------------------------------------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------------------------
# DATABASE
# -------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)

db_conn.autocommit = True


# -------------------------------------------------
# INIT DB
# -------------------------------------------------

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
        CREATE TABLE IF NOT EXISTS vector_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            content TEXT,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


init_db()

# -------------------------------------------------
# BASIC MEMORY
# -------------------------------------------------

def save_memory(user_id, role, content):
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO user_memory (user_id, role, content)
            VALUES (%s, %s, %s)
        """, (user_id, role, content))


def load_memory(user_id, limit=12):
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT role, content
            FROM user_memory
            WHERE user_id = %s
            ORDER BY id DESC
            LIMIT %s
        """, (user_id, limit))

        rows = cur.fetchall()
        rows.reverse()
        return rows


# -------------------------------------------------
# EMBEDDINGS
# -------------------------------------------------

def get_embedding(text):
    try:
        r = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return r.data[0].embedding
    except:
        return None


# -------------------------------------------------
# SMART MEMORY CLASSIFIER (GOD MODE)
# -------------------------------------------------

async def classify_memory_importance(text):
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """
Classify if message contains important long term memory.

Return ONLY JSON:
{
 "save": true or false
}
"""
                },
                {"role": "user", "content": text}
            ],
            temperature=0
        )

        return json.loads(r.choices[0].message.content)

    except:
        return {"save": False}


# -------------------------------------------------
# VECTOR MEMORY SAVE
# -------------------------------------------------

def save_vector_memory(user_id, text):
    try:
        emb = get_embedding(text)

        if emb is None:
            return

        with db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vector_memory (user_id, content, embedding)
                VALUES (%s, %s, %s)
            """, (user_id, text, str(emb)))

    except Exception as e:
        print("Vector save error:", e)


# -------------------------------------------------
# SEMANTIC SEARCH
# -------------------------------------------------

def semantic_search(user_id, text, limit=3):
    try:
        emb = get_embedding(text)

        if emb is None:
            return []

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT content
                FROM vector_memory
                WHERE user_id = %s
                ORDER BY embedding <-> %s
                LIMIT %s
            """, (user_id, str(emb), limit))

            return [r["content"] for r in cur.fetchall()]

    except Exception as e:
        print("Semantic search error:", e)
        return []


# -------------------------------------------------
# TELEGRAM COMMANDS
# -------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\n"
        "Mogu zapamtiti stvari o tebi 💾"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM user_memory WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM vector_memory WHERE user_id = %s", (user_id,))

    await update.message.reply_text("Memory resetiran.")


# -------------------------------------------------
# MAIN MESSAGE HANDLER
# -------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)
    text = update.message.text

    reply = None

    try:
        save_memory(user_id, "user", text)

        decision = await classify_memory_importance(text)

        if decision.get("save"):
            save_vector_memory(user_id, text)

        memory = load_memory(user_id)
        semantic_mem = semantic_search(user_id, text)

        memory_context = ""
        if semantic_mem:
            memory_context = "User memory:\n" + "\n".join(semantic_mem)

        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are Vinka AI assistant.

Use memory if relevant:
{memory_context}
"""
                },
                *memory,
                {"role": "user", "content": text}
            ]
        )

        reply = r.choices[0].message.content

        save_memory(user_id, "assistant", reply)

    except Exception as e:
        print("ERROR:", e)

    # SEND REPLY OUTSIDE TRY
    if reply:
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text(
            "Ups 😅 AI server je malo spor, probaj opet."
        )



# -------------------------------------------------
# REGISTER HANDLERS
# -------------------------------------------------

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
