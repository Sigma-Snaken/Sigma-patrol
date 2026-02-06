# Backend Documentation

## Overview

The backend is a Python Flask application that provides the REST API, manages robot communication via gRPC, orchestrates patrol missions, runs AI inference, and generates PDF reports.

## File Structure

```
src/backend/
├── app.py               # Flask application, route definitions, startup
├── config.py            # Environment variables, paths, defaults
├── database.py          # SQLite schema, migrations, DB helpers
├── settings_service.py  # Global settings CRUD (wraps DB table)
├── robot_service.py     # Kachaka robot gRPC interface
├── patrol_service.py    # Patrol orchestration, scheduling
├── ai_service.py        # Google Gemini AI integration
├── pdf_service.py       # PDF report generation (ReportLab)
├── video_recorder.py    # Video recording during patrols (OpenCV)
├── utils.py             # JSON I/O, timezone helpers
├── logger.py            # Timezone-aware logging setup
└── requirements.txt     # Python dependencies
```

## Service Architecture

Services are instantiated as module-level singletons. Import order matters because services read settings from the database at module load time.

```
config.py           -- Loaded first (env vars, paths)
    |
database.py         -- Schema init (init_db called before service imports)
    |
settings_service.py -- Reads global_settings table
    |
robot_service.py    -- Connects to Kachaka (reads ROBOT_IP from env)
ai_service.py       -- Configures Gemini client (reads API key from settings)
patrol_service.py   -- Imports robot_service, ai_service, settings_service
pdf_service.py      -- Reads from database for report data
video_recorder.py   -- Used by patrol_service
utils.py            -- Used by patrol_service, app.py
logger.py           -- Used by ai_service, patrol_service, video_recorder
```

## Modules

### `config.py`

Reads environment variables and defines filesystem paths.

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ROBOT_ID` | `"default"` | Unique robot identifier |
| `ROBOT_NAME` | `"Robot"` | Display name |
| `ROBOT_IP` | `"192.168.50.133:26400"` | Kachaka gRPC address |
| `DATA_DIR` | `{project}/data` | Shared data directory |
| `LOG_DIR` | `{project}/logs` | Log file directory |
| `PORT` | `5000` | Flask listen port |
| `TZ` | (system) | System timezone (Docker) |

**Derived Paths:**

| Path | Value | Description |
|------|-------|-------------|
| `REPORT_DIR` | `{DATA_DIR}/report` | Shared report directory |
| `DB_FILE` | `{REPORT_DIR}/report.db` | SQLite database |
| `ROBOT_DATA_DIR` | `{DATA_DIR}/{ROBOT_ID}` | Per-robot data |
| `ROBOT_CONFIG_DIR` | `{ROBOT_DATA_DIR}/config` | Per-robot config |
| `ROBOT_IMAGES_DIR` | `{ROBOT_DATA_DIR}/report/images` | Per-robot images |
| `POINTS_FILE` | `{ROBOT_CONFIG_DIR}/points.json` | Waypoints file |
| `SCHEDULE_FILE` | `{ROBOT_CONFIG_DIR}/patrol_schedule.json` | Schedule file |

Also defines `DEFAULT_SETTINGS` dict with default values for all global settings, and `ensure_dirs()` / `migrate_legacy_files()` functions.

### `database.py`

SQLite database management with schema initialization and migrations.

**Connection settings:**
- WAL journal mode for concurrent access
- 5000ms busy timeout
- Row factory for dict-like access

**Context manager:**
```python
with db_context() as (conn, cursor):
    cursor.execute("SELECT ...")
    # Auto-commits on success, rolls back on error
