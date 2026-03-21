FROM python:3.10-slim

RUN pip install flask requests

WORKDIR /app

COPY autodj.py .
COPY templates/ ./templates/
COPY static/ ./static/

CMD ["python", "-u", "autodj.py"]
