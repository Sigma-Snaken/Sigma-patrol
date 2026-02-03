# Sigma Patrol

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.x-green)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange)

An autonomous robot patrol system integrating **Kachaka Robot** with **Google Gemini Vision AI** for intelligent environment monitoring and anomaly detection.

## Features

- **Autonomous Patrol** - Define waypoints and let the robot navigate automatically
- **AI-Powered Inspection** - Gemini Vision analyzes images for anomalies (falls, intruders, hazards)
- **Video Recording** - Record patrol footage with AI video analysis
- **Real-time Dashboard** - Live map, robot position, battery, dual camera streams
- **Scheduled Patrols** - Set recurring patrol times with day-of-week filtering
- **Multi-day Analysis Reports** - Generate AI-powered analysis reports for any date range
- **Unified PDF Reports** - Server-side PDF generation with full Markdown support (tables, lists, code blocks)
- **Manual Control** - Web-based remote control with D-pad navigation
- **History & Analytics** - Browse past patrols with token usage statistics
- **Chinese Language Support** - Full CJK font support in PDF reports

## Quick Start (Docker)

```bash
# Pull and run from GitHub Container Registry
docker pull ghcr.io/sigma-snaken/sigma-patrol:latest
docker run -d -p 5000:5000 -v sigma-data:/app/data ghcr.io/sigma-snaken/sigma-patrol:latest

# Or use docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

Access the web interface at [http://localhost:5000](http://localhost:5000)

### Initial Setup

1. Go to **Settings** tab
2. Enter your **Google Gemini API Key**
3. Configure **Robot IP** (default: `192.168.50.133:26400`)
4. Set your **Timezone**
5. Click **Save Settings**

## Screenshots

| Patrol Dashboard | History & Reports |
|------------------|-------------------|
| Live map with robot position, camera feeds, and patrol status | Browse past patrols and generate multi-day analysis reports |

## Project Structure

```
Sigma-patrol/
├── src/
│   ├── backend/                 # Python Flask backend
│   │   ├── app.py              # REST API server
│   │   ├── patrol_service.py   # Patrol orchestration
│   │   ├── robot_service.py    # Kachaka robot interface
│   │   ├── ai_service.py       # Gemini AI integration
│   │   ├── pdf_service.py      # PDF report generation (ReportLab)
│   │   ├── database.py         # SQLite management
│   │   ├── config.py           # Configuration & defaults
│   │   ├── utils.py            # Utilities (JSON, time, etc.)
│   │   ├── logger.py           # Timezone-aware logging
│   │   └── requirements.txt    # Python dependencies
│   │
│   └── frontend/               # Web UI
│       ├── templates/
│       │   └── index.html      # Single-page app
│       └── static/
│           ├── css/style.css   # Light mode cream/beige theme
│           └── js/main.js      # UI logic
│
├── data/                       # Runtime data (Docker volume)
│   ├── config/
│   │   ├── points.json         # Patrol waypoints
│   │   └── settings.json       # System settings
│   ├── patrol_schedule.json    # Scheduled patrols
│   └── report/
│       ├── report.db           # SQLite database
│       └── images/             # Captured patrol images
│
├── logs/                       # Application logs
├── tools/                      # Debug & inspection utilities
├── tests/                      # Unit tests
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/          # CI/CD pipelines
    └── docker-publish.yaml     # Auto-build Docker images
```

## Local Development

```bash
# Install dependencies
pip install -r src/backend/requirements.txt

# Set environment variables
export DATA_DIR=$(pwd)/data
export LOG_DIR=$(pwd)/logs

# Run the server
python src/backend/app.py
```

## API Reference

### Robot Control
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Robot status (battery, pose, map) |
| `/api/map` | GET | PNG map image |
| `/api/move` | POST | Move to coordinates `{x, y, theta}` |
| `/api/manual_control` | POST | D-pad control `{action}` |
| `/api/return_home` | POST | Return to charging station |
| `/api/cancel_command` | POST | Cancel current movement |
| `/api/camera/front` | GET | Front camera MJPEG stream |
| `/api/camera/back` | GET | Back camera MJPEG stream |

### Patrol Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patrol/start` | POST | Start patrol |
| `/api/patrol/stop` | POST | Stop patrol |
| `/api/patrol/status` | GET | Current patrol status |
| `/api/patrol/schedule` | GET/POST | Manage scheduled patrols |
| `/api/patrol/schedule/<id>` | PUT/DELETE | Update or delete schedule |
| `/api/patrol/results` | GET | Recent inspection results |

