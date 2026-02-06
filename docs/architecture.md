# System Architecture

## Overview

Visual Patrol is a multi-robot autonomous inspection system. A web-based single-page application (SPA) connects through an nginx reverse proxy to per-robot Flask backend instances, all sharing a common SQLite database.

```
                           Browser (SPA)
                               |
                       nginx (port 5000)
                      /        |        \
               robot-a     robot-b     robot-c
              Flask:5000  Flask:5000  Flask:5000
                 |            |           |
              Kachaka A    Kachaka B   Kachaka C
                 \            |          /
                  \           |         /
                   Shared SQLite DB (WAL)
                     data/report/report.db
```

## Component Breakdown

### Frontend (SPA)

- **Location**: `src/frontend/`
- **Served by**: nginx (static files) or Flask (fallback in dev)
- **Technology**: Vanilla JavaScript ES modules, no framework
- **Entry point**: `src/frontend/templates/index.html`
- **JS entry**: `src/frontend/static/js/app.js`

The frontend is a single HTML page with tab-based navigation. All views (Control, Patrol, History, Stats, Settings) exist in the DOM and are shown/hidden via `switchTab()`. The map canvas is physically reparented between the Control and Patrol tabs to avoid maintaining duplicate canvas state.

### Backend (Flask)

- **Location**: `src/backend/`
- **Entry point**: `src/backend/app.py`
- **Runtime**: Python 3.10+, Flask 3.x

Each robot runs its own Flask process. The backend handles:
- REST API for the frontend
- gRPC communication with Kachaka robots via `kachaka-api`
- AI inference through Google Gemini API
- Patrol orchestration (movement, image capture, AI analysis)
- PDF report generation
- Telegram notifications
- Video recording during patrols
- Live camera monitoring via VILA Alert API during patrols

### Reverse Proxy (nginx)

- **Dev config**: `nginx.conf` (root)
- **Prod config**: `deploy/nginx.conf`

nginx performs two functions:
1. Serves static frontend assets directly (faster than Flask)
2. Routes API requests to the correct backend based on URL pattern

### Database (SQLite)

- **File**: `data/report/report.db`
- **Mode**: WAL (Write-Ahead Logging) for concurrent read/write from multiple processes
- **Busy timeout**: 5000ms

All robot backends share a single database file. The `robot_id` column in each table distinguishes data per robot.

## Request Flow

### Robot-Specific Requests

```
Browser:  GET /api/robot-a/state
    |
nginx:    Regex match ^/api/(robot-a)/(.*)$
          Strips prefix, proxies to http://robot-a:5000/api/state
    |
Flask:    Handles /api/state, returns robot-specific data
```

### Global Requests

```
Browser:  GET /api/settings
    |
nginx:    Falls through to /api/ catch-all
          Proxies to http://robot-a:5000/api/settings
    |
Flask:    Reads from shared SQLite DB, returns settings
```

Any backend can serve global requests because they all share the same database.

## Data Model

### Per-Robot Data (filesystem)

Each robot stores its own configuration and images:

```
data/
├── report/
│   └── report.db              # Shared database
├── robot-a/
│   ├── config/
│   │   ├── points.json        # Patrol waypoints
│   │   └── patrol_schedule.json
│   └── report/
│       ├── images/            # Inspection photos
│       │   └── {run_id}_{timestamp}/
│       └── live_alerts/       # Live monitor evidence images
├── robot-b/
│   └── ...
```

### Shared Data (database)

See [backend.md](backend.md) for the full database schema.

## Threading Model

Each Flask backend runs several background threads:

| Thread | Purpose | Interval |
|--------|---------|----------|
| `_polling_loop` (robot_service) | Polls robot pose, battery, map via gRPC | 100ms |
| `_heartbeat_loop` (app.py) | Updates robot online status in DB | 30s |
| `_schedule_checker` (patrol_service) | Checks for scheduled patrol times | 30s |
| `_inspection_worker` (patrol_service) | Processes AI inspection queue | Event-driven |
| `_record_loop` (video_recorder) | Captures video frames during patrol | 1/fps |
| `_monitor_loop` (live_monitor) | Sends frames to VILA Alert API during patrol | Configurable (default 5s) |

## Networking Modes

### Development (WSL2 / Docker Desktop)

Uses Docker bridge networking:

- nginx binds `ports: 5000:5000`
- All Flask backends listen on port 5000 internally
- nginx resolves backend hostnames via Docker DNS (`resolver 127.0.0.11`)
- Docker service names must match `ROBOT_ID` values (e.g., service `robot-a` = `ROBOT_ID=robot-a`)

### Production (Jetson / Linux host)

Uses host networking (`network_mode: host`):

- All containers share the host network stack
- nginx listens on port 5000
- Each Flask backend uses a unique port via `PORT` env var (5001, 5002, ...)
- nginx routes by robot ID using explicit proxy rules to `127.0.0.1:PORT`

See [deployment.md](deployment.md) for details.

## Security

- nginx adds security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- Sensitive settings (API keys, Telegram tokens) are masked in GET responses (`****` prefix)
- Robot ID path parameters are validated against `^robot-[a-z0-9-]+$`
- Image serving validates robot ID format before constructing filesystem paths
- Docker runs Flask as non-root user (`appuser`, UID 1000)
- `entrypoint.sh` uses `gosu` to drop privileges after fixing volume permissions
