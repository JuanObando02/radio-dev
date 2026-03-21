# --- Configuración desde variables de entorno ---
icecast_host = getenv("ICECAST_HOST")
icecast_port = int_of_string(getenv("ICECAST_PORT"))
icecast_pass = getenv("ICECAST_PASS")
icecast_mount = getenv("ICECAST_MOUNT")
music_dir = "/app/musica"

# --- Cola dinámica (aquí Flask encola canciones) ---
radio_queue = request.queue(id="radio_queue")

# --- Fallback: reproduce carpeta en shuffle infinito ---
fallback_playlist = playlist(
  id="fallback",
  mode="randomize",
  reload=60,
  music_dir
)

# --- Fuente final: primero la cola, si no hay nada el fallback ---
radio = fallback(
  id="radio",
  track_sensitive=true,
  [radio_queue, fallback_playlist]
)

# --- Salida hacia Icecast ---
output.icecast(
  %mp3(bitrate=128),
  host=icecast_host,
  port=icecast_port,
  password=icecast_pass,
  mount=icecast_mount,
  name="Radio Dev",
  description="AutoDJ con Liquidsoap",
  radio
)

# --- API Telnet en puerto 1234 ---
server.telnet(bind_addr="0.0.0.0", port=1234)
