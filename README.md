# Sigma Patrol

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-2.x-green)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange)

An autonomous robot patrol system integrating **Kachaka Robot** with **Google Gemini Vision AI** for intelligent environment monitoring and anomaly detection.

## Features

- **Autonomous Patrol** - Define waypoints and let the robot navigate automatically
- **AI-Powered Inspection** - Gemini Vision analyzes images for anomalies (falls, intruders, hazards)
- **Real-time Dashboard** - Live map, robot position, battery, dual camera streams
- **Scheduled Patrols** - Set recurring patrol times with day-of-week filtering
- **PDF Reports** - Generate downloadable patrol reports with images and AI analysis
- **Manual Control** - Web-based remote control with D-pad navigation
- **History & Analytics** - Browse past patrols with token usage statistics

## Quick Start (Docker)

```bash
# Start the service
docker-compose up --build -d

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

## Project Structure

```
Sigma-patrol/
├── src/
│   ├── backend/                 # Python Flask backend
│   │   ├── app.py              # REST API server
│   │   ├── patrol_service.py   # Patrol orchestration
│   │   ├── robot_service.py    # Kachaka robot interface
│   │   ├── ai_service.py       # Gemini AI integration
│   │   ├── pdf_service.py      # PDF report generation
│   │   ├── database.py         # SQLite management
│   │   ├── config.py           # Configuration paths
│   │   ├── utils.py            # Utilities (JSON, time, etc.)
│   │   ├── logger.py           # Timezone-aware logging
│   │   └── requirements.txt    # Python dependencies
│   │
│   └── frontend/               # Web UI
│       ├── templates/
│       │   └── index.html      # Single-page app
│       └── static/
│           ├── css/style.css   # Industrial HUD theme
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
└── docker-compose.yml
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
| `/api/camera/front` | GET | Front camera MJPEG stream |
| `/api/camera/back` | GET | Back camera MJPEG stream |

### Patrol Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/patrol/start` | POST | Start patrol |
| `/api/patrol/stop` | POST | Stop patrol |
| `/api/patrol/status` | GET | Current patrol status |
| `/api/patrol/schedule` | GET/POST | Manage scheduled patrols |
| `/api/patrol/results` | GET | Recent inspection results |

### Points & Settings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/points` | GET/POST/DELETE | Manage patrol waypoints |
| `/api/points/reorder` | POST | Reorder waypoints |
| `/api/points/from_robot` | GET | Import locations from robot |
| `/api/settings` | GET/POST | System settings |

### History & Reports
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/history` | GET | List all patrol runs |
| `/api/history/<run_id>` | GET | Patrol run details |
| `/api/report/<run_id>/pdf` | GET | Download PDF report |
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
    "gemini_model": "gemini-2.5-flash",
    "robot_ip": "192.168.50.133:26400",
    "timezone": "Asia/Taipei",
    "system_prompt": "You are a security robot...",
    "report_prompt": "Generate a patrol summary...",
    "turbo_mode": false
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

## Turbo Mode

Enable **Turbo Mode** in settings to queue AI inspections asynchronously. This allows the robot to continue moving while images are being analyzed, reducing total patrol time.

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

## License

Developed for Kachaka Robot Integration.
