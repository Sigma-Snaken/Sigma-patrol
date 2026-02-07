# Production Deployment

See the full [Deployment Guide](../docs/deployment.md) for setup instructions, multi-robot configuration, mediamtx RTSP relay setup, and troubleshooting.

## Quick Start

```bash
mkdir -p ~/visual-patrol && cd ~/visual-patrol

curl -LO https://raw.githubusercontent.com/sigma-snaken/visual-patrol/main/deploy/docker-compose.prod.yaml
curl -LO https://raw.githubusercontent.com/sigma-snaken/visual-patrol/main/deploy/nginx.conf

vim docker-compose.prod.yaml   # Edit robot IPs and ports

docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

## Update

```bash
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

## RTSP Relay Service (Jetson only)

The relay service runs on Jetson for GPU-accelerated video encoding. Build locally:

```bash
cd /code/visual-patrol
git pull
docker build -f deploy/relay-service/Dockerfile -t visual-patrol-relay .
docker compose -f deploy/docker-compose.prod.yaml up -d rtsp-relay
```

See [Deployment Guide - RTSP Relay Service](../docs/deployment.md#rtsp-relay-service-jetson-gpu-encoding) for details.
