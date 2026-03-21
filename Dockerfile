FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg curl && \
    curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp && \
    rm -rf /var/lib/apt/lists/*

RUN pip install flask requests

WORKDIR /app

COPY autodj.py .
COPY templates/ ./templates/
COPY static/ ./static/

CMD ["python", "-u", "autodj.py"]
