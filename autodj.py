import os
import subprocess
import time
import random
import threading
from flask import Flask, jsonify, render_template

# --- CONFIGURACIÓN ---
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast_dev")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
ICECAST_USER = os.environ.get("ICECAST_USER", "source")
ICECAST_PASS = os.environ.get("ICECAST_PASS", "supersecreto")
ICECAST_MOUNT = os.environ.get("ICECAST_MOUNT", "/radio.mp3")

ICECAST_URL = f"icecast://{ICECAST_USER}:{ICECAST_PASS}@{ICECAST_HOST}:{ICECAST_PORT}{ICECAST_MOUNT}"

# --- DASHBOARD WEB (FLASK) ---
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/playlist')
def get_playlist():
    songs = []
    if os.path.exists("playlist.txt"):
        with open("playlist.txt", "r") as f:
            for line in f:
                name = line.split('/')[-1].replace("'", "").strip()
                songs.append(name)
    return jsonify({"songs": songs})

def start_web():
    # Arranca el servidor web en el puerto 5000 (interno del contenedor)
    app.run(host='0.0.0.0', port=5000)

# --- MOTOR DE LA RADIO ---
def run_radio():
    print("--- Iniciando Motor de Radio (Dev) ---", flush=True)
    while True:
        # 1. Escanear canciones
        all_songs = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.m4a'))]
        random.shuffle(all_songs)
        
        # 2. Crear archivo de lista
        with open("playlist.txt", "w") as f:
            for s in all_songs:
                f.write(f"file '{os.path.join(MUSIC_DIR, s)}'\n")
        
        # 3. Lanzar FFmpeg (Inifinito)
        command = [
            "ffmpeg", "-re", "-stream_loop", "-1",
            "-f", "concat", "-safe", "0", "-i", "playlist.txt",
            "-vn", "-c:a", "libmp3lame", "-b:a", "128k",
            "-content_type", "audio/mpeg", "-f", "mp3", ICECAST_URL
        ]
        subprocess.run(command)
        time.sleep(2)

if __name__ == "__main__":
    time.sleep(5) # Esperar a Icecast
    # Lanzar la web en un hilo aparte
    threading.Thread(target=start_web, daemon=True).start()
    # Lanzar la radio en el hilo principal
    run_radio()