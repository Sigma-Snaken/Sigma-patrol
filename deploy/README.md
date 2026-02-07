# Production Deployment

See the full [Deployment Guide](../docs/deployment.md) for setup instructions, multi-robot configuration, mediamtx RTSP relay setup, and troubleshooting.

## Quick Start

```bash
mkdir -p ~/visual-patrol && cd ~/visual-patrol

curl -LO https://raw.githubusercontent.com/sigma-snaken/visual-patrol/main/deploy/docker-compose.prod.yaml
curl -LO https://raw.githubusercontent.com/sigma-snaken/visual-patrol/main/deploy/nginx.conf

vim docker-compose.prod.yaml   # Edit robot IPs, ports, mediamtx config

docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

## Update

```bash
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```
