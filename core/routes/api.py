from flask import Blueprint, jsonify, request, render_template
import os
import json
import requests
import subprocess
import threading

from core.config import ICECAST_HOST, ICECAST_PORT, STREAM_URL
from core.state import state_lock, queue_lock, pending_lock, radio_state, song_queue, pending_downloads, download_queue, download_lock
from core.services.liquidsoap import liq_command, skip_current_song
from core.services.telegram import telegram_send, telegram_answer_callback, telegram_edit_message
from core.services.youtube import download_song

api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def index():
    return render_template('index.html', stream_url=STREAM_URL)

@api_bp.route('/api/playlist')
def get_playlist():
    with state_lock:
        songs = radio_state["playlist"]
        title = radio_state["current_title"]
    with queue_lock:
        python_queue = list(song_queue)
        
    if python_queue:
        print(f"📋 Cola activa: {python_queue}", flush=True)
    
    # También consultar cola de Liquidsoap
    liq_queue = []
    response = liq_command("radio_queue.queue")
    if response:
        rids = [r.strip() for r in response.splitlines()
                if r.strip() and r.strip() != "END"]
        for rid in rids:
            meta = liq_command(f"request.metadata {rid}")
            if meta:
                for line in meta.splitlines():
                    if line.startswith("filename="):
                        path = line.split("=", 1)[1].strip()
                        liq_queue.append(os.path.basename(path))
                        break

    # Combinar: primero las de Liquidsoap, luego las pendientes en Python
    combined_queue = liq_queue + [s for s in python_queue if s not in liq_queue]

    return jsonify({"songs": songs, "now_playing": title, "queue": combined_queue})

