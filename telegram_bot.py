import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from openai import OpenAI


# =====================================================
# CONFIG
# =====================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = os.getenv("ADMIN_ID")

client = OpenAI(api_key=OPENAI_API_KEY)


# =====================================================
# DATABASE
# =====================================================

db_conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)

db_conn.autocommit = True


# =====================================================
# DB INIT
# =====================================================

def init_db():
    with db_conn.cursor() as cur:

        # MEMORY
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_memory (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # CLIENTS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            client_code TEXT PRIMARY KEY,
            name TEXT,
            system_prompt TEXT
        );
        """)

        # USER CLIENT MAP
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_clients (
            user_id TEXT PRIMARY KEY,
            client_code TEXT
        );
        """)

        # PLANS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id SERIAL PRIMARY KEY,
            name TEXT,
            price_monthly INTEGER,
            message_limit INTEGER
        );
        """)

        # SUBSCRIPTIONS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS client_subscriptions (
            client_code TEXT PRIMARY KEY,
            plan_id INTEGER,
            status TEXT,
            current_period_end TIMESTAMP
        );
        """)

        # USAGE
        cur.execute("""
        CREATE TABLE IF NOT EXISTS client_usage (
            client_code TEXT,
            month TEXT,
            messages_used INTEGER DEFAULT 0,
            PRIMARY KEY (client_code, month)
        );
        """)

        # DEFAULT PLANS
        cur.execute("""
        INSERT INTO plans (name, price_monthly, message_limit)
        VALUES
        ('free', 0, 200),
        ('pro', 39, 2000),
        ('business', 99, 10000)
        ON CONFLICT DO NOTHING;
        """)


init_db()


# =====================================================
# HELPERS
# =====================================================

def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID)


# CLIENT CONFIG

def set_user_client(user_id, client_code):
    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_clients (user_id, client_code)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET client_code = EXCLUDED.client_code
        """, (user_id, client_code))


def get_user_client(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT client_code FROM user_clients WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
    return row["client_code"] if row else None


def get_client_prompt(client_code):
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT system_prompt FROM clients WHERE client_code = %s
        """, (client_code,))
        row = cur.fetchone()
    return row["system_prompt"] if row else "Ti si AI asistent."


# BILLING

def get_client_plan(client_code):
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT p.name, p.message_limit, s.status
        FROM client_subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.client_code = %s
        """, (client_code,))
        return cur.fetchone()


def increment_usage(client_code):
    month = datetime.utcnow().strftime("%Y-%m")

    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO client_usage (client_code, month, messages_used)
        VALUES (%s, %s, 1)
        ON CONFLICT (client_code, month)
        DO UPDATE SET messages_used = client_usage.messages_used + 1
        """, (client_code, month))


def can_client_send(client_code):
    plan = get_client_plan(client_code)

    if not plan:
        return True

    if plan["status"] != "active":
        return False

    month = datetime.utcnow().strftime("%Y-%m")

    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT messages_used FROM client_usage
        WHERE client_code = %s AND month = %s
        """, (client_code, month))
        row = cur.fetchone()

    used = row["messages_used"] if row else 0
    return used < plan["message_limit"]


# MEMORY

def save_memory(user_id, role, content):
    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO user_memory (user_id, role, content)
        VALUES (%s, %s, %s)
        """, (user_id, role, content))


def get_memory_context(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
        SELECT content FROM user_memory
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 5
        """, (user_id,))
        rows = cur.fetchall()

    return "\n".join(r["content"] for r in rows) if rows else ""


# OPENAI

def ask_openai(user_text, memory_context, client_prompt):

    messages = [
        {
            "role": "system",
            "content": f"{client_prompt}\n\nMemory:\n{memory_context}"
        },
        {"role": "user", "content": user_text}
    ]

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content


# =====================================================
# ADMIN COMMANDS
# =====================================================

async def add_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    client_code = context.args[0]
    name = " ".join(context.args[1:])

    with db_conn.cursor() as cur:
        cur.execute("""
        INSERT INTO clients (client_code, name, system_prompt)
        VALUES (%s, %s, %s)
        ON CONFLICT (client_code)
        DO UPDATE SET name = EXCLUDED.name
        """, (client_code, name, "Ti si AI asistent."))

    await update.message.reply_text("Client dodan.")


async def set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    client_code = context.args[0]
    prompt = " ".join(context.args[1:])

    with db_conn.cursor() as cur:
        cur.execute("""
        UPDATE clients SET system_prompt = %s WHERE client_code = %s
        """, (prompt, client_code))

    await update.message.reply_text("Prompt updatean.")


async def list_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    with db_conn.cursor() as cur:
        cur.execute("SELECT client_code, name FROM clients")
        rows = cur.fetchall()

    text = "\n".join([f"{r['client_code']} → {r['name']}" for r in rows])
    await update.message.reply_text(text or "Nema klijenata.")


# =====================================================
# USER HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)

    if context.args:
        client_code = context.args[0]
        set_user_client(user_id, client_code)
        await update.message.reply_text("Bot aktiviran.")
    else:
        await update.message.reply_text("Pošaljite client kod.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)
    user_text = update.message.text

    client_code = get_user_client(user_id)

    if not client_code:
        await update.message.reply_text("Pokrenite bot pomoću client koda.")
        return

    if not can_client_send(client_code):
        await update.message.reply_text("Dosegnut mjesečni limit.")
        return

    increment_usage(client_code)

    client_prompt = get_client_prompt(client_code)

    save_memory(user_id, "user", user_text)
    memory_context = get_memory_context(user_id)

    reply = ask_openai(user_text, memory_context, client_prompt)

    save_memory(user_id, "assistant", reply)

    await update.message.reply_text(reply)


# =====================================================
# REGISTER
# =====================================================

def register_handlers(app):

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_client", add_client))
    app.add_handler(CommandHandler("set_prompt", set_prompt))
    app.add_handler(CommandHandler("list_clients", list_clients))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
