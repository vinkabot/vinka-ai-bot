import requests
import time
import os

# =========================
# ENV VARIABLES
# =========================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FLASK_CHAT_URL = "http://127.0.0.1:5000/chat"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

last_update_id = None


# =========================
# TELEGRAM FUNCTIONS
# =========================

def get_updates():
    global last_update_id

    url = f"{TELEGRAM_API}/getUpdates"
    params = {"timeout": 30}

    if last_update_id:
        params["offset"] = last_update_id + 1

    r = requests.get(url, params=params, timeout=30)
    return r.json()


def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    requests.post(url, json=payload)


# =========================
# AI BACKEND CALL
# =========================

def ask_ai(text):
    try:
        r = requests.post(
            FLASK_CHAT_URL,
            json={"message": text},
            timeout=60
        )

        data = r.json()
        return data.get("reply", "No reply")

    except Exception as e:
        print("AI ERROR:", e)
        return "AI backend error"


# =========================
# MAIN LOOP
# =========================

print("Telegram bot running...")

while True:

    updates = get_updates()

    if "result" in updates:

        for update in updates["result"]:

            last_update_id = update["update_id"]

            if "message" not in update:
                continue

            if "text" not in update["message"]:
                continue

            chat_id = update["message"]["chat"]["id"]
            text = update["message"]["text"]

            print("Received:", text)

            # START COMMAND
            if text.lower() == "/start":
                send_message(chat_id, "Hello 👋 I am Vinka AI Assistant. How can I help you today?")
                continue

            # NORMAL MESSAGE → AI
            reply = ask_ai(text)

            send_message(chat_id, reply)

    time.sleep(2)
