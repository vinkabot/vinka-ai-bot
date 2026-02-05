from telegram.ext import CommandHandler, MessageHandler, filters
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------- COMMANDS ----------

async def start(update, context):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖"
    )


async def reset(update, context):
    await update.message.reply_text(
        "Memory resetirana."
    )


# ---------- MESSAGE ----------

async def handle_message(update, context):
    try:
        if not update.message or not update.message.text:
            return

        user_text = update.message.text

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ti si Vinka AI."},
                {"role": "user", "content": user_text},
            ],
        )

        reply = response.choices[0].message.content

        await update.message.reply_text(reply)

    except Exception as e:
        print("HANDLE ERROR:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")


# ---------- SETUP ----------

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
