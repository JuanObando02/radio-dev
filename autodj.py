import time
import os
import threading
from flask import Flask

from core.config import MUSIC_DIR
from core.state import state_lock, radio_state
from core.routes.api import api_bp
from core.routes.admin import admin_bp
from core.tasks import track_current_song, scan_playlist, queue_manager
from core.services.telegram import register_telegram_webhook

# --- FLASK APP ---
app = Flask(__name__, static_folder='static', template_folder='templates')

# Registrar Blueprints
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)

def start_web():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    print("Esperando a que los servicios estén listos...", flush=True)
    time.sleep(10)

    # Escaneo inicial de playlist
    songs = sorted([
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith(('.mp3', '.m4a', '.wav'))
    ])
    with state_lock:
        radio_state["playlist"] = songs

    print(f"✅ {len(songs)} canciones encontradas", flush=True)

    # Iniciar hilos
    threading.Thread(target=start_web, daemon=True).start()
    threading.Thread(target=track_current_song, daemon=True).start()
    threading.Thread(target=scan_playlist, daemon=True).start()
    threading.Thread(target=queue_manager, daemon=True).start()

    time.sleep(3)
    register_telegram_webhook()

    print("📻 Radio lista.", flush=True)

    while True:
        time.sleep(60)
