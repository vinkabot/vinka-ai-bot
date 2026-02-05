import os
from telegram import Update
from telegram.ext import ContextTypes
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\nMožeš pričati sa mnom normalno."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pošalji mi bilo koju poruku 🙂")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Resetirano!")

# ---------------- AI CHAT ----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        user_text = update.message.text or ""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Ti si friendly AI koji govori hrvatski."},
                {"role": "user", "content": user_text}
            ]
        )

        reply = response.choices[0].message.content
        await update.message.reply_text(reply)

    except Exception as e:
        print("OPENAI ERROR:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")
