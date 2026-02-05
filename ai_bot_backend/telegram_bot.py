import os
import requests
from dotenv import load_dotenv
from pathlib import Path
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

API_URL = "http://127.0.0.1:5000/chat"
RESET_URL = "http://127.0.0.1:5000/reset"

# --------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bok! Ja sam Vinka AI.\n"
        "Pamtim razgovor za svakog korisnika posebno.\n\n"
        "Komande:\n/reset\n/help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start – start\n/reset – reset memory\n/help – help"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    requests.post(
        RESET_URL,
        json={"user_id": user_id}
    )

    await update.message.reply_text("🔄 Memory resetiran!")

# --------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text

    response = requests.post(
        API_URL,
        json={
            "user_id": user_id,
            "message": text
        },
        timeout=30
    )

    reply = response.json().get("reply", "No response")
    await update.message.reply_text(reply)

# --------------------------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot running with per-user memory...")
    app.run_polling()

if __name__ == "__main__":
    main()
