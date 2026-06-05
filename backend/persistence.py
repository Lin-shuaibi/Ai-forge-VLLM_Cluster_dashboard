"""SQLite persistence layer for vLLM Dashboard."""
import sqlite3
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent / "data" / "vllm_dashboard.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS download_tasks (
        task_id TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        local_path TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        progress REAL DEFAULT 0.0,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS vllm_models (
        model_id TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        status TEXT NOT NULL,
        container_id TEXT,
        port INTEGER,
        gpu_ids TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS clusters (
        cluster_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        nodes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
        bench_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        config TEXT,
        results TEXT,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT DEFAULT 'anonymous',
        messages TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.commit()

    
    # Notification center
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,           -- 'gpu_temp', 'model_error', 'node_offline', 'disk_full', 'system'
        level TEXT NOT NULL,          -- 'info', 'warning', 'error', 'critical'
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        data TEXT DEFAULT '{}',       -- JSON extra data
        read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Alert rules
    c.execute("""CREATE TABLE IF NOT EXISTS alert_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,           -- 'gpu_temperature', 'memory_usage', 'disk_usage', 'node_status'
        condition TEXT NOT NULL,      -- JSON: {"field": "gpu_temp", "operator": ">", "value": 85}
        actions TEXT DEFAULT '[]',    -- JSON array: ["webhook", "email", "in_app"]
        enabled BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Audit logs
    c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT DEFAULT 'anonymous',
        action TEXT NOT NULL,         -- 'create', 'update', 'delete', 'start', 'stop'
        resource_type TEXT NOT NULL,  -- 'cluster', 'model', 'benchmark', 'download', 'settings'
        resource_id TEXT,
        details TEXT DEFAULT '{}',    -- JSON: parameters, before/after state
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Model templates (Marketplace)
    c.execute("""CREATE TABLE IF NOT EXISTS model_templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        model_name TEXT NOT NULL,     -- e.g. 'Qwen/Qwen2.5-7B-Instruct'
        description TEXT,
        category TEXT,                -- 'llm', 'vision', 'audio', 'multimodal'
        tags TEXT DEFAULT '[]',       -- JSON array
        recommended_config TEXT DEFAULT '{}',  -- JSON: {"gpu_ids": "0", "port": 8000, ...}
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # A/B test versions
    c.execute("""CREATE TABLE IF NOT EXISTS model_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        version_name TEXT NOT NULL,   -- 'v1.0', 'experimental', 'optimized'
        config TEXT NOT NULL,         -- JSON full config
        traffic_weight INTEGER DEFAULT 100,
        is_active BOOLEAN DEFAULT TRUE,
        metrics TEXT DEFAULT '{}',    -- JSON: performance metrics
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(model_id, version_name)
    )""")

    
    conn.close()


class PersistentStore:
    """Base class for services needing async-safe SQLite persistence."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._db_path = str(DB_PATH)
        init_db()

    def _get_conn(self):
        return sqlite3.connect(self._db_path)

    def save(self, key: str, data: Dict[str, Any]):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(
                f"INSERT OR REPLACE INTO {self.table_name} (id, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, json.dumps(data)),
            )

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(
                f"SELECT data FROM {self.table_name} WHERE id = ?", (key,)
            )
            row = c.fetchone()
            return json.loads(row[0]) if row else None

    def delete(self, key: str):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (key,))

    def list_all(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(f"SELECT id, data FROM {self.table_name}")
            return [{"id": r[0], **json.loads(r[1])} for r in c.fetchall()]


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
