FROM python:3.10-slim

# Instalamos FFmpeg, que es el motor que procesará los mp3
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Instalamos Flask para el Dashboard web
RUN pip install flask

WORKDIR /app

# Copiamos los archivos al contenedor
COPY autodj.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Ejecutamos el script
CMD ["python","-u", "autodj.py"]
