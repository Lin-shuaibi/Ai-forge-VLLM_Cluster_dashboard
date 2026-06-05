"""SQLite database module for persistent storage."""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, Any

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "vllm_dashboard.db")


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            cluster_id TEXT,
            port INTEGER DEFAULT 8000,
            status TEXT DEFAULT 'stopped',
            params TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS benchmarks (
            id TEXT PRIMARY KEY,
            model_id TEXT,
            model_name TEXT,
            url TEXT NOT NULL,
            num_prompts INTEGER DEFAULT 100,
            concurrency INTEGER DEFAULT 1,
            ttft_ms REAL,
            tpot_ms REAL,
            decode_tokens_per_second REAL,
            avg_latency_ms REAL,
            p50_latency_ms REAL,
            p95_latency_ms REAL,
            p99_latency_ms REAL,
            total_tokens INTEGER,
            total_time_seconds REAL,
            status TEXT DEFAULT 'pending',
            error TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS download_tasks (
            task_id TEXT PRIMARY KEY,
            model_name TEXT NOT NULL,
            local_path TEXT NOT NULL,
            remote_host TEXT,
            remote_user TEXT,
            remote_model_name TEXT,
            remote_path TEXT,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0.0,
            error TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            quota_total INTEGER DEFAULT 0,
            quota_used INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id TEXT,
            model_id TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            latency_ms REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            source TEXT,
            resolved INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# Initialize on import
init_db()

