import json
import requests
from core.config import TELEGRAM_API, TELEGRAM_CHAT_ID, DASHBOARD_URL

def telegram_send(text, reply_markup=None):
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        data = res.json()
        if data.get("ok"):
            return data["result"]["message_id"]
    except Exception as e:
        print(f"Error enviando mensaje Telegram: {e}", flush=True)
    return None

def telegram_answer_callback(callback_id, text="✅"):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback_id,
            "text": text
        }, timeout=5)
    except Exception as e:
        print(f"Error respondiendo callback: {e}", flush=True)

def telegram_edit_message(message_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/editMessageText", json={
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=5)
    except Exception as e:
        print(f"Error editando mensaje: {e}", flush=True)

def register_telegram_webhook():
    webhook_url = f"{DASHBOARD_URL}/api/telegram-webhook"
    try:
        res = requests.post(f"{TELEGRAM_API}/setWebhook", json={
            "url": webhook_url,
            "allowed_updates": ["callback_query"]
        }, timeout=10)
        data = res.json()
        print(f"Webhook Telegram: {data}", flush=True)
    except Exception as e:
        print(f"Error registrando webhook: {e}", flush=True)
