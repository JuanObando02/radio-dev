import os
import subprocess
import time
import random
import threading
import requests
from flask import Flask, jsonify, render_template

# --- CONFIGURACIÓN ---
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast_dev")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
ICECAST_USER = os.environ.get("ICECAST_USER", "source")
ICECAST_PASS = os.environ.get("ICECAST_PASS", "supersecreto")
ICECAST_MOUNT = os.environ.get("ICECAST_MOUNT", "/radio.mp3")

ICECAST_URL = f"icecast://{ICECAST_USER}:{ICECAST_PASS}@{ICECAST_HOST}:{ICECAST_PORT}{ICECAST_MOUNT}"
PLAYLIST_PATH = "/tmp/playlist.txt"

# --- ESTADO DE LA RADIO ---
radio_state = {
    "current_song": "Iniciando...",
    "playlist": [],
    "song_index": 0,        # índice de la canción actual en la playlist
    "song_start": 0.0,      # timestamp de cuando empezó la canción actual
}

# Lock para acceso seguro al estado desde múltiples hilos
state_lock = threading.Lock()

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
            "now_playing": radio_state["current_song"]
        })

@app.route('/api/now-playing')
def now_playing_proxy():
    """Proxy para consultar estadísticas de oyentes en Icecast"""
    try:
        url_icecast = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url_icecast, timeout=2)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_web():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


# --- TRACKER: calcula qué canción está sonando según el tiempo ---
def track_current_song(durations):
    """
    Recibe una lista de duraciones (en segundos) de cada canción en la playlist.
    Cada 2 segundos calcula qué canción debería estar sonando según el tiempo
    transcurrido desde que empezó el stream y actualiza radio_state.
    """
    with state_lock:
        start_time = radio_state["song_start"]
        playlist = radio_state["playlist"][:]

    while True:
        elapsed = time.time() - start_time
        accumulated = 0.0

        for i, duration in enumerate(durations):
            accumulated += duration
            if elapsed < accumulated:
                with state_lock:
                    radio_state["current_song"] = playlist[i]
                    radio_state["song_index"] = i
                break
        else:
            # Si ya terminó toda la playlist, marcamos la última
            with state_lock:
                radio_state["current_song"] = playlist[-1]

        time.sleep(2)


# --- UTILIDAD: obtener duración de un archivo de audio con ffprobe ---
def get_duration(filepath):
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                filepath
            ],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


# --- MOTOR DE LA RADIO ---
def run_radio():
    print("--- Iniciando Motor de Radio (stream continuo) ---", flush=True)

    while True:
        # 1. Escanear canciones
        all_songs = [
            f for f in os.listdir(MUSIC_DIR)
            if f.lower().endswith(('.mp3', '.m4a', '.wav'))
        ]
        if not all_songs:
            print("No se encontraron canciones en /app/musica. Reintentando en 10s...", flush=True)
            time.sleep(10)
            continue

        random.shuffle(all_songs)

        # 2. Obtener duraciones de todas las canciones
        print("⏱ Calculando duraciones...", flush=True)
        durations = []
        for song in all_songs:
            path = os.path.join(MUSIC_DIR, song)
            d = get_duration(path)
            durations.append(d)
            print(f"  {song}: {d:.1f}s", flush=True)

        # 3. Escribir playlist para FFmpeg
        with open(PLAYLIST_PATH, "w") as f:
            for song in all_songs:
                song_path = os.path.join(MUSIC_DIR, song)
                f.write(f"file '{song_path}'\n")

        # 4. Actualizar estado global
        with state_lock:
            radio_state["playlist"] = all_songs
            radio_state["current_song"] = all_songs[0]
            radio_state["song_index"] = 0
            radio_state["song_start"] = time.time()

        # 5. Lanzar tracker en hilo separado
        tracker = threading.Thread(
            target=track_current_song,
            args=(durations,),
            daemon=True
        )
        tracker.start()

        # 6. Lanzar FFmpeg con la playlist completa (UNA SOLA CONEXIÓN)
        print("▶ Iniciando stream continuo...", flush=True)
        command = [
            "ffmpeg", "-re",
            "-f", "concat", "-safe", "0", "-i", PLAYLIST_PATH,
            "-vn",
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-content_type", "audio/mpeg",
            "-f", "mp3", ICECAST_URL
        ]
        subprocess.run(command)

        # Cuando FFmpeg termina (toda la playlist), vuelve a mezclar y repetir
        print("🔁 Playlist terminada, reiniciando...", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    # Esperar a que Icecast esté listo
    time.sleep(7)

    # Hilo 1: Servidor Web Flask
    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()

    # Hilo principal: Motor de Radio
    run_radio()