```

#### Database Schema

**`patrol_runs`** -- One row per patrol mission

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `start_time` | TEXT | Patrol start timestamp |
| `end_time` | TEXT | Patrol end timestamp |
| `status` | TEXT | `Running`, `Completed`, `Patrol Stopped` |
| `robot_serial` | TEXT | Kachaka serial number |
| `report_content` | TEXT | AI-generated summary report (Markdown) |
| `model_id` | TEXT | Gemini model name |
| `token_usage` | TEXT | JSON string of token usage |
| `prompt_tokens` | INTEGER | Aggregated input tokens |
| `candidate_tokens` | INTEGER | Aggregated output tokens |
| `total_tokens` | INTEGER | Aggregated total tokens |
| `video_path` | TEXT | Path to recorded video |
| `video_analysis` | TEXT | AI video analysis result |
| `robot_id` | TEXT | Robot identifier |

**`inspection_results`** -- One row per waypoint inspection

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `run_id` | INTEGER FK | References `patrol_runs.id` |
| `point_name` | TEXT | Waypoint name |
| `coordinate_x` | REAL | World X coordinate |
| `coordinate_y` | REAL | World Y coordinate |
| `prompt` | TEXT | AI prompt used |
| `ai_response` | TEXT | Raw AI response (JSON or text) |
| `is_ng` | INTEGER | 1 if abnormal, 0 if normal |
| `ai_description` | TEXT | Parsed description |
| `token_usage` | TEXT | JSON string of token usage |
| `prompt_tokens` | INTEGER | Input tokens |
| `candidate_tokens` | INTEGER | Output tokens |
| `total_tokens` | INTEGER | Total tokens |
| `image_path` | TEXT | Relative path to inspection image |
| `timestamp` | TEXT | Inspection timestamp |
| `robot_moving_status` | TEXT | Movement result (`Success`, `Error: ...`) |
| `robot_id` | TEXT | Robot identifier |

**`generated_reports`** -- AI-generated multi-day analysis reports

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `start_date` | TEXT | Report period start |
| `end_date` | TEXT | Report period end |
| `report_content` | TEXT | AI report content (Markdown) |
| `prompt_tokens` | INTEGER | Input tokens |
| `candidate_tokens` | INTEGER | Output tokens |
| `total_tokens` | INTEGER | Total tokens |
| `timestamp` | TEXT | Generation timestamp |
| `robot_id` | TEXT | Robot filter used |

**`robots`** -- Registered robot instances

| Column | Type | Description |
|--------|------|-------------|
| `robot_id` | TEXT PK | Unique identifier |
| `robot_name` | TEXT | Display name |
| `robot_ip` | TEXT | gRPC address |
| `last_seen` | TEXT | Last heartbeat time |
| `status` | TEXT | `online` or `offline` |

**`global_settings`** -- Key-value settings store

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT PK | Setting name |
| `value` | TEXT | JSON-encoded value |

**Schema Migrations:**

The `_run_migrations()` function adds columns to existing tables for backward compatibility. It checks if a column exists by attempting a SELECT, and adds missing columns via ALTER TABLE if the check fails.

### `settings_service.py`

Thin wrapper around `database.get_global_settings()` and `database.save_global_settings()`.

- `get_all()` -- Returns settings merged with `DEFAULT_SETTINGS`
- `get(key, default)` -- Get single setting
- `save(dict)` -- UPSERT all key-value pairs
- `migrate_from_json(path)` -- One-time import from legacy `settings.json`

### `robot_service.py`

Manages the gRPC connection to a Kachaka robot.

**Singleton:** `robot_service = RobotService()`

**Key methods:**

| Method | Description |
|--------|-------------|
| `connect()` | Establish gRPC connection to `ROBOT_IP` |
| `get_client()` | Returns gRPC client (or `None` if disconnected) |
| `get_state()` | Returns `{battery, pose, map_info}` |
| `get_map_bytes()` | Returns PNG map as bytes |
| `move_to(x, y, theta)` | Move robot to pose |
| `move_forward(distance, speed)` | Move forward/backward |
| `rotate(angle)` | Rotate in place |
| `return_home()` | Return to charging station |
| `cancel_command()` | Cancel current command |
| `get_front_camera_image()` | Get front camera JPEG |
| `get_back_camera_image()` | Get back camera JPEG |
| `get_serial()` | Get robot serial number |
| `get_locations()` | Get saved locations from robot |

**Thread safety:** Uses `client_lock` for gRPC client access and `state_lock` for state reads/writes.

**Auto-reconnect:** The polling loop resets `self.client = None` on persistent errors, triggering reconnection on the next poll cycle.

### `ai_service.py`

Google Gemini AI integration for visual inspection and report generation.

**Singleton:** `ai_service = AIService()`

Uses the `google-genai` SDK (not the deprecated `google-generativeai`).

**Key methods:**

| Method | Description |
|--------|-------------|
| `generate_inspection(image, prompt, sys_prompt)` | Analyze image with structured JSON response |
| `generate_report(prompt)` | Generate text report from patrol data |
| `analyze_video(path, prompt)` | Analyze patrol video |
| `is_configured()` | Check if API key is set |
| `get_model_name()` | Get current model name |

**Structured output:** `generate_inspection()` uses a Pydantic `InspectionResult` schema to enforce JSON response format:
```python
class InspectionResult(BaseModel):
    is_NG: bool   # True if abnormal
    Description: str
