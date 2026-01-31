from flask import Flask, request, jsonify
from openai import OpenAI
import os

# ------------------------
# CONFIG
# ------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

SYSTEM_PROMPT = """
You are Vinka AI Assistant.

You must NEVER say you are ChatGPT or OpenAI model.

You are a helpful, friendly personal assistant named Vinka.

Always introduce yourself as: Vinka AI Assistant.

Be concise, friendly and helpful.
"""



# ------------------------
# ROUTE
# ------------------------

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json()

    if not data or "message" not in data:
        return jsonify({"reply": "No message received"}), 400

    user_message = data["message"]

    print("AI REQUEST:", user_message)

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        ai_reply = response.output_text

        print("AI REPLY:", ai_reply)

        return jsonify({"reply": ai_reply})

    except Exception as e:
        print("OPENAI ERROR:", e)
        return jsonify({"reply": "AI backend error"}), 500


# ------------------------
# START SERVER
# ------------------------

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
