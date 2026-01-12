# Sigma Single Robot Patrol with Gemini

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.x-green)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange)

這是一個整合 **Kachaka 智慧機器人** 與 **Google Gemini AI** 的全自動巡邏檢測系統。機器人能夠依照設定的路線自動巡邏，拍攝關鍵地點的照片，並即時利用 AI 分析環境狀況，識別潛在異常。

## ✨ 主要功能

- **🚀 智慧巡邏**: 可設定多個巡邏點位，機器人自動導航並精確定位。
- **🧠 AI 環境檢測**: 整合 Google Gemini Vision 模型，對巡邏照片進行深度語意分析（例如：偵測跌倒、入侵者、物品遺失等）。
- **📊 即時監控儀表板**: 
  - 顯示機器人即時位置、電量、地圖。
  - 即時影像串流（前後鏡頭）。
  - 最新 AI 分析結果與 Token 使用量統計。
- **🎮 手動控制**: 支援網頁介面手動遙控機器人移動。
- **📝 完整的歷史紀錄**: 自動保存每次巡邏的詳細報告、照片與 AI 分析結果，並支援回放檢視。

## 📂 專案結構

此專案採用前後端分離架構，所有程式碼與設定檔皆組織於以下結構中：

```
my-ai-project/
├── src/
│   ├── backend/        # Python Flask 後端 API 服務
│   │   ├── app.py      # 主程式入口
│   │   ├── ai_service.py # Gemini AI 整合邏輯
│   │   ├── patrol_service.py # 巡邏流程控制
│   │   └── ...
│   └── frontend/       # Web 前端介面
│       ├── static/     # CSS, JS, Images
│       └── templates/  # HTML 模板
├── data/               # 資料儲存區 (Docker Volume)
│   ├── config/         # 設定檔 (points.json, settings.json)
│   ├── images/         # 巡邏拍攝的照片
│   └── database.db     # SQLite 資料庫 (儲存巡邏紀錄)
├── logs/               # 系統日誌
├── Dockerfile          # Docker 建置檔
└── docker-compose.yml  # Docker Compose 設定
```

## 🚀 快速開始 (Docker 推薦)

這是最簡單的部署方式，無需在本地安裝複雜的 Python 環境。

### 前置需求
1. 安裝 [Docker](https://www.docker.com/) 與 Docker Compose。
2. 確保電腦與 Kachaka 機器人位於 **同一區域網路 (Wi-Fi/LAN)** 下。

### 步驟

1. **啟動服務**
   在專案根目錄開啟終端機，執行：
   ```bash
   docker-compose up --build -d
   ```

2. **訪問網頁介面**
   打開瀏覽器訪問 [http://localhost:5000](http://localhost:5000)。

3. **系統設定**
   - 進入「檢測設定」頁面。
   - 輸入您的 **Google Gemini API Key**。
   - 輸入 **Kachaka 機器人 IP**。
   - 儲存設定後，系統即準備就緒。

4. **查看日誌 (Optional)**
   若需除錯，可執行：
   ```bash
   docker-compose logs -f
   ```

## 🛠️ 本地開發 (Local Development)

若您是開發者，希望修改程式碼進行測試：

1. **安裝 Python 依賴**
   ```bash
   pip install -r src/backend/requirements.txt
   ```

2. **設定環境變數並執行**
   Linux / macOS:
   ```bash
   export DATA_DIR=$(pwd)/data
   export LOG_DIR=$(pwd)/logs
   python src/backend/app.py
   ```
   
   Windows (PowerShell):
   ```powershell
   $env:DATA_DIR="$(Get-Location)\data"
   $env:LOG_DIR="$(Get-Location)\logs"
   python src/backend/app.py
   ```

## 🧩 技術細節

### 後端 (Backend)
- **Framework**: Flask
- **Database**: SQLite (透過 `sqlite3` 與 `database.py` 管理)
- **AI Integration**: Google Generative AI Python SDK (`google-generativeai`)
- **Robot Control**: `kachaka-api` gRPC client
- **Concurrency**: 使用 Threading 處理背景巡邏任務與機器人狀態輪詢。

### 前端 (Frontend)
- **Technologies**: HTML5, CSS3, Vanilla JavaScript.
- **Data Flow**: 透過 RESTful API 與後端溝通，使用 Polling 機制更新即時狀態。

### 連線機制
- 系統會自動嘗試連線機器人，若斷線會每 2 秒重試一次。
- 狀態更新頻率為 10Hz (每 0.1 秒)。

## ❓ 常見問題 (Troubleshooting)

**Q: 介面顯示 "Robot Disconnected"?**
- 請確認機器人 IP 設定正確。
- 請確認電腦與機器人在同一網域。
- 若使用 Docker，請確認 Docker 網路設定無誤（預設 bridge 模式通常可行，若有問題可嘗試 `network_mode: host`，注意 host 模式僅支援 Linux）。

**Q: AI 分析失敗?**
- 請確認 API Key 是否有效。
- 檢查 `logs/app.log` 查看詳細錯誤訊息。

---
Developed for Kachaka Robot Integration. 2026.
