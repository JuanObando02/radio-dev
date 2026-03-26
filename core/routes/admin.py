from flask import Blueprint, request, jsonify, redirect, render_template
import os
import shutil
import jwt
import datetime
from functools import wraps
from werkzeug.utils import secure_filename

from core.config import ADMIN_PASSWORD, SECRET_KEY, ALLOWED_EXTENSIONS, MUSIC_DIR, STREAM_URL
from core.services.liquidsoap import skip_current_song

admin_bp = Blueprint('admin', __name__)

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
    
@admin_bp.route('/api/admin/skip', methods=['POST'])
@admin_required
def handle_skip():
    # Aquí puedes agregar la verificación de sesión de tu panel de admin (si la tienes)
    
    if skip_current_song():
        return jsonify({"ok": True, "message": "Saltando a la siguiente canción..."}), 200
    else:
        return jsonify({"ok": False, "message": "Error de comunicación con Liquidsoap."}), 500

@admin_bp.route('/admin')
@admin_page_required
def admin_panel():
    return render_template('admin.html', stream_url=STREAM_URL)

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('login.html')
    data = request.get_json()
    if data.get('password') == ADMIN_PASSWORD:
        token = generate_token()
        res = jsonify({"ok": True, "token": token})
        res.set_cookie("admin_token", token, httponly=True, samesite='Strict', max_age=28800)
        return res
    return jsonify({"ok": False}), 401

@admin_bp.route('/admin/logout', methods=['POST'])
def admin_logout():
    res = jsonify({"ok": True})
    res.delete_cookie("admin_token")
    return res

@admin_bp.route('/admin/api/songs')
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

@admin_bp.route('/admin/api/delete', methods=['POST'])
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

@admin_bp.route('/admin/api/upload', methods=['POST'])
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
