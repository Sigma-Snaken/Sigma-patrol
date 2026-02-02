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

## Kubernetes

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- nginx-ingress controller (optional, for Ingress)

### Deploy

```bash
# Apply all resources
kubectl apply -f deploy/kubernetes/deployment.yaml

# Check status
kubectl get pods -n sigma-patrol
kubectl get svc -n sigma-patrol

# View logs
kubectl logs -f deployment/sigma-patrol -n sigma-patrol
```

### Configure Secrets

```bash
# Set your Gemini API Key
kubectl create secret generic sigma-patrol-secrets \
  --from-literal=GEMINI_API_KEY=your-api-key \
  -n sigma-patrol \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Access

**Port Forward (Development)**
```bash
kubectl port-forward svc/sigma-patrol 5000:80 -n sigma-patrol
```

**Ingress (Production)**
Update `patrol.example.com` in `deployment.yaml` to your domain.

### Cleanup

```bash
kubectl delete -f deploy/kubernetes/deployment.yaml
```

## Docker Image

The image is automatically built and pushed to GitHub Container Registry on every push to `main`.

**Pull manually:**
```bash
docker pull ghcr.io/sigma-snaken/sigma-patrol:latest
```

**Available tags:**
- `latest` - Latest main branch
- `main` - Main branch
- `v1.0.0` - Semantic version tags
