import requests
import time
import os

# ======================
# ENV VARIJABLE
# ======================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")  # nije direktno potreban ovdje, ali OK da postoji

# ======================
# URL-ovi
# ======================

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
FLASK_CHAT_URL = "http://127.0.0.1:5000/chat"

# ======================
# GLOBAL STATE
# ======================

last_update_id = None


# ======================
# TELEGRAM API
# ======================

def get_updates():
    global last_update_id

    url = f"{TELEGRAM_API}/getUpdates"
    params = {}

    if last_update_id:
        params["offset"] = last_update_id + 1

    response = requests.get(url, params=params, timeout=30)
    return response.json()


def send_message(chat_id, text):
    url = f"{TELEGRAM_API}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    requests.post(url, json=payload)


# ======================
# AI BACKEND CALL
# ======================

def ask_ai(text):
    try:
        response = requests.post(
            FLASK_CHAT_URL,
            json={"message": text},
            timeout=60
        )

        data = response.json()
        return data.get("reply", "No reply from AI")

    except Exception as e:
        print("AI ERROR:", e)
        return "AI backend error"


# ======================
# MAIN LOOP
# ======================

print("Telegram bot running...")

while True:

    updates = get_updates()

    if "result" in updates:

        for update in updates["result"]:

            last_update_id = update["update_id"]

            if "message" in update and "text" in update["message"]:

                chat_id = update["message"]["chat"]["id"]
                text = update["message"]["text"]

                print("Received:", text)

                # -------------------
                # START COMMAND
                # -------------------

                if text == "/start":
                    send_message(
                        chat_id,
                        "Hello 👋 I am Vinka AI Assistant.\nHow can I help you today?"
                    )
                    continue

                # -------------------
                # AI RESPONSE
                # -------------------

                reply = ask_ai(text)

                send_message(chat_id, reply)

    time.sleep(2)
