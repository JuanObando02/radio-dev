import os
import socket
import time
import threading
import subprocess
import json
import requests
from flask import Flask, jsonify, render_template, request
from flask import session, redirect, send_from_directory

# --- CONFIGURACIÓN ---
MUSIC_DIR = "/app/musica"
ICECAST_HOST = os.environ.get("ICECAST_HOST", "icecast")
ICECAST_PORT = os.environ.get("ICECAST_PORT", "8000")
LIQUIDSOAP_HOST = os.environ.get("LIQUIDSOAP_HOST", "liquidsoap")
LIQUIDSOAP_PORT = int(os.environ.get("LIQUIDSOAP_PORT", "1234"))
STREAM_URL = os.environ.get("STREAM_URL", "http://localhost:8000/radio.mp3")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://dev-radio.juanobando.dev")

# --- TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# --- COLA PROPIA ---
song_queue = []
queue_lock = threading.Lock()

# --- SOLICITUDES DE DESCARGA PENDIENTES ---
pending_downloads = {}
pending_lock = threading.Lock()

# --- ESTADO DE LA RADIO ---
radio_state = {
    "current_title": "Iniciando...",
    "playlist": [],
}
state_lock = threading.Lock()

# --- TELEGRAM ---
def telegram_send(text, reply_markup=None):
    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        data = res.json()
        if data.get("ok"):
            return data["result"]["message_id"]
    except Exception as e:
        print(f"Error enviando mensaje Telegram: {e}", flush=True)
    return None

def telegram_answer_callback(callback_id, text="✅"):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback_id,
            "text": text
        }, timeout=5)
    except Exception as e:
        print(f"Error respondiendo callback: {e}", flush=True)

def telegram_edit_message(message_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/editMessageText", json={
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=5)
    except Exception as e:
        print(f"Error editando mensaje: {e}", flush=True)

def register_telegram_webhook():
    webhook_url = f"{DASHBOARD_URL}/api/telegram-webhook"
    try:
        res = requests.post(f"{TELEGRAM_API}/setWebhook", json={
            "url": webhook_url,
            "allowed_updates": ["callback_query"]
        }, timeout=10)
        data = res.json()
        print(f"Webhook Telegram: {data}", flush=True)
    except Exception as e:
        print(f"Error registrando webhook: {e}", flush=True)

def download_song(url, title, message_id=None):
    print(f"⬇ Descargando: {url}", flush=True)
    result = subprocess.run([
        "yt-dlp", "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
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

# --- LIQUIDSOAP ---
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

# --- FLASK ---
app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html', stream_url=STREAM_URL)

@app.route('/api/playlist')
def get_playlist():
    with state_lock:
        songs = radio_state["playlist"]
        title = radio_state["current_title"]
    with queue_lock:
        q = list(song_queue)
    return jsonify({"songs": songs, "now_playing": title, "queue": q})

@app.route('/api/now-playing')
def now_playing_proxy():
    try:
        url = f"http://{ICECAST_HOST}:{ICECAST_PORT}/status-json.xsl"
        response = requests.get(url, timeout=2)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/play-next/<path:song_name>', methods=['POST'])
def play_next(song_name):
    with state_lock:
        playlist = radio_state["playlist"]
    if song_name not in playlist:
        return jsonify({"error": "Canción no encontrada"}), 404
    with queue_lock:
        if song_name in song_queue:
            return jsonify({"error": "La canción ya está en la cola"}), 400
        song_queue.append(song_name)
        position = len(song_queue)
    print(f"📋 Encolada en posición {position}: {song_name}", flush=True)
    return jsonify({"ok": True, "queued": song_name, "position": position})

@app.route('/api/search-youtube', methods=['POST'])
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
                    "thumbnail": v.get("thumbnail"),
                })
            except:
                continue
        return jsonify({"results": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/request-download', methods=['POST'])
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

@app.route('/api/telegram-webhook', methods=['POST'])
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
        telegram_answer_callback(callback_id, "✅ Aprobado, descargando...")
        telegram_edit_message(message_id,
            f"✅ *Descarga aprobada*\n\n🎵 {download_info['title']}\nDescargando...")
        threading.Thread(
            target=download_song,
            args=(download_info["url"], download_info["title"], message_id),
            daemon=True
        ).start()
    else:
        telegram_answer_callback(callback_id, "❌ Rechazado")
        telegram_edit_message(message_id,
            f"❌ *Descarga rechazada*\n\n🎵 {download_info['title']}")

    return jsonify({"ok": True})

def start_web():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# --- ADMIN ---
import shutil
import jwt
import datetime
from functools import wraps
from werkzeug.utils import secure_filename

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "radio1234")
SECRET_KEY = os.environ.get("SECRET_KEY", "radio-secret-2024")
ALLOWED_EXTENSIONS = {'.mp3', '.m4a', '.wav'}

def generate_token():
    payload = {
        "admin": True,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return True
    except:
        return False

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token or not verify_token(token):
            return jsonify({"error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_page_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Para páginas HTML verificamos el token en cookie
        token = request.cookies.get("admin_token", "")
        if not token or not verify_token(token):
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated

@app.route('/admin')
@admin_page_required
def admin_panel():
    return send_from_directory('templates', 'admin.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return send_from_directory('templates', 'login.html')
    data = request.get_json()
    if data.get('password') == ADMIN_PASSWORD:
        token = generate_token()
        res = jsonify({"ok": True, "token": token})
        res.set_cookie("admin_token", token, httponly=True, samesite='Strict', max_age=28800)
        return res
    return jsonify({"ok": False}), 401

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    res = jsonify({"ok": True})
    res.delete_cookie("admin_token")
    return res

@app.route('/admin/api/songs')
@admin_required
def admin_songs():
    songs = sorted([
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith(('.mp3', '.m4a', '.wav'))
    ])
    total = shutil.disk_usage(MUSIC_DIR)
    def fmt(b):
        gb = b / (1024**3)
        return f"{gb:.1f}GB" if gb >= 1 else f"{b/(1024**2):.0f}MB"
    return jsonify({
        "songs": songs,
        "total": len(songs),
        "disk_used": fmt(total.used),
        "disk_free": fmt(total.free)
    })

@app.route('/admin/api/delete', methods=['POST'])
@admin_required
def admin_delete():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"error": "Nombre requerido"}), 400
    path = os.path.join(MUSIC_DIR, name)
    if not os.path.exists(path):
        return jsonify({"error": "Archivo no encontrado"}), 404
    try:
        os.remove(path)
        print(f"🗑 Eliminada: {name}", flush=True)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/upload', methods=['POST'])
@admin_required
def admin_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Formato no permitido"}), 400
    filename = secure_filename(file.filename)
    path = os.path.join(MUSIC_DIR, filename)
    file.save(path)
    print(f"⬆ Subida: {filename}", flush=True)
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("Esperando a que los servicios estén listos...", flush=True)
    time.sleep(10)

    songs = sorted([
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith(('.mp3', '.m4a', '.wav'))
    ])
    with state_lock:
        radio_state["playlist"] = songs

    print(f"✅ {len(songs)} canciones encontradas", flush=True)

    threading.Thread(target=start_web, daemon=True).start()
    threading.Thread(target=track_current_song, daemon=True).start()
    threading.Thread(target=scan_playlist, daemon=True).start()
    threading.Thread(target=queue_manager, daemon=True).start()

    time.sleep(3)
    register_telegram_webhook()

    print("📻 Radio lista.", flush=True)

    while True:
        time.sleep(60)
