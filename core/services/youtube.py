import subprocess
from core.config import MUSIC_DIR
from core.services.telegram import telegram_edit_message

def download_song(url, title, message_id=None):
    print(f"⬇ Descargando: {url}", flush=True)
    result = subprocess.run([
        "yt-dlp", "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-metadata",
        "--cookies", "/app/cookies.txt",
        "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s",
        url
    ], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Descarga exitosa: {title}", flush=True)
        if message_id:
            telegram_edit_message(message_id,
                f"✅ *Descarga completada*\n\n🎵 {title}\n\nYa está disponible en la radio.")
    else:
        print(f"❌ Error descargando: {result.stderr}", flush=True)
        if message_id:
            telegram_edit_message(message_id,
                f"❌ *Error en la descarga*\n\n🎵 {title}")
