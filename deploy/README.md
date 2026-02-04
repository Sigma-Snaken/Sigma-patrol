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

1. Add a new service to `docker-compose.prod.yaml`:

```yaml
  robot-b:
    container_name: visual_patrol_robot_b
    image: ghcr.io/sigma-snaken/visual-patrol:latest
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DATA_DIR=/app/data
      - LOG_DIR=/app/logs
      - TZ=Asia/Taipei
      - ROBOT_ID=robot-b
      - ROBOT_NAME=Robot B
      - ROBOT_IP=192.168.50.134:26400
    restart: unless-stopped
```

2. Add `robot-b` to the nginx `depends_on` list.
3. Run `docker compose -f docker-compose.prod.yaml up -d`.

> Service name **must** match `ROBOT_ID` (e.g. `robot-b`). nginx uses the Docker service name to route requests.

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
