# Visual Patrol

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.x-green)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange)
![Platform](https://img.shields.io/badge/Platform-amd64%20%7C%20arm64-lightgrey)

Autonomous robot patrol system integrating **Kachaka Robot** with **Google Gemini Vision AI** for intelligent environment monitoring and anomaly detection. Supports both x86 and ARM64 (NVIDIA Jetson) platforms.

## Features

- **Autonomous Patrol** - Define waypoints and let the robot navigate automatically
- **AI-Powered Inspection** - Gemini Vision analyzes images for anomalies (falls, intruders, hazards)
- **Video Recording** - Record patrol footage with codec auto-detection (H.264 / XVID / MJPEG)
- **Real-time Dashboard** - Live map, robot position, battery, dual camera streams
- **Scheduled Patrols** - Set recurring patrol times with day-of-week filtering
- **Multi-day Analysis Reports** - Generate AI-powered analysis reports for any date range
- **PDF Reports** - Server-side PDF generation with Markdown and CJK support
- **Manual Control** - Web-based remote control with D-pad navigation
- **History & Analytics** - Browse past patrols with token usage statistics

## Quick Start

```bash
# Docker Compose (recommended)
docker compose up -d

# Or pull from GitHub Container Registry
docker pull ghcr.io/sigma-snaken/visual-patrol:latest
docker run -d -p 5000:5000 -v vp-data:/app/data ghcr.io/sigma-snaken/visual-patrol:latest
```

Open [http://localhost:5000](http://localhost:5000), then go to **Settings** to configure:

1. **Google Gemini API Key**
2. **Robot IP** (default: `192.168.50.133:26400`)
3. **Timezone**

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────>│  Flask API  │────>│   Kachaka   │
│  Dashboard  │<────│  (app.py)   │<────│   Robot     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
               ┌───────────┼───────────┐
               v           v           v
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │  Patrol  │ │    AI    │ │   PDF    │
       │ Service  │ │ Service  │ │ Service  │
       └────┬─────┘ └────┬─────┘ └──────────┘
            │            │
            v            v
       ┌──────────┐ ┌──────────┐
       │  SQLite  │ │  Gemini  │
       │    DB    │ │   API    │
       └──────────┘ └──────────┘
```

## Project Structure

```
visual-patrol/
├── src/
│   ├── backend/
│   │   ├── app.py              # REST API server
│   │   ├── patrol_service.py   # Patrol orchestration
│   │   ├── robot_service.py    # Kachaka robot interface
│   │   ├── ai_service.py       # Gemini AI integration
│   │   ├── video_recorder.py   # Video recording with codec fallback
│   │   ├── pdf_service.py      # PDF report generation
│   │   ├── database.py         # SQLite management
│   │   ├── config.py           # Configuration
│   │   ├── utils.py            # Utilities
│   │   ├── logger.py           # Timezone-aware logging
│   │   └── requirements.txt
│   └── frontend/
│       ├── templates/
│       │   └── index.html
│       └── static/
│           ├── css/style.css
│           └── js/main.js
├── data/                       # Runtime data (Docker volume)
├── logs/                       # Application logs
├── tools/                      # Debug utilities
├── tests/                      # Unit tests
├── deploy/                     # Production compose file
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/          # CI/CD (multi-arch build)
```

## Local Development

```bash
uv pip install --system -r src/backend/requirements.txt

export DATA_DIR=$(pwd)/data
export LOG_DIR=$(pwd)/logs

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
| `/api/report/<run_id>/pdf` | GET | Download single patrol PDF |
| `/api/reports/generate` | POST | Generate multi-day analysis report |
| `/api/reports/generate/pdf` | GET | Download multi-day analysis PDF |
| `/api/stats/token_usage` | GET | Token usage by date |
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
        "x": 1.5, "y": 2.0, "theta": 0.0,
        "prompt": "Check for obstructions",
        "enabled": true
    }
]
```

## Deployment

Docker images are automatically built for **linux/amd64** and **linux/arm64** on every push to `main`.

```bash
# Production deployment
docker compose -f deploy/docker-compose.prod.yaml up -d

# Or pull manually
docker pull ghcr.io/sigma-snaken/visual-patrol:latest
```

See [deploy/README.md](deploy/README.md) for more details.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Robot disconnected | Verify robot IP in settings; ensure same network; check port 26400 |
| AI analysis failed | Verify Gemini API key; check `logs/ai_service.log`; ensure API quota |
| PDF generation failed | Check `logs/app.log`; verify images in `data/report/images/` |
| Camera stream not loading | Enable `enable_idle_stream` in settings; refresh page |

## License

Developed for Kachaka Robot Integration.
