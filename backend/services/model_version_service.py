"""Model version management service."""
import json
import sqlite3
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from services.error_handlers import NotFoundError, ConflictError

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "vllm_dashboard.db"
MODELS_DIR = BASE_DIR / "data" / "models"
VERSION_STORE = MODELS_DIR / "versions"
VERSION_STORE.mkdir(parents=True, exist_ok=True)


class ModelVersion:
    """Model version data class."""

    def __init__(
        self,
        model_name: str,
        version: str,
        path: str,
        size_mb: float,
        framework: str = "vllm",
        description: str = "",
        config: dict = None,
        tags: list = None,
        parent_version: str = None,
        created_by: str = "system",
    ):
        self.id = None
        self.model_name = model_name
        self.version = version
        self.path = path
        self.size_mb = round(size_mb, 2)
        self.framework = framework
        self.description = description
        self.config = config or {}
        self.tags = tags or []
        self.parent_version = parent_version
        self.created_by = created_by
        self.checksum = None
        self.created_at = None
        self.download_count = 0
        self.is_active = False


class ModelVersionService:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute("CREATE TABLE IF NOT EXISTS model_versions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "model_name TEXT NOT NULL, "
                "version TEXT NOT NULL, "
                "path TEXT NOT NULL, "
                "size_mb REAL DEFAULT 0, "
                "framework TEXT DEFAULT 'vllm', "
                "description TEXT, "
                "config TEXT, "
                "tags TEXT, "
                "parent_version TEXT, "
                "created_by TEXT DEFAULT 'system', "
                "checksum TEXT, "
                "download_count INTEGER DEFAULT 0, "
                "is_active BOOLEAN DEFAULT 1, "
                "deployment_status TEXT DEFAULT 'registered', "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "UNIQUE(model_name, version))")

            c.execute("CREATE TABLE IF NOT EXISTS model_version_files ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "version_id INTEGER NOT NULL, "
                "file_name TEXT NOT NULL, "
                "file_size INTEGER NOT NULL, "
                "checksum TEXT, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (version_id) REFERENCES model_versions(id) ON DELETE CASCADE)")

            c.execute("CREATE TABLE IF NOT EXISTS model_deployments ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "version_id INTEGER NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "host TEXT, "
                "port INTEGER, "
                "gpu_count INTEGER DEFAULT 1, "
                "started_at TIMESTAMP, "
                "stopped_at TIMESTAMP, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (version_id) REFERENCES model_versions(id) ON DELETE CASCADE)")

            conn.commit()

    def register_version(self, mv: ModelVersion) -> Dict[str, Any]:
        """Register a new model version."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Check for duplicate
            c.execute(
                "SELECT id FROM model_versions WHERE model_name = ? AND version = ?",
                (mv.model_name, mv.version))
            if c.fetchone():
                raise ConflictError(
                    message=f"Version {mv.version} for model {mv.model_name} already exists",
                    code="VERSION_EXISTS")

            # Create version directory
            version_path = VERSION_STORE / mv.model_name / f"v{mv.version}"
            version_path.mkdir(parents=True, exist_ok=True)

            # Calculate checksum if path exists
            checksum = None
            if mv.path and Path(mv.path).exists():
                checksum = self._calculate_directory_hash(mv.path)

            c.execute(
                "INSERT INTO model_versions (model_name, version, path, size_mb, "
                "framework, description, config, tags, parent_version, "
                "created_by, checksum) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (mv.model_name, mv.version, str(version_path), mv.size_mb,
                 mv.framework, mv.description, json.dumps(mv.config),
                 json.dumps(mv.tags), mv.parent_version,
                 mv.created_by, checksum))

            version_id = c.lastrowid
            conn.commit()

            return self.get_version(version_id)

    def get_version(self, version_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific version by ID."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT * FROM model_versions WHERE id = ?", (version_id,))
            row = c.fetchone()
            if not row:
                raise NotFoundError(message=f"Version {version_id} not found")

            return self._row_to_dict(row)

    def list_versions(self, model_name: str = None, active_only: bool = False) -> List[Dict[str, Any]]:
        """List versions for a model."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if model_name:
                sql = "SELECT * FROM model_versions WHERE model_name = ?"
                params = [model_name]
                if active_only:
                    sql += " AND is_active = 1"
                sql += " ORDER BY created_at DESC"
                c.execute(sql, params)
            else:
                sql = "SELECT * FROM model_versions"
                if active_only:
                    sql += " WHERE is_active = 1"
                sql += " ORDER BY model_name, created_at DESC"
                c.execute(sql)

            return [self._row_to_dict(row) for row in c.fetchall()]

    def get_latest_version(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get the latest active version of a model."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "SELECT * FROM model_versions WHERE model_name = ? AND is_active = 1 "
                "ORDER BY id DESC LIMIT 1",
                (model_name,))
            row = c.fetchone()
            return self._row_to_dict(row) if row else None

    def activate_version(self, version_id: int) -> Dict[str, Any]:
        """Activate a specific version and deactivate others for the same model."""
        version = self.get_version(version_id)

        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            # Deactivate all other versions of this model
            c.execute(
                "UPDATE model_versions SET is_active = 0 "
                "WHERE model_name = ? AND id != ?",
                (version["model_name"], version_id))

            # Activate this version
            c.execute(
                "UPDATE model_versions SET is_active = 1, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (version_id,))
            conn.commit()

        return self.get_version(version_id)

    def delete_version(self, version_id: int) -> bool:
        """Delete a model version."""
        version = self.get_version(version_id)

        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            # Check if any deployments reference this
            c.execute("SELECT COUNT(*) FROM model_deployments WHERE version_id = ?", (version_id,))
            if c.fetchone()[0] > 0:
                # Archive instead of delete
                c.execute(
                    "UPDATE model_versions SET is_active = 0, deployment_status = 'archived' "
                    "WHERE id = ?",
                    (version_id,))
            else:
                c.execute("DELETE FROM model_versions WHERE id = ?", (version_id))

            conn.commit()

        return True

    def compare_versions(self, model_name: str, v1: str, v2: str) -> Dict[str, Any]:
        """Compare two model versions."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "SELECT * FROM model_versions WHERE model_name = ? AND version IN (?, ?)",
                (model_name, v1, v2))
            rows = c.fetchall()

            if len(rows) != 2:
                raise NotFoundError(message="One or both versions not found")

            version_a = self._row_to_dict(rows[0])
            version_b = self._row_to_dict(rows[1])

            differences = {}
            fields_to_compare = ["size_mb", "framework", "config", "tags", "description"]

            for field in fields_to_compare:
                val_a = version_a.get(field)
                val_b = version_b.get(field)

                if val_a != val_b:
                    differences[field] = {
                        v1: val_a,
                        v2: val_b
                    }

            return {
                "model_name": model_name,
                "version_a": v1,
                "version_b": v2,
                "differences": differences,
                "identical": len(differences) == 0
            }

    def rollback(self, model_name: str, target_version_id: int) -> Dict[str, Any]:
        """Rollback to a previous version."""
        target = self.get_version(target_version_id)

        if target["model_name"] != model_name:
            raise ConflictError(message="Version does not belong to the specified model")

        # Activate the target version
        result = self.activate_version(target_version_id)
        result["rollback"] = True
        result["rolled_back_from"] = "previous_active_version"
        return result

    def create_deployment(self, version_id: int, host: str = None, port: int = None,
                         gpu_count: int = 1) -> Dict[str, Any]:
        """Create a deployment for a model version."""
        version = self.get_version(version_id)

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "INSERT INTO model_deployments (version_id, status, host, port, gpu_count) "
                "VALUES (?, 'pending', ?, ?, ?)",
                (version_id, host, port, gpu_count))

            deployment_id = c.lastrowid

            # Update version deployment status
            c.execute(
                "UPDATE model_versions SET deployment_status = 'deploying' WHERE id = ?",
                (version_id,))
            conn.commit()

        return {
            "deployment_id": deployment_id,
            "version": version,
            "status": "pending"
        }

    def update_deployment_status(self, deployment_id: int, status: str) -> Dict[str, Any]:
        """Update deployment status."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT * FROM model_deployments WHERE id = ?", (deployment_id,))
            deployment = c.fetchone()
            if not deployment:
                raise NotFoundError(message=f"Deployment {deployment_id} not found")

            updates = {"status": status}
            if status == "running" and not deployment["started_at"]:
                updates["started_at"] = "CURRENT_TIMESTAMP"
                c.execute(
                    "UPDATE model_deployments SET status = ?, started_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (status, deployment_id))
                c.execute(
                    "UPDATE model_versions SET deployment_status = 'running' WHERE id = ?",
                    (deployment["version_id"],))
            elif status in ("stopped", "failed"):
                updates["stopped_at"] = "CURRENT_TIMESTAMP"
                c.execute(
                    "UPDATE model_deployments SET status = ?, stopped_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (status, deployment_id))
                c.execute(
                    "UPDATE model_versions SET deployment_status = ? WHERE id = ?",
                    (status, deployment["version_id"]))
            else:
                c.execute(
                    "UPDATE model_deployments SET status = ? WHERE id = ?",
                    (status, deployment_id))

            conn.commit()

            return {"deployment_id": deployment_id, "status": status}

    def get_deployment_history(self, version_id: int) -> List[Dict[str, Any]]:
        """Get deployment history for a version."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "SELECT * FROM model_deployments WHERE version_id = ? "
                "ORDER BY created_at DESC",
                (version_id,))
            return [dict(row) for row in c.fetchall()]

    def _calculate_directory_hash(self, path: str) -> str:
        """Calculate SHA256 hash of all files in a directory."""
        hasher = hashlib.sha256()

        for file_path in sorted(Path(path).rglob("*")):
            if file_path.is_file():
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)

        return hasher.hexdigest()

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a DB row to dict with parsed JSON fields."""
        d = dict(row)
        for field in ["config", "tags"]:
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except json.JSONDecodeError:
                    d[field] = {}
        return d


model_version_service = ModelVersionService()