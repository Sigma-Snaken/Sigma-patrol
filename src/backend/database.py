"""
Database management for Sigma Patrol system.
SQLite with automatic schema migrations.
"""

import sqlite3
from contextlib import contextmanager
from config import DB_FILE


def get_db_connection():
    """Create a new database connection with Row factory."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
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
            total_tokens INTEGER
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
            FOREIGN KEY(run_id) REFERENCES patrol_runs(id)
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
