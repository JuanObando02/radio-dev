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
STREAM_URL = os.environ.get("STREAM_URL", "http://localhost:8000/radio.mp3")

# --- ESTADO DE LA RADIO ---
radio_state = {
    "current_song": "Iniciando...",
    "current_title": "Iniciando...",   # ← título limpio de Icecast
    "playlist": [],
    "queue": [],
}
state_lock = threading.Lock()

# --- COMUNICACIÓN CON LIQUIDSOAP VÍA TELNET ---
def liq_command(cmd):
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

def get_filename_from_rid(rid):
    """Obtiene el nombre de archivo de un RID de Liquidsoap."""
    response = liq_command(f"request.metadata {rid}")
    if response:
        for line in response.splitlines():
            if line.startswith("filename="):
                path = line.split("=", 1)[1].strip()
                return os.path.basename(path)
    return None

def get_queue_liq():
    """Consulta la cola real de Liquidsoap y retorna lista de nombres de canciones."""
    response = liq_command("radio_queue.queue")
    if not response:
        return []
    rids = [r.strip() for r in response.splitlines() if r.strip() and r.strip() != "END"]
    songs = []
    for rid in rids:
        name = get_filename_from_rid(rid)
        if name:
            songs.append(name)
    return songs

def enqueue_song(song_name):
    """Encola una canción en Liquidsoap."""
    song_path = os.path.join(MUSIC_DIR, song_name)
    response = liq_command(f'radio_queue.push {song_path}')
    print(f"Encolada: {song_name} → {response}", flush=True)
    return response

def get_current_song_icecast():
    """Lee el título actual desde Icecast."""
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        data = response.json()
        source = data.get("icestats", {}).get("source", {})
        return source.get("title", None)
    except Exception as e:
        print(f"Error consultando Icecast: {e}", flush=True)
    return None

# --- TRACKER: actualiza current_song y queue cada 3 segundos ---
def track_current_song():
    while True:
        title = get_current_song_icecast()
        if title:
            with state_lock:
                radio_state["current_title"] = title

        queue = get_queue_liq()
        with state_lock:
            radio_state["queue"] = queue

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
    return render_template('index.html', stream_url=STREAM_URL)

@app.route('/api/playlist')
def get_playlist():
    with state_lock:
        return jsonify({
            "songs": radio_state["playlist"],
            "now_playing": radio_state["current_title"],  # ← cambia esto
            "queue": radio_state["queue"],
        })

@app.route('/api/now-playing')
def now_playing_proxy():
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/play-next/<path:song_name>', methods=['POST'])
def play_next(song_name):
    with state_lock:
        playlist = radio_state["playlist"]

    if song_name not in playlist:
        return jsonify({"error": "Canción no encontrada"}), 404

    result = enqueue_song(song_name)
    if result is not None:
        return jsonify({"ok": True, "queued": song_name})
    else:
        return jsonify({"error": "No se pudo encolar"}), 500

def start_web():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    print("Esperando a que los servicios estén listos...", flush=True)
    time.sleep(10)

    songs = sorted([
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith(('.mp3', '.m4a', '.wav'))
    ])
    with state_lock:
        radio_state["playlist"] = songs

    print(f"✅ {len(songs)} canciones encontradas", flush=True)

    threading.Thread(target=start_web, daemon=True).start()
    threading.Thread(target=track_current_song, daemon=True).start()
    threading.Thread(target=scan_playlist, daemon=True).start()

    print("📻 Radio lista.", flush=True)

    while True:
        time.sleep(60)