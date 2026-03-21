FROM python:3.10-slim
FROM savonet/liquidsoap:v2.2.5

COPY radio.liq /app/radio.liq

RUN pip install flask requests

WORKDIR /app

COPY autodj.py .
COPY templates/ ./templates/
COPY static/ ./static/

CMD ["python", "-u", "autodj.py"]

