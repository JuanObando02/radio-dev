import os
import socket
import time
import threading
import queue
import requests
import subprocess
from flask import Flask, jsonify, render_template, request

# --- CONFIGURACIÓN ---
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
LIQUIDSOAP_HOST = os.environ.get("LIQUIDSOAP_HOST", "liquidsoap")
LIQUIDSOAP_PORT = int(os.environ.get("LIQUIDSOAP_PORT", "1234"))
STREAM_URL = os.environ.get("STREAM_URL", "http://localhost:8000/radio.mp3")
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")

# --- COLA PROPIA (fuente de verdad) ---
# Lista ordenada de canciones pendientes
song_queue = []
queue_lock = threading.Lock()

# --- ESTADO DE LA RADIO ---
radio_state = {
    "current_title": "Iniciando...",
    "playlist": [],
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

def get_liq_queue_size():
    """Cuántas canciones tiene Liquidsoap en su cola interna."""
    response = liq_command("radio_queue.queue")
    if not response:
        return 0
    rids = [r.strip() for r in response.splitlines()
            if r.strip() and r.strip() != "END"]
    return len(rids)

def push_to_liquidsoap(song_name):
    """Envía una canción a la cola de Liquidsoap."""
    song_path = os.path.join(MUSIC_DIR, song_name)
    response = liq_command(f'radio_queue.push {song_path}')
    print(f"→ Liquidsoap: {song_name} ({response})", flush=True)
    return response is not None

# --- GESTOR DE COLA ---
def queue_manager():
    """
    Hilo que gestiona la cola propia.
    Mantiene siempre 1 canción en Liquidsoap para que no haya
    esperas pero tampoco se pierdan canciones de la cola.
    """
    print("🎵 Gestor de cola iniciado", flush=True)
    while True:
        with queue_lock:
            pending = len(song_queue)
            next_song = song_queue[0] if song_queue else None

        if next_song:
            liq_size = get_liq_queue_size()
            # Solo enviamos a Liquidsoap si su cola está vacía
            if liq_size == 0:
                with queue_lock:
                    if song_queue:
                        song = song_queue.pop(0)
                success = push_to_liquidsoap(song)
                if not success:
                    # Si falla, devolver al frente de la cola
                    with queue_lock:
                        song_queue.insert(0, song)

        time.sleep(2)

# --- TRACKER: canción actual desde Icecast ---
def get_current_title():
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        data = response.json()
        source = data.get("icestats", {}).get("source", {})
        return source.get("title", None)
    except Exception as e:
        print(f"Error consultando Icecast: {e}", flush=True)
    return None

def track_current_song():
    while True:
        title = get_current_title()
        if title:
            with state_lock:
                radio_state["current_title"] = title
        time.sleep(3)

# --- SCANNER: lista de canciones ---
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

@app.route('/api/search-youtube', methods=['POST'])
def search_youtube():
    data = request.get_json()
    query = data.get('query')
    if not query:
        return jsonify({"error": "Query requerida"}), 400

    try:
        result = subprocess.run([
            "yt-dlp",
            f"ytsearch5:{query}",  # top 5 resultados
            "--dump-json",
            "--flat-playlist",
            "--no-download"
        ], capture_output=True, text=True, timeout=15)

        videos = []
        for line in result.stdout.strip().splitlines():
            try:
                v = __import__('json').loads(line)
                videos.append({
                    "title": v.get("title"),
                    "channel": v.get("channel") or v.get("uploader"),
                    "duration": str(int(v.get("duration", 0) // 60)) + ":" + str(int(v.get("duration", 0) % 60)).zfill(2),
                    "url": f"https://youtube.com/watch?v={v.get('id')}",
                    "thumbnail": v.get("thumbnail"),
                })
            except:
                continue

        return jsonify({"results": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/request-download', methods=['POST'])
def request_download():
    data = request.get_json()
    url = data.get('url')
    title = data.get('title')
    channel = data.get('channel')
    duration = data.get('duration')

    if not url:
        return jsonify({"error": "URL requerida"}), 400

    try:
        res = requests.post(N8N_WEBHOOK_URL, json={
            "url": url,
            "title": title,
            "channel": channel,
            "duration": duration
        }, timeout=5)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/playlist')
def get_playlist():
    with state_lock:
        songs = radio_state["playlist"]
        title = radio_state["current_title"]
    with queue_lock:
        q = list(song_queue)
    return jsonify({
        "songs": songs,
        "now_playing": title,
        "queue": q,
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

    # Verificar si ya está en la cola
    with queue_lock:
        if song_name in song_queue:
            return jsonify({"error": "La canción ya está en la cola"}), 400
        song_queue.append(song_name)
        position = len(song_queue)

    print(f"📋 Encolada en posición {position}: {song_name}", flush=True)
    return jsonify({"ok": True, "queued": song_name, "position": position})

@app.route('/api/queue')
def get_queue():
    with queue_lock:
        return jsonify({"queue": list(song_queue)})

def start_web():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

@app.route('/api/download', methods=['POST'])
def download_song():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL requerida"}), 400

    def run_download():
        print(f"⬇ Descargando: {url}", flush=True)
        result = subprocess.run([
            "yt-dlp", "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s",
            url
        ], capture_output=True, text=True)
        print(result.stdout, flush=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}", flush=True)

    # Correr en hilo para no bloquear Flask
    threading.Thread(target=run_download, daemon=True).start()
    return jsonify({"ok": True, "message": "Descarga iniciada"})

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
    threading.Thread(target=queue_manager, daemon=True).start()

    print("📻 Radio lista.", flush=True)

    while True:
        time.sleep(60)