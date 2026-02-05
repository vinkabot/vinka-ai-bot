from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pathlib import Path
import os
import json
from datetime import datetime
from openai import OpenAI

# --------------------------------------------------
# Setup
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

app = Flask(__name__)

@app.route("/")
def health():
    return "Bot alive"

from telegram import Update
from telegram.ext import Application

telegram_app = None

@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook():
    global telegram_app
    
    if telegram_app is None:
        telegram_app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)

    return "ok"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --------------------------------------------------
# Files
# --------------------------------------------------
MEMORY_FILE = BASE_DIR / "memory_store.json"
LOG_FILE = BASE_DIR / "chat_logs.txt"

SYSTEM_PROMPT = (
    "You are Vinka AI Assistant. "
    "You remember conversation context for each user. "
    "Be friendly and helpful."
)

MAX_HISTORY = 12

# --------------------------------------------------
# Load memory
# --------------------------------------------------
if MEMORY_FILE.exists():
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        try:
            user_memories = json.load(f)
        except:
            user_memories = {}
else:
    user_memories = {}

# --------------------------------------------------
# Save memory
# --------------------------------------------------
def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(user_memories, f, ensure_ascii=False, indent=2)

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def get_user_memory(user_id):
    if user_id not in user_memories:
        user_memories[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        save_memory()
    return user_memories[user_id]

def reset_user_memory(user_id):
    user_memories[user_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    save_memory()

def log_message(user_id, role, content):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] USER:{user_id} {role.upper()}: {content}\n")

# --------------------------------------------------
# Chat
# --------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    user_id = str(data.get("user_id", "default"))
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"reply": "No message provided"}), 400

    memory = get_user_memory(user_id)

    log_message(user_id, "user", message)
    memory.append({"role": "user", "content": message})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=memory
        )

        reply = response.choices[0].message.content

        log_message(user_id, "assistant", reply)
        memory.append({"role": "assistant", "content": reply})

        if len(memory) > MAX_HISTORY:
            memory[:] = [memory[0]] + memory[-(MAX_HISTORY - 1):]

        save_memory()

        return jsonify({"reply": reply})

    except Exception as e:
        print(e)
        return jsonify({"reply": "Error"}), 500

# --------------------------------------------------
# Reset
# --------------------------------------------------
@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json()
    user_id = str(data.get("user_id", "default"))

    reset_user_memory(user_id)
    return jsonify({"status": "reset"})


# --------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )

