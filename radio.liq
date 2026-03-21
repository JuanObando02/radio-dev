settings.server.telnet.set(true)
settings.server.telnet.bind_addr.set("0.0.0.0")
settings.server.telnet.port.set(1234)

# --- Cola dinámica ---
radio_queue = request.queue(id="radio_queue")

# --- Fallback: carpeta en shuffle ---
fallback_playlist = playlist(
  id="fallback",
  mode="randomize",
  reload_mode="watch",
  "/app/musica"
)

# --- Fuente final: cola primero, si no hay nada el fallback ---
# mksafe garantiza que siempre haya audio (infallible)
radio = mksafe(
  fallback(
    id="radio",
    track_sensitive=true,
    [radio_queue, fallback_playlist]
  )
)

# --- Salida hacia Icecast ---
output.icecast(
  %mp3(bitrate=128),
  host=environment.get("ICECAST_HOST"),
  port=int_of_string(environment.get("ICECAST_PORT")),
  password=environment.get("ICECAST_PASS"),
  mount=environment.get("ICECAST_MOUNT"),
  name="Radio Dev",
  description="AutoDJ con Liquidsoap",
  radio
)
