from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters


# ===== COMMANDS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\n"
        "Možeš pričati sa mnom normalno."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Memory resetirana.")


# ===== CHAT =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    try:
        # ZA SADA samo echo test (100% stabilno)
        await update.message.reply_text(f"Rekla si: {user_text}")

    except Exception as e:
        print("Message error:", e)
        await update.message.reply_text("Ups 😅 nešto je pošlo po zlu.")


# ===== REGISTER =====

def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
