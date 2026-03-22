import os

# Variables de entorno

# --- CONEXIONES ---
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST") or "icecast"
ICECAST_PORT = os.environ.get("ICECAST_PORT") or "8000"
LIQUIDSOAP_HOST = os.environ.get("LIQUIDSOAP_HOST") or "liquidsoap"
LIQUIDSOAP_PORT = int(os.environ.get("LIQUIDSOAP_PORT") or "1234")

# --- URLS ---
STREAM_URL = os.environ.get("STREAM_URL") or "https://dev-stream.juanobando.dev/radio.mp3"
DASHBOARD_URL = os.environ.get("DASHBOARD_URL") or "https://dev-radio.juanobando.dev"

# --- TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or ""
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or ""
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# --- ADMIN ---
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "radio1234"
SECRET_KEY = os.environ.get("SECRET_KEY") or "radio-secret-2024"
ALLOWED_EXTENSIONS = {'.mp3', '.m4a', '.wav'}
