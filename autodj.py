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
        # 1. Escanear y mezclar canciones
        all_songs = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.m4a', '.wav'))]
        if not all_songs:
            print("No se encontraron canciones en /app/musica. Reintentando en 10s...")
            time.sleep(10)
            continue
            
        random.shuffle(all_songs)
        radio_state["playlist"] = all_songs
        
        # 2. Reproducir una por una
        for song in all_songs:
            radio_state["current_song"] = song
            song_path = os.path.join(MUSIC_DIR, song)
            
            print(f"▶ Reproduciendo: {song}", flush=True)
            
            # Comando FFmpeg para UNA sola canción con Metadatos
            command = [
                "ffmpeg", "-re", "-i", song_path,
                "-vn",                                 # Sin video
                "-c:a", "libmp3lame", "-b:a", "128k",   # Convertir a MP3 128k
                "-metadata", f"title={song}",           # Enviar título a Icecast
                "-content_type", "audio/mpeg", 
                "-f", "mp3", ICECAST_URL
            ]
            
            # Ejecutamos y esperamos a que la canción termine
            subprocess.run(command)
            
            # Pequeña pausa técnica entre canciones
            time.sleep(1)

if __name__ == "__main__":
    # Esperar un poco a que el contenedor de Icecast esté listo
    time.sleep(7)
    
    # Hilo 1: Servidor Web Flask
    web_thread = threading.Thread(target=start_web, daemon=True)
    web_thread.start()
    
    # Hilo 2: Motor de Radio (en el hilo principal)
    run_radio()