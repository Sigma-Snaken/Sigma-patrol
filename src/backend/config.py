import os

ROBOT_IP = "192.168.50.133:26400"

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))

CONFIG_DIR = os.path.join(DATA_DIR, "config")
REPORT_DIR = os.path.join(DATA_DIR, "report")
IMAGES_DIR = os.path.join(REPORT_DIR, "images")

POINTS_FILE = os.path.join(CONFIG_DIR, "points.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
RESULTS_FILE = os.path.join(REPORT_DIR, "results.json")
DB_FILE = os.path.join(REPORT_DIR, "report.db")

DEFAULT_SETTINGS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-3-flash-preview",
    "system_prompt": "You are a helpful robot assistant. Analyze this image from my patrol.",
    "timezone": "UTC",
    "enable_video_recording": False,
    "video_prompt": "Analyze this video of a robot patrol. Identify any safety hazards, obstacles, or anomalies.",
    "enable_idle_stream": True,
    "report_prompt": """**任務：填寫巡檢報告表**

**背景資訊/表格結構：**
以下是本次巡檢的項目清單。請以這個結構為基礎，進行評估與填寫。

| 類別 (Category) | 編號 (No.) | 巡檢項目 (Check Item) | 
| :--- | :--- | :--- |
| 用電安全 | 1 | 公共區域電氣設備使用完畢是否依程序關閉—廁所及走廊 |
| 用電安全 | 2 | 公共區域是否不當使用插座—辨識公共插座是否沒有插線 |
| 室內環境 | 1 | 是否沒有物品掉落阻礙通行 |
| 室內環境 | 2 | 室內照明是否足夠 |
| 防災避難設施 | 1 | 有效光不足場域緊急照明設備是否有正常操作 |
| 防災避難設施 | 2 | 室內裝設有避難指標或避難方向指示燈是否正常運作 |
| 防災避難設施 | 3 | 滅火器是否放置到位位置 |
| 防災避難設施 | 4 | 逃生通道是否無障礙物 |
| 其他 | 1 | 是否有偵測到人體跌倒? |
| 其他 | 2 | 夜間關懷—深夜辦公室電燈未關? |

**指令：**
請以表格形式輸出巡檢結果。除了原有的「類別」、「編號」和「巡檢項目」三欄外，請務必新增以下兩欄：
1.  **結果 (Result)：** 填寫「**O**」（表示符合/正常）或「**X**」（表示不符合/異常）。
2.  **備註/異常說明 (Notes)：** 詳細說明任何標記為「X」的項目，或需要注意的事項。

**請以一個完整的 Markdown 表格呈現最終的巡檢報告。**"""
}

def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
