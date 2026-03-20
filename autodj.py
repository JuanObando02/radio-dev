import os
import subprocess
import time
import random

MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
ICECAST_USER = os.environ.get("ICECAST_USER", "source")
ICECAST_PASS = os.environ.get("ICECAST_PASS", "supersecreto")
ICECAST_MOUNT = os.environ.get("ICECAST_MOUNT", "/radio.mp3")

# URL de conexión interna en Docker
ICECAST_URL = f"icecast://{ICECAST_USER}:{ICECAST_PASS}@{ICECAST_HOST}:{ICECAST_PORT}{ICECAST_MOUNT}"

def get_playlist():
    # Busca todos los mp3 en la carpeta
    songs = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.endswith('.mp3')]
    random.shuffle(songs) # Modo aleatorio
    return songs

def stream_radio():
    print("Iniciando transmisión de radio...", flush=True)
    while True:
        playlist = get_playlist()
        if not playlist:
            print(f"No hay música en {MUSIC_DIR}. Esperando 10 segundos...", flush=True)
            time.sleep(10)
            continue

        for song in playlist:
            print(f"Reproduciendo: {os.path.basename(song)}", flush=True)
            # Usamos FFmpeg para codificar a 128kbps y enviar al servidor Icecast
            command = [
                "ffmpeg", "-re", "-i", song,
                "-c:a", "libmp3lame", "-b:a", "128k",
                "-content_type", "audio/mpeg",
                "-f", "mp3", ICECAST_URL
            ]
            # Ejecutamos el comando de forma silenciosa y esperamos a que termine la canción
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    # Le damos 5 segundos a Icecast para que termine de encender antes de transmitir
    time.sleep(5)
    stream_radio()