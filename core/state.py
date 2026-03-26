import threading

# --- COLA PROPIA ---
song_queue = []
queue_lock = threading.Lock()

# --- SOLICITUDES DE DESCARGA PENDIENTES ---
pending_downloads = {}
pending_lock = threading.Lock()

# --- COLA DE DESCARGAS APROBADAS ---
download_queue = []
download_lock = threading.Lock()

# --- ESTADO DE LA RADIO ---
radio_state = {
    "current_title": "Iniciando...",
    "playlist": [],
    "current_track_for_votes": None,
    "voted_ips": set()
}

state_lock = threading.Lock()
