FROM nvcr.io/nvidia/l4t-base:r36.4.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir flask

# Build from repo root: docker build -f deploy/relay-service/Dockerfile .
COPY src/backend/relay_service.py /app/relay_service.py

WORKDIR /app

ENV RELAY_SERVICE_PORT=5020
ENV MEDIAMTX_HOST=localhost:8555
ENV USE_NVENC=true
ENV LOG_DIR=/app/logs

EXPOSE 5020

CMD ["python3", "relay_service.py"]