@api_bp.route('/api/now-playing')
def now_playing_proxy():
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        data = response.json()
        
        # Interceptar stats para inyectar info de saltos (skip)
        source = data.get("icestats", {}).get("source", {})
        if isinstance(source, list) and len(source) > 0:
            source = source[0]
            
        song_title = source.get("title", "")
        listeners = source.get("listeners", 0)
        
        with state_lock:
            # Reseteo de votos al cambiar canción
            if song_title != radio_state["current_track_for_votes"]:
                radio_state["current_track_for_votes"] = song_title
                radio_state["voted_ips"].clear()
                
            if listeners <= 3:
                required = 1
            elif 4 <= listeners <= 10:
                required = max(1, listeners // 2)
            else:
                required = (listeners // 2) + 1
                
            data["skip_votes"] = len(radio_state["voted_ips"])
            data["skip_required"] = required
            
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/vote-skip', methods=['POST'])
def vote_skip():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
        
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        data = response.json()
        source = data.get("icestats", {}).get("source", {})
        if isinstance(source, list) and len(source) > 0:
            source = source[0]
        listeners = source.get("listeners", 0)
    except:
        listeners = 0

    with state_lock:
        if client_ip in radio_state["voted_ips"]:
            return jsonify({"error": "Ya has votado para saltar esta canción."}), 400
            
        radio_state["voted_ips"].add(client_ip)
        
        if listeners <= 3:
            required = 1
        elif 4 <= listeners <= 10:
            required = max(1, listeners // 2)
        else:
            required = (listeners // 2) + 1
            
        if len(radio_state["voted_ips"]) >= required:
            # Ejecutar salto real
            skip_current_song()
            # Prevenir colisiones múltiples
            radio_state["voted_ips"].clear()
            return jsonify({"ok": True, "skipped": True, "message": "¡Voto aceptado y canción saltada!"})
            
    return jsonify({"ok": True, "skipped": False, "message": "Voto registrado correctamente."})

@api_bp.route('/api/play-next/<path:song_name>', methods=['POST'])
def play_next(song_name):
    import urllib.parse
    song_name = urllib.parse.unquote(song_name)
    
    with state_lock:
        playlist = radio_state["playlist"]
    
    # Debug log para ver qué estamos recibiendo
    print(f"📥 Solicitud para encolar: {song_name}", flush=True)
    
    if song_name not in playlist:
        print(f"❌ Error: La canción '{song_name}' no existe en la playlist.", flush=True)
        return jsonify({"error": "Canción no encontrada"}), 404
    with queue_lock:
        if song_name in song_queue:
            return jsonify({"error": "La canción ya está en la cola"}), 400
        song_queue.append(song_name)
        position = len(song_queue)
    print(f"📋 Encolada en posición {position}: {song_name}", flush=True)
    return jsonify({"ok": True, "queued": song_name, "position": position})

@api_bp.route('/api/search-youtube', methods=['POST'])
def search_youtube():
    try:
        data = request.get_json()
        query = data.get('query')
        if not query:
            return jsonify({"error": "Query requerida"}), 400

        result = subprocess.run([
            "yt-dlp", f"ytsearch5:{query}",
            "--dump-json", "--flat-playlist", "--no-download"
        ], capture_output=True, text=True, timeout=15)

        videos = []
        for line in result.stdout.strip().splitlines():
            try:
                v = json.loads(line)
                dur = int(v.get("duration") or 0)
                videos.append({
                    "title": v.get("title"),
                    "channel": v.get("channel") or v.get("uploader"),
                    "duration": f"{dur // 60}:{str(dur % 60).zfill(2)}",
                    "url": f"https://youtube.com/watch?v={v.get('id')}",
                    "thumbnail": v.get("thumbnail") or f"https://i.ytimg.com/vi/{v.get('id')}/mqdefault.jpg",
                })
            except:
                continue
        return jsonify({"results": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/request-download', methods=['POST'])
def request_download():
    try:
        data = request.get_json()
        url = data.get('url')
        title = data.get('title', 'Sin título')
        channel = data.get('channel', '')
        duration = data.get('duration', '')

        if not url:
            return jsonify({"error": "URL requerida"}), 400

        message_id = telegram_send(
            f"🎵 *Nueva solicitud de descarga*\n\n"
            f"Título: {title}\n"
            f"Canal: {channel}\n"
            f"Duración: {duration}\n"
            f"URL: {url}\n\n"
            f"¿Aprobar descarga?",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "✅ Aprobar", "callback_data": "approve"},
                    {"text": "❌ Rechazar", "callback_data": "reject"}
                ]]
            }
        )

        if message_id:
            with pending_lock:
                pending_downloads[message_id] = {
                    "url": url, "title": title,
                    "channel": channel, "duration": duration
                }
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "No se pudo enviar mensaje a Telegram"}), 500

    except Exception as e:
        print(f"❌ Error en request_download: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/telegram-webhook', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    callback = update.get("callback_query")
    if not callback:
        return jsonify({"ok": True})

    callback_id = callback["id"]
    message_id = callback["message"]["message_id"]
    action = callback["data"]

    with pending_lock:
        download_info = pending_downloads.pop(message_id, None)

    if not download_info:
        telegram_answer_callback(callback_id, "⚠️ Solicitud no encontrada")
        return jsonify({"ok": True})

    if action == "approve":
        # Calculamos la posición en la cola para darle feedback al usuario
        with download_lock:
            posicion = len(download_queue) + 1
            download_queue.append({
                "url": download_info["url"],
                "title": download_info["title"],
                "message_id": message_id
            })
            
        telegram_answer_callback(callback_id, f"✅ Encolado (Posición {posicion})")
        telegram_edit_message(message_id,
            f"⏳ *Descarga en cola (Pos. {posicion})*\n\n🎵 {download_info['title']}\nEsperando turno...")
    else:
        telegram_answer_callback(callback_id, "❌ Rechazado")
        telegram_edit_message(message_id,
            f"❌ *Descarga rechazada*\n\n🎵 {download_info['title']}")

    return jsonify({"ok": True})
