"""
Database management for Visual Patrol system.
SQLite with automatic schema migrations and multi-robot support.
"""

import sqlite3
import json
from contextlib import contextmanager
from config import DB_FILE


def get_db_connection():
    """Create a new database connection with Row factory and WAL mode."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def db_context():
    """
    Context manager for database operations.
    Auto-commits on success, rolls back on error, always closes.

    Usage:
        with db_context() as (conn, cursor):
            cursor.execute("SELECT ...")
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_run_token_totals(run_id):
    """
    Calculate total tokens used in a patrol run.
    Returns dict with prompt_tokens, candidate_tokens, total_tokens.
    """
    with db_context() as (conn, cursor):
        cursor.execute('''
            SELECT
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(candidate_tokens), 0) as candidate_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens
            FROM inspection_results
            WHERE run_id = ?
        ''', (run_id,))
        row = cursor.fetchone()
        return {
            'prompt_tokens': row['prompt_tokens'],
            'candidate_tokens': row['candidate_tokens'],
            'total_tokens': row['total_tokens']
        }


def update_run_tokens(run_id):
    """Update patrol_runs table with aggregated token counts."""
    totals = get_run_token_totals(run_id)
    with db_context() as (conn, cursor):
        cursor.execute('''
            UPDATE patrol_runs
            SET prompt_tokens = ?, candidate_tokens = ?, total_tokens = ?
            WHERE id = ?
        ''', (totals['prompt_tokens'], totals['candidate_tokens'],
              totals['total_tokens'], run_id))


def save_generated_report(start_date, end_date, content, usage, robot_id=None):
    """Save AI generated report to database."""
    with db_context() as (conn, cursor):
        cursor.execute('''
            INSERT INTO generated_reports
            (start_date, end_date, report_content, prompt_tokens, candidate_tokens, total_tokens, timestamp, robot_id)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), ?)
        ''', (start_date, end_date, content,
              usage.get('prompt_token_count', 0),
              usage.get('candidates_token_count', 0),
              usage.get('total_token_count', 0),
              robot_id))
        return cursor.lastrowid


# === Multi-Robot Functions ===

def register_robot(robot_id, robot_name, robot_ip):
    """Register or update a robot in the robots table."""
    with db_context() as (conn, cursor):
        cursor.execute('''
            INSERT INTO robots (robot_id, robot_name, robot_ip, last_seen, status)
            VALUES (?, ?, ?, datetime('now', 'localtime'), 'online')
            ON CONFLICT(robot_id) DO UPDATE SET
                robot_name = excluded.robot_name,
                robot_ip = excluded.robot_ip,
                last_seen = datetime('now', 'localtime'),
                status = 'online'
        ''', (robot_id, robot_name, robot_ip))


def update_robot_heartbeat(robot_id, is_connected=True):
    """Update last_seen timestamp and connection status for a robot."""
    status = 'online' if is_connected else 'offline'
    with db_context() as (conn, cursor):
        cursor.execute('''
            UPDATE robots SET last_seen = datetime('now', 'localtime'), status = ?
            WHERE robot_id = ?
        ''', (status, robot_id))


def get_all_robots():
    """Get all registered robots."""
    with db_context() as (conn, cursor):
        cursor.execute('SELECT robot_id, robot_name, robot_ip, last_seen, status FROM robots ORDER BY robot_id')
        return [dict(row) for row in cursor.fetchall()]


def backfill_robot_id(robot_id):
    """Set robot_id on rows where it's NULL (one-time migration)."""
    with db_context() as (conn, cursor):
        cursor.execute('UPDATE patrol_runs SET robot_id = ? WHERE robot_id IS NULL', (robot_id,))
        cursor.execute('UPDATE inspection_results SET robot_id = ? WHERE robot_id IS NULL', (robot_id,))
        cursor.execute('UPDATE generated_reports SET robot_id = ? WHERE robot_id IS NULL', (robot_id,))


def get_global_settings():
    """Get all global settings as a dict."""
    from config import DEFAULT_SETTINGS
    settings = DEFAULT_SETTINGS.copy()
    with db_context() as (conn, cursor):
        cursor.execute('SELECT key, value FROM global_settings')
        for row in cursor.fetchall():
            try:
                settings[row['key']] = json.loads(row['value'])
            except (json.JSONDecodeError, TypeError):
                settings[row['key']] = row['value']
    return settings


def save_global_settings(settings_dict):
    """Save settings dict to global_settings table (UPSERT each key)."""
    with db_context() as (conn, cursor):
        for key, value in settings_dict.items():
            json_value = json.dumps(value, ensure_ascii=False)
            cursor.execute('''
                INSERT INTO global_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (key, json_value))


def init_db():
    """Initialize database schema with migrations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Core tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patrol_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            status TEXT,
            robot_serial TEXT,
            report_content TEXT,
            model_id TEXT,
            token_usage TEXT,
            prompt_tokens INTEGER,
            candidate_tokens INTEGER,
            total_tokens INTEGER,
            video_path TEXT,
            video_analysis TEXT,
            robot_id TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generated_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT,
            end_date TEXT,
            report_content TEXT,
            prompt_tokens INTEGER,
            candidate_tokens INTEGER,
            total_tokens INTEGER,
            timestamp TEXT,
            robot_id TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inspection_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            point_name TEXT,
            coordinate_x REAL,
            coordinate_y REAL,
            prompt TEXT,
            ai_response TEXT,
            is_ng INTEGER,
            ai_description TEXT,
            token_usage TEXT,
            prompt_tokens INTEGER,
            candidate_tokens INTEGER,
            total_tokens INTEGER,
            image_path TEXT,
            timestamp TEXT,
            robot_moving_status TEXT,
            robot_id TEXT,
            FOREIGN KEY(run_id) REFERENCES patrol_runs(id)
        )
    ''')

    # Multi-robot tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS robots (
            robot_id TEXT PRIMARY KEY,
            robot_name TEXT NOT NULL,
            robot_ip TEXT,
            last_seen TEXT,
            status TEXT DEFAULT 'offline'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Run migrations for existing databases
    _run_migrations(cursor)

    conn.commit()
    conn.close()


def _run_migrations(cursor):
    """Apply database migrations for backward compatibility."""
    migrations = [
        # (check_column, table, columns_to_add)
        ('is_ng', 'inspection_results', ['is_ng INTEGER', 'ai_description TEXT', 'token_usage TEXT']),
        ('prompt_tokens', 'inspection_results', ['prompt_tokens INTEGER', 'candidate_tokens INTEGER', 'total_tokens INTEGER']),
        ('token_usage', 'patrol_runs', ['token_usage TEXT']),
        ('prompt_tokens', 'patrol_runs', ['prompt_tokens INTEGER', 'candidate_tokens INTEGER', 'total_tokens INTEGER']),
        ('robot_moving_status', 'inspection_results', ['robot_moving_status TEXT']),
        ('video_path', 'patrol_runs', ['video_path TEXT', 'video_analysis TEXT']),
        # Multi-robot migrations
        ('robot_id', 'patrol_runs', ['robot_id TEXT']),
        ('robot_id', 'inspection_results', ['robot_id TEXT']),
        ('robot_id', 'generated_reports', ['robot_id TEXT']),
    ]

    for check_col, table, columns in migrations:
        try:
            cursor.execute(f"SELECT {check_col} FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            print(f"Migrating: Adding columns to {table}...")
            for col_def in columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                except Exception as e:
                    print(f"  Migration warning: {e}")
