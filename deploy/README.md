# Deployment Guide

## Prerequisites

- Docker & Docker Compose
- Network access to GitHub Container Registry (`ghcr.io`)

## Fresh Install

不需要 clone 整個 repo，只需要兩個設定檔：

```bash
# 建立部署目錄
mkdir -p ~/visual-patrol && cd ~/visual-patrol

# 下載設定檔
curl -LO https://raw.githubusercontent.com/sigma-snaken/visual-patrol/main/deploy/docker-compose.prod.yaml
curl -LO https://raw.githubusercontent.com/sigma-snaken/visual-patrol/main/deploy/nginx.conf

# 修改機器人 IP 等設定
vim docker-compose.prod.yaml

# 啟動
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

`data/` 和 `logs/` 目錄會在首次啟動時自動建立，不需要手動建立。

## Update

```bash
cd ~/visual-patrol
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

## Common Commands

```bash
# View logs
docker compose -f docker-compose.prod.yaml logs -f

# Stop
docker compose -f docker-compose.prod.yaml down

# Restart single service
docker compose -f docker-compose.prod.yaml restart robot-a
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

## Directory Structure

部署後的目錄結構：

```
~/visual-patrol/
├── docker-compose.prod.yaml   # 服務定義（從 GHCR 拉 image）
├── nginx.conf                 # nginx 路由設定
├── data/                      # 自動產生 — DB、設定、巡檢圖片
│   ├── report/report.db       #   共用 SQLite 資料庫
│   └── robot-a/               #   每台機器人的資料
└── logs/                      # 自動產生 — 應用程式 log
```
