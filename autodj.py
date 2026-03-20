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

# --- ESTADO DE LA RADIO (Para la API) ---
radio_state = {
    "current_song": "Iniciando...",
    "playlist": []
}

# --- DASHBOARD WEB (FLASK) ---
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/playlist')
def get_playlist():
    """Devuelve la lista completa y la canción actual desde la memoria del script"""
    return jsonify({
        "songs": radio_state["playlist"],
        "now_playing": radio_state["current_song"]
    })

@app.route('/api/now-playing')
def now_playing_proxy():
    """Proxy para consultar a Icecast (útil para ver estadísticas de oyentes)"""
    try:
        url_icecast = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url_icecast, timeout=2)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_web():
    # El servidor web corre en el puerto 5000 interno
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# --- MOTOR DE LA RADIO (Lógica de Canción por Canción) ---
def run_radio():
    print("--- Iniciando Motor de Radio Inteligente (Dev) ---", flush=True)
    
    while True:
        all_songs = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.m4a', '.wav'))]
        if not all_songs:
            print("No se encontraron canciones. Reintentando en 10s...")
            time.sleep(10)
            continue

        random.shuffle(all_songs)
        radio_state["playlist"] = all_songs

        # Escribir playlist temporal para FFmpeg
        playlist_path = "/tmp/playlist.txt"
        with open(playlist_path, "w") as f:
            for song in all_songs:
                song_path = os.path.join(MUSIC_DIR, song)
                f.write(f"file '{song_path}'\n")

        # Un solo proceso FFmpeg que toca TODAS las canciones sin cortar
        command = [
            "ffmpeg", "-re",
            "-f", "concat", "-safe", "0", "-i", playlist_path,
            "-vn",
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-content_type", "audio/mpeg",
            "-f", "mp3", ICECAST_URL
        ]

        print("▶ Iniciando stream continuo...", flush=True)
        subprocess.run(command)
        # Cuando termina toda la playlist, vuelve a mezclar y empieza de nuevo

def track_current_song():
    """Consulta Icecast cada 5s para saber qué canción está sonando"""
    while True:
        try:
            url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
            response = requests.get(url, timeout=2)
            data = response.json()
            
            # Navegar el JSON de Icecast para sacar el título
            source = data["icestats"]["source"]
            # Si hay varias fuentes, source es una lista
            if isinstance(source, list):
                source = source[0]
            
            title = source.get("title", "Desconocido")
            radio_state["current_song"] = title
        except Exception as e:
            print(f"Error consultando Icecast: {e}", flush=True)
        
        time.sleep(5)

if __name__ == "__main__":
    # Esperar un poco a que el contenedor de Icecast esté listo
    time.sleep(7)
    
    # Hilo 1: Servidor Web Flask
    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()
    
    tracker_thread = threading.Thread(target=track_current_song, daemon=True)
    tracker_thread.start()

    run_radio()