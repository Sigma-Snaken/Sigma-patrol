# Visual Patrol

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange)
![Platform](https://img.shields.io/badge/Platform-amd64%20%7C%20arm64-lightgrey)

Autonomous multi-robot patrol system integrating **Kachaka Robot** with **Google Gemini Vision AI** for intelligent environment monitoring and anomaly detection. A single web dashboard controls multiple robots through an nginx reverse proxy, with each robot running an isolated Flask backend sharing a common SQLite database.

## Features

- **Multi-Robot Support** - Single dashboard controls multiple robots via dropdown selector
- **Autonomous Patrol** - Define waypoints per robot and let them navigate automatically
- **AI-Powered Inspection** - Gemini Vision analyzes camera images at each waypoint
- **Video Recording** - Record patrol footage with codec auto-detection (H.264 / XVID / MJPEG)
- **Real-time Dashboard** - Live map, robot position, battery, camera streams
- **Scheduled Patrols** - Recurring patrol times with day-of-week filtering
- **Multi-day Analysis Reports** - AI-powered aggregated reports across date ranges
- **PDF Reports** - Server-side PDF generation with Markdown and CJK support
- **Telegram Notifications** - Send patrol reports and PDFs to Telegram on completion
- **Manual Control** - Web-based remote control with D-pad navigation
- **History & Analytics** - Browse past patrols with token usage statistics and robot filtering

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Browser (http://localhost:5000)                     │
│  ├── Robot selector dropdown                         │
│  ├── /api/{robot-id}/state  → robot-specific calls   │
│  └── /api/settings          → global calls           │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  nginx (port 5000)                                   │
│  ├── /              → index.html (static)            │
│  ├── /static/       → CSS / JS assets                │
│  ├── /api/{robot-id}/...  → proxy to backend         │
│  └── /api/...       → proxy to robot-a (global)      │
├─────────────────────────────────────────────────────┤
│  robot-a (Flask:5000)  ←→  Kachaka Robot A           │
│  robot-b (Flask:5000)  ←→  Kachaka Robot B           │
│  robot-c (Flask:5000)  ←→  Kachaka Robot C           │
│  (all share ./data volume with SQLite WAL)           │
└─────────────────────────────────────────────────────┘
```

- nginx regex `^/api/(robot-[^/]+)/(.*)$` strips the robot ID and proxies to the matching Docker service
- Docker service names **must** match robot IDs (`robot-a`, `robot-b`, etc.)
- Global endpoints (`/api/settings`, `/api/robots`, `/api/history`, `/api/stats`) proxy to any backend (shared DB)
- Adding a robot = add a service to `docker-compose.yml` + restart

## Quick Start

```bash
docker compose up -d
```

Open [http://localhost:5000](http://localhost:5000), go to **Settings** and configure:

1. **Google Gemini API Key**
2. **Timezone**

Robot IPs are set per-service in `docker-compose.yml` via the `ROBOT_IP` environment variable.

### Adding a New Robot

Add a new service to `docker-compose.yml`:

```yaml
  robot-d:
    container_name: visual_patrol_robot_d
    build: .
    volumes:
      - ./src:/app/src
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DATA_DIR=/app/data
      - LOG_DIR=/app/logs
      - TZ=Asia/Taipei
      - ROBOT_ID=robot-d
      - ROBOT_NAME=Robot D
      - ROBOT_IP=192.168.50.135:26400
    restart: unless-stopped
```

Add `robot-d` to the nginx `depends_on` list, then `docker compose up -d`.

## Project Structure

```
visual-patrol/
├── nginx.conf                  # Dev reverse proxy config
├── docker-compose.yml          # Dev: nginx + per-robot services (bridge network)
├── Dockerfile                  # Backend image (Python 3.10, non-root user)
├── .dockerignore
├── src/
│   ├── backend/
│   │   ├── app.py              # Flask REST API
│   │   ├── robot_service.py    # Kachaka gRPC interface
│   │   ├── patrol_service.py   # Patrol orchestration
│   │   ├── ai_service.py       # Gemini AI integration
│   │   ├── settings_service.py # Global settings (DB-backed)
│   │   ├── pdf_service.py      # PDF report generation
│   │   ├── database.py         # SQLite management
│   │   ├── config.py           # Per-robot env config
│   │   ├── video_recorder.py   # Video recording
│   │   ├── utils.py            # Utilities
│   │   ├── logger.py           # Timezone-aware logging
│   │   └── requirements.txt
│   └── frontend/
│       ├── templates/
│       │   └── index.html      # SPA (static, no Jinja2)
│       └── static/
│           ├── css/style.css
│           └── js/
│               ├── app.js      # Entry point, tab switching, robot selector
│               ├── state.js    # Shared state hub
│               ├── map.js      # Canvas map rendering
│               ├── controls.js # Manual D-pad control
│               ├── patrol.js   # Patrol start/stop, status polling
│               ├── points.js   # Waypoint CRUD
│               ├── schedule.js # Scheduled patrols
│               ├── ai.js       # AI test panel
│               ├── history.js  # Patrol history & reports
│               ├── settings.js # Settings panel
│               └── stats.js    # Token usage chart
├── data/                       # Shared runtime data (SQLite DB, images)
├── logs/                       # Per-robot application logs
├── deploy/                     # Production config (host networking)
│   ├── docker-compose.prod.yaml
│   ├── nginx.conf
│   └── README.md
└── .github/workflows/          # CI/CD (multi-arch build → GHCR)
```

## API Reference

### URL Convention

- **Robot-specific**: `/api/{robot-id}/endpoint` — nginx strips the robot ID prefix before proxying
- **Global**: `/api/endpoint` — proxied to any backend (shared DB)

### Robot Control (robot-specific)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/{id}/state` | GET | Robot status (battery, pose, map) |
| `/api/{id}/map` | GET | PNG map image |
| `/api/{id}/move` | POST | Move to coordinates `{x, y, theta}` |
| `/api/{id}/manual_control` | POST | D-pad control `{action}` |
| `/api/{id}/return_home` | POST | Return to charging station |
| `/api/{id}/cancel_command` | POST | Cancel current movement |
| `/api/{id}/camera/front` | GET | Front camera MJPEG stream |
| `/api/{id}/camera/back` | GET | Back camera MJPEG stream |

### Patrol Management (robot-specific)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/{id}/patrol/start` | POST | Start patrol |
| `/api/{id}/patrol/stop` | POST | Stop patrol |
| `/api/{id}/patrol/status` | GET | Current patrol status |
| `/api/{id}/patrol/schedule` | GET/POST | Manage scheduled patrols |
| `/api/{id}/patrol/schedule/{sid}` | PUT/DELETE | Update or delete schedule |
| `/api/{id}/patrol/results` | GET | Current run inspection results |

### Points (robot-specific)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/{id}/points` | GET/POST/DELETE | Manage patrol waypoints |
| `/api/{id}/points/reorder` | POST | Reorder waypoints |
| `/api/{id}/points/export` | GET | Export points as JSON |
| `/api/{id}/points/import` | POST | Import points from JSON file |
| `/api/{id}/points/from_robot` | GET | Import saved locations from robot |
| `/api/{id}/test_ai` | POST | Test AI on current camera frame |

### Global Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/settings` | GET/POST | System settings (sensitive fields masked in GET) |
| `/api/robots` | GET | All registered robots with online status |
| `/api/history` | GET | Patrol history (`?robot_id=` filter) |
| `/api/history/{run_id}` | GET | Patrol run detail with inspections |
| `/api/report/{run_id}/pdf` | GET | Download single patrol PDF |
| `/api/reports/generate` | POST | Generate multi-day analysis report |
| `/api/reports/generate/pdf` | GET | Download multi-day analysis PDF |
| `/api/stats/token_usage` | GET | Token usage by date (`?robot_id=` filter) |

## Configuration

Settings are stored in a shared SQLite database (`data/report/report.db`, table `global_settings`) and managed through the web UI Settings page.

| Setting | Description |
|---------|-------------|
| `gemini_api_key` | Google Gemini API key |
| `gemini_model` | AI model name (e.g. `gemini-2.0-flash`) |
| `timezone` | Display timezone (e.g. `Asia/Taipei`) |
| `system_prompt` | AI system role prompt |
| `report_prompt` | Single patrol report generation prompt |
| `multiday_report_prompt` | Multi-day aggregated report prompt |
| `turbo_mode` | Async AI analysis (robot moves while images process) |
| `enable_video_recording` | Record patrol video |
| `video_prompt` | Video analysis prompt |
| `enable_idle_stream` | Camera stream when not patrolling |
| `enable_telegram` | Telegram notifications on patrol completion |
| `telegram_bot_token` / `telegram_user_id` | Telegram config |

Per-robot settings (`ROBOT_ID`, `ROBOT_NAME`, `ROBOT_IP`) are set via environment variables in `docker-compose.yml`.

## Deployment

Docker images are automatically built for **linux/amd64** and **linux/arm64** on every push to `main`.

```bash
# Production (host networking, for Jetson / Linux)
docker compose -f deploy/docker-compose.prod.yaml up -d
```

See [deploy/README.md](deploy/README.md) for production setup including multi-robot configuration.

## Local Development

```bash
uv pip install --system -r src/backend/requirements.txt

export DATA_DIR=$(pwd)/data
export LOG_DIR=$(pwd)/logs
export ROBOT_ID=robot-a
export ROBOT_NAME="Robot A"
export ROBOT_IP=192.168.50.133:26400

python src/backend/app.py
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Robot shows "offline" | Check `ROBOT_IP` in docker-compose.yml; ensure robot is on same network |
| Robot dropdown empty | Verify backends are running: `docker compose ps` |
| AI analysis failed | Verify Gemini API key in Settings; check `logs/{robot-id}_ai_service.log` |
| PDF generation failed | Check `logs/{robot-id}_app.log` |
| Camera stream not loading | Enable "Continuous Camera Stream" in Settings; check robot connection |
| Map not loading | Robot may still be connecting; check container logs for gRPC errors |

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- [Architecture Overview](docs/architecture.md) -- System design, request flow, threading model, networking
- [API Reference](docs/api-reference.md) -- All REST endpoints with request/response examples
- [Frontend Guide](docs/frontend.md) -- Module structure, state management, UI patterns
- [Backend Guide](docs/backend.md) -- Services, database schema, startup sequence
- [Deployment Guide](docs/deployment.md) -- Dev and production setup, Docker, adding robots
- [Configuration](docs/configuration.md) -- Environment variables, settings, per-robot config files

## License

Copyright (c) 2026 Sigma Robotics. All rights reserved.
