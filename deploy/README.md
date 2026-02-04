# Deployment Guide

## Docker Compose (Recommended)

### Production Deployment

```bash
# Pull and run the latest image
docker compose -f deploy/docker-compose.prod.yaml up -d

# View logs
docker compose -f deploy/docker-compose.prod.yaml logs -f

# Stop
docker compose -f deploy/docker-compose.prod.yaml down
```

### Configuration

After starting, configure via web UI at `http://localhost:5000`:
1. Go to Settings tab
2. Enter Gemini API Key
3. Configure Robot IP
4. Save Settings

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
