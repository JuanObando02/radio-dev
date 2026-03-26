import socket
import time
import os
from core.config import LIQUIDSOAP_HOST, LIQUIDSOAP_PORT, MUSIC_DIR

def skip_current_song():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect(('liquidsoap', 1234)) 
            s.sendall(b"radio.skip\r\n")
            s.sendall(b"quit\r\n")
        print("⏭️ Comando 'skip' enviado a Liquidsoap.", flush=True)
        return True
    except Exception as e:
        print(f"❌ Error enviando 'skip' a Liquidsoap: {e}", flush=True)
        return False

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
    response = liq_command("radio_queue.queue")
    if not response:
        return 0
    rids = [r.strip() for r in response.splitlines()
            if r.strip() and r.strip() != "END"]
    return len(rids)

def push_to_liquidsoap(song_name):
    song_path = os.path.join(MUSIC_DIR, song_name)
    response = liq_command(f'radio_queue.push {song_path}')
    print(f"→ Liquidsoap: {song_name} ({response})", flush=True)
    return response is not None
