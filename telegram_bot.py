from app import chat_with_ai
from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bok! Ja sam Vinka AI 🤖\n"
        "Možeš pričati sa mnom normalno.\n"
        "Mogu zapamtiti stvari o tebi 💾"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Samo mi napiši poruku 😊"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "Resetirao sam razgovor 😊"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text

    try:
        reply = chat_with_ai(user_id, text)
        await update.message.reply_text(reply)

    except Exception as e:
        print("Telegram error:", e)

        await update.message.reply_text(
            "Ups 😅 nešto je pošlo po zlu."
        )