### Points & Settings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/points` | GET/POST/DELETE | Manage patrol waypoints |
| `/api/points/reorder` | POST | Reorder waypoints |
| `/api/points/export` | GET | Export points as JSON |
| `/api/points/import` | POST | Import points from JSON |
| `/api/points/from_robot` | GET | Import locations from robot |
| `/api/settings` | GET/POST | System settings |

### History & Reports
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/history` | GET | List all patrol runs |
| `/api/history/<run_id>` | GET | Patrol run details |
| `/api/report/<run_id>/pdf` | GET | Download single patrol PDF report |
| `/api/reports/generate` | POST | Generate multi-day analysis report |
| `/api/reports/generate/pdf` | GET | Download multi-day analysis PDF |
| `/api/stats/token_usage` | GET | Token usage by date |

### AI Testing
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/test_ai` | POST | Test AI on current camera frame |

## Configuration

### settings.json
```json
{
    "gemini_api_key": "your-api-key",
    "gemini_model": "gemini-2.0-flash",
    "robot_ip": "192.168.50.133:26400",
    "timezone": "Asia/Taipei",
    "system_prompt": "You are a security robot...",
    "report_prompt": "Generate a patrol summary...",
    "multiday_report_prompt": "Generate a comprehensive analysis...",
    "turbo_mode": false,
    "enable_video_recording": false,
    "video_prompt": "Analyze this patrol video...",
    "enable_idle_stream": true
}
```

### points.json
```json
[
    {
        "id": "unique-id",
        "name": "Entrance",
        "x": 1.5,
        "y": 2.0,
        "theta": 0.0,
        "prompt": "Check for obstructions",
        "enabled": true
    }
]
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  Flask API  │────▶│   Kachaka   │
│  (main.js)  │◀────│  (app.py)   │◀────│   Robot     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │  Patrol  │ │    AI    │ │   PDF    │
      │ Service  │ │ Service  │ │ Service  │
      └────┬─────┘ └────┬─────┘ └──────────┘
           │            │
           ▼            ▼
      ┌──────────┐ ┌──────────┐
      │  SQLite  │ │  Gemini  │
      │    DB    │ │   API    │
      └──────────┘ └──────────┘
```

## Key Features Explained

### Turbo Mode
Enable **Turbo Mode** in settings to queue AI inspections asynchronously. This allows the robot to continue moving while images are being analyzed, reducing total patrol time.

### Video Recording
When enabled, the system records video during patrols for later AI analysis. Configure the video analysis prompt in settings to customize what the AI looks for in recorded footage.

### Multi-day Analysis Reports
Generate comprehensive reports spanning any date range:
1. Go to **History** tab
2. Select start and end dates
3. Click **Generate Report**
4. Download as PDF with full Markdown formatting

### PDF Report Features
- Professional layout with consistent styling
- Full Markdown support (headers, tables, lists, code blocks, blockquotes)
- Chinese/CJK character support (STSong-Light font)
- Embedded inspection images
- Page numbers and footers
- Server-side generation (no browser dependency)

## Troubleshooting

**Robot Disconnected**
- Verify robot IP in settings
- Ensure same network as robot
- Check if Kachaka API port (26400) is accessible

**AI Analysis Failed**
- Verify Gemini API key is valid
- Check `logs/ai_service.log` for errors
- Ensure sufficient API quota

**PDF Generation Failed**
- Check `logs/app.log` for errors
- Verify images exist in `data/report/images/`
- For Chinese text issues, ensure CJK fonts are available

**Camera Stream Not Loading**
- Check if `enable_idle_stream` is enabled in settings
- Verify robot camera is accessible
- Try refreshing the page

## CI/CD

Docker images are automatically built and pushed to GitHub Container Registry on every push to `main`:

```bash
# Pull the latest image
docker pull ghcr.io/sigma-snaken/sigma-patrol:latest
```

## License

Developed for Kachaka Robot Integration.
