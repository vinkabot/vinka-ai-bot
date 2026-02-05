from telegram import Update
from telegram.ext import ContextTypes
from openai import OpenAI
import os

import psycopg2
from psycopg2.extras import RealDictCursor


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

db_conn = psycopg2.connect(
    os.getenv("DATABASE_URL"),
    cursor_factory=RealDictCursor
)
db_conn.autocommit = True


# ---------------- MEMORY ----------------

def save_message(user_id, role, content):
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_memory (user_id, role, content) VALUES (%s,%s,%s)",
            (user_id, role, content)
        )


def get_memory(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT role, content
            FROM user_memory
            WHERE user_id=%s
            ORDER BY id DESC
            LIMIT 10
        """, (user_id,))
        return cur.fetchall()


def save_fact(user_id, fact):
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO user_facts (user_id, fact) VALUES (%s,%s)",
            (user_id, fact)
        )


def get_facts(user_id):
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT fact FROM user_facts
            WHERE user_id=%s
            ORDER BY id DESC
            LIMIT 10
        """, (user_id,))
        return [r["fact"] for r in cur.fetchall()]


def detect_fact(text):
    t = text.lower()
    if "volim" in t:
        return text
    return None


# ---------------- AI ----------------

def chat_with_ai(user_id, text):

    save_message(user_id, "user", text)

    fact = detect_fact(text)
    if fact:
        save_fact(user_id, fact)

    memory = get_memory(user_id)
    facts = get_facts(user_id)

    messages = []

    if facts:
        messages.append({
            "role": "system",
            "content": "User facts: " + "; ".join(facts)
        })

    for m in reversed(memory):
        messages.append({
            "role": m["role"],
            "content": m["content"]
        })

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages
    )

    reply = response.choices[0].message.content

    save_message(user_id, "assistant", reply)

    return reply


# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\n"
        "Mogu zapamtiti stvari o tebi 💾"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Samo piši 😊")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Resetirao sam razgovor 😊")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text

    try:
        reply = chat_with_ai(user_id, text)
        await update.message.reply_text(reply)

    except Exception as e:
        print("TELEGRAM ERROR:", e)

        await update.message.reply_text(
            "Ups 😅 nešto je pošlo po zlu."
        )
