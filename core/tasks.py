import time
import os
import requests

from core.config import MUSIC_DIR, ICECAST_HOST, ICECAST_PORT
from core.state import state_lock, queue_lock, radio_state, song_queue
from core.services.liquidsoap import get_liq_queue_size, push_to_liquidsoap

def queue_manager():
    print("🎵 Gestor de cola iniciado", flush=True)
    while True:
        with queue_lock:
            next_song = song_queue[0] if song_queue else None
        if next_song:
            liq_size = get_liq_queue_size()
            if liq_size == 0:
                with queue_lock:
                    if song_queue:
                        song = song_queue.pop(0)
                push_to_liquidsoap(song)
        time.sleep(2)

def get_current_title():
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        data = response.json()
        source = data.get("icestats", {}).get("source", {})
        return source.get("title", None)
    except:
        return None

def track_current_song():
    while True:
        title = get_current_title()
        if title:
            with state_lock:
                radio_state["current_title"] = title
        time.sleep(3)

def scan_playlist():
    while True:
        songs = sorted([
            f for f in os.listdir(MUSIC_DIR)
            if f.lower().endswith(('.mp3', '.m4a', '.wav'))
        ])
        with state_lock:
            radio_state["playlist"] = songs
        time.sleep(30)
