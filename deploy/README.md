# Deployment Guide

## Quick Start

```bash
cd deploy

# Pull and run
docker compose -f docker-compose.prod.yaml up -d

# View logs
docker compose -f docker-compose.prod.yaml logs -f

# Stop
docker compose -f docker-compose.prod.yaml down
```

Open `http://localhost:5000`, go to **Settings** to configure your Gemini API Key.

## Configuration

Edit `docker-compose.prod.yaml` to set your robot's IP:

```yaml
environment:
  - ROBOT_ID=robot-a
  - ROBOT_NAME=Robot A
  - ROBOT_IP=192.168.50.133:26400    # ← your robot's IP:port
```

## Adding More Robots

1. Add a new service to `docker-compose.prod.yaml` with a unique `PORT`:

```yaml
  robot-b:
    container_name: visual_patrol_robot_b
    image: ghcr.io/sigma-snaken/visual-patrol:latest
    network_mode: host
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DATA_DIR=/app/data
      - LOG_DIR=/app/logs
      - TZ=Asia/Taipei
      - PORT=5002
      - ROBOT_ID=robot-b
      - ROBOT_NAME=Robot B
      - ROBOT_IP=192.168.50.134:26400
    restart: unless-stopped
```

2. Add the backend to `nginx.conf`:

```nginx
    # In the robot-specific location block, add routing by robot ID:
    location ~ ^/api/(robot-b)/(.*)$ {
        proxy_pass http://127.0.0.1:5002/api/$2$is_args$args;
        ...
    }
```

3. Run `docker compose -f docker-compose.prod.yaml up -d`.

> Each robot backend needs a unique `PORT` (5001, 5002, ...) since all containers share the host network.

## Docker Image

The image is automatically built and pushed to GitHub Container Registry on every push to `main`.

**Pull manually:**
```bash
docker pull ghcr.io/sigma-snaken/visual-patrol:latest
```

**Available tags:**
- `latest` - Latest main branch
- `main` - Main branch
- `v1.0.0` - Semantic version tags
