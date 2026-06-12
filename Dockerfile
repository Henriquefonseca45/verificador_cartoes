FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py clients_colors.json logo_rvb.png ./
COPY static ./static
COPY templates ./templates

RUN mkdir -p /data/jobs

EXPOSE 8080
VOLUME ["/data"]

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "300", "web_app:app"]
