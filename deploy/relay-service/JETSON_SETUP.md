# Jetson RTSP Relay Service 部署說明

## 背景

測試階段架構：
- **VP (Visual Patrol)**: 在開發機 (WSL2) 上執行
- **Relay Service + mediamtx + VILA JPS**: 在 Jetson 上執行

VP 透過 gRPC 擷取機器人相機畫面，以 HTTP POST 送至 Jetson 上的 Relay Service。Relay Service 利用 Jetson GPU (NVENC) 硬體編碼後推送至 mediamtx，供 VILA JPS 分析。

```
開發機 (WSL2)                      Jetson (192.168.50.35)
┌──────────────────────┐          ┌─────────────────────────────────┐
│ VP Flask Backend     │          │                                 │
│  FrameFeederThread   │  HTTP    │ Relay Service (:5020)           │
│  gRPC frame grab     │ ──────> │  ffmpeg NVENC → mediamtx (:8555)│
│  → POST /frame       │         │                                 │
│                      │         │ mediamtx (:8555)                │
│                      │         │  → VILA JPS (:5010/:5016)       │
└──────────────────────┘         └─────────────────────────────────┘
```

## 前置條件

Jetson 上已有：
- Docker + NVIDIA runtime (`--runtime=nvidia`)
- mediamtx 在 `/code/mediamtx/` 執行中 (port 8555)
- VILA JPS 在 `/code/vila-jps/` 執行中 (port 5010/5016)

## 步驟

### 1. Clone 或更新 repo

```bash
# 如果還沒有 clone
cd /code
git clone https://github.com/sigma-snaken/visual-patrol.git
cd visual-patrol

# 如果已有
cd /code/visual-patrol
git pull
```

### 2. 建置 Relay Service Docker 映像

必須從 repo 根目錄執行 build（Dockerfile 中的 COPY 路徑相對於 repo root）：

```bash
cd /code/visual-patrol
docker build -f deploy/relay-service/Dockerfile -t visual-patrol-relay .
```

### 3. 確認 mediamtx 執行中

```bash
# 檢查 mediamtx 是否在 port 8555 監聽
ss -tlnp | grep 8555

# 如果沒有，啟動它
cd /code/mediamtx && docker compose up -d
```

### 4. 啟動 Relay Service

```bash
docker run -d --name visual_patrol_rtsp_relay \
  --runtime=nvidia \
  --network=host \
  -v /code/visual-patrol/deploy/logs:/app/logs \
  -e TZ=Asia/Taipei \
  -e RELAY_SERVICE_PORT=5020 \
  -e MEDIAMTX_HOST=localhost:8555 \
  -e USE_NVENC=true \
  --restart=unless-stopped \
  visual-patrol-relay
```

### 5. 驗證

```bash
# 健康檢查
curl http://localhost:5020/health
# 預期回應: {"status":"ok"}

# 檢查日誌
docker logs visual_patrol_rtsp_relay

# 測試外部 RTSP relay（如有外部攝影機）
curl -X POST http://localhost:5020/relays \
  -H 'Content-Type: application/json' \
  -d '{"key":"test/external","type":"external_rtsp","source_url":"rtsp://admin:pass@192.168.50.46:554/live/profile.1"}'

# 檢查串流就緒
curl "http://localhost:5020/relays/test%2Fexternal/ready?timeout=15"

# 停止測試 relay
curl -X POST http://localhost:5020/relays/stop_all
```

### 6. NVENC 測試

如果 NVENC 不可用（例如缺少 jetson-ffmpeg），可以先用軟體編碼測試：

```bash
# 停止並移除
docker rm -f visual_patrol_rtsp_relay

# 用軟體編碼重啟
docker run -d --name visual_patrol_rtsp_relay \
  --runtime=nvidia \
  --network=host \
  -v /code/visual-patrol/deploy/logs:/app/logs \
  -e TZ=Asia/Taipei \
  -e RELAY_SERVICE_PORT=5020 \
  -e MEDIAMTX_HOST=localhost:8555 \
  -e USE_NVENC=false \
  --restart=unless-stopped \
  visual-patrol-relay
```

## 常用指令

```bash
# 查看日誌
docker logs -f visual_patrol_rtsp_relay

# 重啟
docker restart visual_patrol_rtsp_relay

# 停止
docker stop visual_patrol_rtsp_relay

# 移除
docker rm -f visual_patrol_rtsp_relay

# 重新建置（程式碼更新後）
cd /code/visual-patrol && git pull
docker rm -f visual_patrol_rtsp_relay
docker build -f deploy/relay-service/Dockerfile -t visual-patrol-relay .
# 然後重新 docker run（見步驟 4）
```

## API 參考

| 方法 | 端點 | 說明 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `GET` | `/relays` | 列出所有 relay 狀態 |
| `POST` | `/relays` | 啟動 relay。Body: `{"key":"robot-a/camera","type":"robot_camera"}` 或 `{"key":"robot-a/external","type":"external_rtsp","source_url":"rtsp://..."}` |
| `POST` | `/relays/<key>/frame` | 送出一幀 JPEG（binary body）。僅 robot_camera 類型。 |
| `DELETE` | `/relays/<key>` | 停止指定 relay |
| `GET` | `/relays/<key>/ready?timeout=15` | 阻塞式串流就緒檢查 |
| `POST` | `/relays/stop_all` | 停止所有 relay |

## 疑難排解

| 問題 | 解決方案 |
|------|----------|
| `docker build` 失敗 `COPY` 找不到檔案 | 確認在 repo 根目錄 (`/code/visual-patrol`) 執行 build |
| health check 無回應 | 檢查 port 5020 是否被占用：`ss -tlnp \| grep 5020` |
| ffmpeg 立即退出 | 檢查 mediamtx 是否執行中：`ss -tlnp \| grep 8555` |
| NVENC 編碼失敗 | 確認 `--runtime=nvidia`；檢查 `ffmpeg -encoders \| grep nvmpi`；設 `USE_NVENC=false` 退回軟體編碼 |
| 串流 ready 但 JPS 收不到 | 確認 mediamtx 和 JPS 在同一 host network；用 `ffplay rtsp://localhost:8555/<key>` 測試 |