```

**Auto-reconfigure:** Each method call runs `_configure()` which checks if settings have changed and reconfigures the client if needed.

**`parse_ai_response()`** is a standalone utility function that normalizes AI responses into a standard dict format used by patrol_service.

### `patrol_service.py`

Orchestrates autonomous patrol missions.

**Singleton:** `patrol_service = PatrolService()`

**Patrol flow:**

1. Load enabled waypoints from `points.json`
2. Validate AI is configured
3. Create `patrol_runs` DB record
4. Optionally start video recording
5. For each waypoint:
   a. Move robot to point (`_move_to_point`)
   b. Wait 2 seconds for stability
   c. Capture front camera image
   d. Run AI inspection (sync or async via turbo mode)
   e. Save result to `inspection_results` table
6. Return home
7. Wait for async queue (turbo mode)
8. Optionally analyze video
9. Generate AI summary report
10. Generate AI-summarized Telegram message and send notification (if enabled)
11. Update run status and tokens

**Turbo mode:** When enabled, images are queued for AI analysis while the robot continues moving to the next waypoint. The `_inspection_worker` thread processes the queue in the background.

**Schedule checker:** A background thread runs every 30 seconds, comparing the current time against enabled schedules. Each schedule can only trigger once per day (tracked by `trigger_key`).

**Image naming:** Images are saved as `{point_name}_processing_{uuid}.jpg` during capture, then renamed to `{point_name}_{OK|NG}_{uuid}.jpg` after AI analysis.

### `pdf_service.py`

Server-side PDF generation using ReportLab.

**Key functions:**

| Function | Description |
|----------|-------------|
| `generate_patrol_report(run_id)` | Single patrol run PDF |
| `generate_analysis_report(content, start, end)` | Multi-day analysis PDF |

**Features:**
- CJK font support (`STSong-Light` for Chinese characters)
- Markdown-to-PDF conversion (headers, bold, italic, code blocks, tables, lists, blockquotes)
- Inspection images embedded in PDF
- OK/NG color coding (green/red)
- Page numbers and footer

### `video_recorder.py`

Records patrol video using OpenCV.

- Tries codecs in order: H.264 (`avc1`), XVID, MJPEG
- Captures frames from robot's front camera at configured FPS (default 5)
- Resizes frames to 640x480
- Runs in a background thread

### `utils.py`

Shared utility functions:

- `load_json(path, default)` -- Safe JSON file loading with fallback
- `save_json(path, data)` -- Atomic JSON save (temp file + rename)
- `get_current_time_str()` -- Timezone-aware timestamp string
- `get_current_datetime()` -- Timezone-aware datetime object
- `get_filename_timestamp()` -- Timestamp for filenames (`YYYYMMDD_HHMMSS`)

### `logger.py`

Logging configuration with timezone support.

- `TimezoneFormatter` -- Custom formatter using configured timezone
- `get_logger(name, file)` -- Creates logger with file + console handlers
- Log files are prefixed with robot ID (e.g., `robot-a_app.log`)
- Flask/Werkzeug request logging is suppressed (`logging.ERROR` level)

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `flask` | >=3.0, <4.0 | Web framework |
| `kachaka-api` | >=3.14, <4.0 | Kachaka robot gRPC client |
| `numpy` | >=2.2, <3.0 | Array operations (video frames) |
| `pillow` | >=10.0, <11.0 | Image processing |
| `google-genai` | >=1.0, <2.0 | Google Gemini AI SDK |
| `reportlab` | >=4.0, <5.0 | PDF generation |
| `opencv-python-headless` | >=4.9, <5.0 | Video recording |
| `requests` | >=2.31, <3.0 | Telegram API calls |

## Startup Sequence (`app.py`)

1. Import `config` (reads env vars)
2. Call `ensure_dirs()` (create data directories)
3. Call `init_db()` (create/migrate DB schema)
4. Import services (they read DB at module level)
5. Create Flask app
6. Configure logging
7. Register routes
8. **On `__main__`:**
   a. `init_db()` again (idempotent)
   b. `migrate_from_json()` (legacy settings migration)
   c. `migrate_legacy_files()` (legacy per-robot file migration)
   d. `register_robot()` (register this instance in DB)
   e. `backfill_robot_id()` (set robot_id on NULL rows)
   f. Start heartbeat thread
   g. `app.run()` on configured port
