import os
import socket
import time
import random
import threading
import requests
from flask import Flask, jsonify, render_template

# --- CONFIGURACIÓN ---
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
LIQUIDSOAP_HOST = os.environ.get("LIQUIDSOAP_HOST", "liquidsoap")
LIQUIDSOAP_PORT = int(os.environ.get("LIQUIDSOAP_PORT", "1234"))

# --- ESTADO DE LA RADIO ---
radio_state = {
    "current_song": "Iniciando...",
    "playlist": [],
    "next_song": None,
}
state_lock = threading.Lock()

# --- COMUNICACIÓN CON LIQUIDSOAP VÍA TELNET ---
def liq_command(cmd):
    """Envía un comando a Liquidsoap y retorna la respuesta."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((LIQUIDSOAP_HOST, LIQUIDSOAP_PORT))
            s.sendall((cmd + "\n").encode())
            time.sleep(0.3)
            response = s.recv(4096).decode().strip()
            return response
    except Exception as e:
        print(f"Error telnet Liquidsoap: {e}", flush=True)
        return None

def enqueue_song(song_name):
    """Encola una canción en Liquidsoap."""
    song_path = os.path.join(MUSIC_DIR, song_name)
    response = liq_command(f'radio_queue.push {song_path}')
    print(f"Encolada: {song_name} → {response}", flush=True)
    return response

def get_current_song_liq():
    """Consulta a Liquidsoap qué canción está sonando."""
    response = liq_command("radio.metadata")
    if response:
        for line in response.splitlines():
            if line.startswith("filename="):
                path = line.split("=", 1)[1].strip()
                return os.path.basename(path)
    return None

# --- TRACKER: actualiza current_song cada 3 segundos ---
def track_current_song():
    while True:
        song = get_current_song_liq()
        if song:
            with state_lock:
                radio_state["current_song"] = song
        time.sleep(3)

# --- SCANNER: mantiene la playlist actualizada ---
def scan_playlist():
    while True:
        songs = sorted([
            f for f in os.listdir(MUSIC_DIR)
            if f.lower().endswith(('.mp3', '.m4a', '.wav'))
        ])
        with state_lock:
            radio_state["playlist"] = songs
        time.sleep(30)

# --- DASHBOARD WEB (FLASK) ---
app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/playlist')
def get_playlist():
    with state_lock:
        return jsonify({
            "songs": radio_state["playlist"],
            "now_playing": radio_state["current_song"],
            "next_song": radio_state["next_song"],
        })

@app.route('/api/now-playing')
def now_playing_proxy():
    """Proxy para estadísticas de Icecast."""
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/play-next/<path:song_name>', methods=['POST'])
def play_next(song_name):
    """Encola una canción para que suene de siguiente."""
    with state_lock:
        playlist = radio_state["playlist"]

    if song_name not in playlist:
        return jsonify({"error": "Canción no encontrada"}), 404

    result = enqueue_song(song_name)
    if result is not None:
        with state_lock:
            radio_state["next_song"] = song_name
        return jsonify({"ok": True, "queued": song_name})
    else:
        return jsonify({"error": "No se pudo encolar"}), 500

def start_web():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Esperar a que Liquidsoap e Icecast estén listos
    print("Esperando a que los servicios estén listos...", flush=True)
    time.sleep(10)

    # Escanear canciones inicial
    songs = sorted([
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith(('.mp3', '.m4a', '.wav'))
    ])
    with state_lock:
        radio_state["playlist"] = songs

    print(f"✅ {len(songs)} canciones encontradas", flush=True)

    # Hilo 1: Servidor Web Flask
    threading.Thread(target=start_web, daemon=True).start()

    # Hilo 2: Tracker de canción actual
    threading.Thread(target=track_current_song, daemon=True).start()

    # Hilo 3: Scanner de playlist
    threading.Thread(target=scan_playlist, daemon=True).start()

    print("📻 Radio lista.", flush=True)

    # Mantener el proceso vivo
    while True:
        time.sleep(60)