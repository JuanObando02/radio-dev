import os
import subprocess
import time
import random

# Variables de entorno
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
ICECAST_USER = os.environ.get("ICECAST_USER", "source")
ICECAST_PASS = os.environ.get("ICECAST_PASS", "supersecreto")
ICECAST_MOUNT = os.environ.get("ICECAST_MOUNT", "/radio.mp3")

# URL de conexión (Protocolo icecast:// para FFmpeg)
ICECAST_URL = f"icecast://{ICECAST_USER}:{ICECAST_PASS}@{ICECAST_HOST}:{ICECAST_PORT}{ICECAST_MOUNT}"

def generate_playlist_file():
    """Crea un archivo de texto que FFmpeg usará como lista de reproducción"""
    songs = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.m4a'))]
    random.shuffle(songs)
    
    with open("playlist.txt", "w") as f:
        for song in songs:
            # Escribimos la ruta absoluta de cada canción
            f.write(f"file '{os.path.join(MUSIC_DIR, song)}'\n")
    return len(songs)

def stream_radio():
    print("--- Iniciando Stream ---", flush=True)
    
    while True:
        num_songs = generate_playlist_file()
        if num_songs == 0:
            print("No hay canciones, esperando...", flush=True)
            time.sleep(10)
            continue

        # Este comando de FFmpeg es el 'Truco Maestro'
        # -f concat: Une los archivos
        # -safe 0: Permite rutas absolutas
        # -stream_loop -1: Cuando llegue al final de la lista, empieza de nuevo SOLITO
        command = [
            "ffmpeg", "-re", 
            "-f", "concat", "-safe", "0", "-i", "playlist.txt",
            "-stream_loop", "-1", 
            "-vn",
            "-c:a", "libmp3lame", "-b:a", "128k", "-ac", "2",
            "-content_type", "audio/mpeg",
            "-f", "mp3", 
            ICECAST_URL
        ]
        
        print(f"Transmitiendo lista de {num_songs} canciones en bucle...", flush=True)
        # Este proceso se quedará corriendo 'para siempre'
        subprocess.run(command)
        print("El stream se cortó por alguna razón, reiniciando flujo principal...", flush=True)

if __name__ == "__main__":
    # Esperamos a que Icecast esté listo
    time.sleep(7)
    stream_radio()