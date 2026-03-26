import socket
import time
import os
from core.config import LIQUIDSOAP_HOST, LIQUIDSOAP_PORT, MUSIC_DIR

def skip_current_song():
    print("⏭️ Enviando comando skip a Liquidsoap...", flush=True)
    # Saltamos la ambos orígenes, ya que el 'fallback' genérico no siempre tiene habilitado el skip
    res_queue = liq_command("radio_queue.skip")
    res_fallback = liq_command("fallback.skip")
    print(f"→ Respuesta Liquidsoap - Queue: {res_queue} | Fallback: {res_fallback}", flush=True)
    return True

def liq_command(cmd):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((LIQUIDSOAP_HOST, LIQUIDSOAP_PORT))
            # Usamos \r\n que es el estándar de Telnet para mayor compatibilidad
            s.sendall(f"{cmd}\r\n".encode())
            time.sleep(0.5)
            response = s.recv(4096).decode().strip()
            # Enviamos quit para cerrar la sesión de forma limpia
            s.sendall(b"quit\r\n")
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
