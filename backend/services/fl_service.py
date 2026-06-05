"""Federated Learning support service."""
import json
import sqlite3
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("vllm-dashboard")

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "vllm_dashboard.db"


class FederatedLearningService:
    def __init__(self):
        self._init_db()
        self._lock = threading.Lock()
        self.active_tasks: Dict[str, Dict[str, Any]] = {}

    def _init_db(self):
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute("CREATE TABLE IF NOT EXISTS fl_projects ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "name TEXT NOT NULL, "
                "description TEXT, "
                "base_model TEXT NOT NULL, "
                "aggregation_strategy TEXT DEFAULT 'fedavg', "
                "num_clients INTEGER DEFAULT 2, "
                "min_clients INTEGER DEFAULT 2, "
                "local_epochs INTEGER DEFAULT 5, "
                "batch_size INTEGER DEFAULT 32, "
                "learning_rate REAL DEFAULT 0.01, "
                "privacy_budget REAL DEFAULT 10.0, "
                "differential_privacy BOOLEAN DEFAULT 0, "
                "secure_aggregation BOOLEAN DEFAULT 0, "
                "status TEXT DEFAULT 'created', "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            c.execute("CREATE TABLE IF NOT EXISTS fl_clients ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "project_id INTEGER NOT NULL, "
                "client_id TEXT NOT NULL, "
                "client_name TEXT, "
                "endpoint_url TEXT, "
                "data_size INTEGER DEFAULT 0, "
                "status TEXT DEFAULT 'registered', "
                "last_heartbeat TIMESTAMP, "
                "last_round INTEGER DEFAULT 0, "
                "contribution_score REAL DEFAULT 0, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "UNIQUE(project_id, client_id), "
                "FOREIGN KEY (project_id) REFERENCES fl_projects(id) ON DELETE CASCADE)")

            c.execute("CREATE TABLE IF NOT EXISTS fl_rounds ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "project_id INTEGER NOT NULL, "
                "round_number INTEGER NOT NULL, "
                "model_version TEXT, "
                "global_accuracy REAL, "
                "global_loss REAL, "
                "num_clients_participated INTEGER DEFAULT 0, "
                "aggregation_time_ms REAL DEFAULT 0, "
                "communication_size_bytes INTEGER DEFAULT 0, "
                "status TEXT DEFAULT 'initiated', "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "completed_at TIMESTAMP, "
                "FOREIGN KEY (project_id) REFERENCES fl_projects(id) ON DELETE CASCADE)")

            c.execute("CREATE TABLE IF NOT EXISTS fl_client_rounds ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "round_id INTEGER NOT NULL, "
                "client_id TEXT NOT NULL, "
                "local_accuracy REAL, "
                "local_loss REAL, "
                "training_time_ms REAL DEFAULT 0, "
                "data_used INTEGER DEFAULT 0, "
                "model_delta_size INTEGER DEFAULT 0, "
                "status TEXT DEFAULT 'training', "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (round_id) REFERENCES fl_rounds(id) ON DELETE CASCADE)")

            c.execute("CREATE TABLE IF NOT EXISTS fl_global_models ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "project_id INTEGER NOT NULL, "
                "round_number INTEGER NOT NULL, "
                "model_version TEXT, "
                "model_path TEXT, "
                "model_size_bytes INTEGER DEFAULT 0, "
                "global_accuracy REAL, "
                "global_loss REAL, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (project_id) REFERENCES fl_projects(id) ON DELETE CASCADE)")

            conn.commit()

    def create_project(self, name: str, base_model: str, description: str = "",
                      aggregation_strategy: str = "fedavg",
                      num_clients: int = 2, min_clients: int = 2,
                      local_epochs: int = 5, batch_size: int = 32,
                      learning_rate: float = 0.01, privacy_budget: float = 10.0,
                      differential_privacy: bool = False,
                      secure_aggregation: bool = False) -> Dict[str, Any]:
        """Create a new federated learning project."""
        valid_strategies = ["fedavg", "fedprox", "fednova", "scaffold", "fedbn", "fedopt"]
        if aggregation_strategy not in valid_strategies:
            raise ValueError(f"Invalid aggregation strategy. Must be one of: {valid_strategies}")

        if min_clients > num_clients:
            raise ValueError("min_clients cannot exceed num_clients")

        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute(
                "INSERT INTO fl_projects (name, description, base_model, aggregation_strategy, "
                "num_clients, min_clients, local_epochs, batch_size, learning_rate, "
                "privacy_budget, differential_privacy, secure_aggregation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, description, base_model, aggregation_strategy,
                 num_clients, min_clients, local_epochs, batch_size, learning_rate,
                 privacy_budget, differential_privacy, secure_aggregation))

            project_id = c.lastrowid
            conn.commit()

            return {
                "id": project_id,
                "name": name,
                "base_model": base_model,
                "aggregation_strategy": aggregation_strategy,
                "num_clients": num_clients,
                "min_clients": min_clients,
                "local_epochs": local_epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "privacy_budget": privacy_budget,
                "differential_privacy": differential_privacy,
                "secure_aggregation": secure_aggregation,
                "status": "created",
                "message": "Project created successfully"
            }

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get project details."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT * FROM fl_projects WHERE id = ?", (project_id,))
            project = c.fetchone()

            if not project:
                return None

            result = dict(project)
            result["differential_privacy"] = bool(result["differential_privacy"])
            result["secure_aggregation"] = bool(result["secure_aggregation"])

            # Get clients
            c.execute("SELECT * FROM fl_clients WHERE project_id = ?", (project_id,))
            result["clients"] = [dict(row) for row in c.fetchall()]

            # Get latest round
            c.execute(
                "SELECT * FROM fl_rounds WHERE project_id = ? ORDER BY round_number DESC LIMIT 1",
                (project_id,))
            latest_round = c.fetchone()
            if latest_round:
                result["latest_round"] = dict(latest_round)

            return result

    def list_projects(self, status: str = None) -> List[Dict[str, Any]]:
        """List all FL projects."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            if status:
                c.execute("SELECT * FROM fl_projects WHERE status = ? ORDER BY created_at DESC", (status,))
            else:
                c.execute("SELECT * FROM fl_projects ORDER BY created_at DESC")

            projects = []
            for row in c.fetchall():
                project = dict(row)
                project["differential_privacy"] = bool(project["differential_privacy"])
                project["secure_aggregation"] = bool(project["secure_aggregation"])

                # Get client count
                c.execute("SELECT COUNT(*) as count FROM fl_clients WHERE project_id = ?",
                         (project["id"],))
                project["client_count"] = c.fetchone()["count"]

                # Get round count
                c.execute("SELECT COUNT(*) as count FROM fl_rounds WHERE project_id = ?",
                         (project["id"],))
                project["round_count"] = c.fetchone()["count"]

                projects.append(project)

            return projects

    def register_client(self, project_id: int, client_id: str,
                       client_name: str = None, endpoint_url: str = None,
                       data_size: int = 0) -> Dict[str, Any]:
        """Register a client for a project."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Verify project exists
            c.execute("SELECT id FROM fl_projects WHERE id = ?", (project_id,))
            if not c.fetchone():
                raise ValueError(f"Project {project_id} not found")

            try:
                c.execute(
                    "INSERT INTO fl_clients (project_id, client_id, client_name, endpoint_url, data_size) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (project_id, client_id, client_name or client_id, endpoint_url, data_size))

                client_db_id = c.lastrowid
                conn.commit()

                return {
                    "id": client_db_id,
                    "project_id": project_id,
                    "client_id": client_id,
                    "client_name": client_name or client_id,
                    "endpoint_url": endpoint_url,
                    "data_size": data_size,
                    "status": "registered",
                    "message": "Client registered successfully"
                }
            except sqlite3.IntegrityError:
                raise ValueError(f"Client {client_id} already registered for project {project_id}")

    def get_clients(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all clients for a project."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT * FROM fl_clients WHERE project_id = ? ORDER BY client_id",
                     (project_id,))
            return [dict(row) for row in c.fetchall()]

    def start_training_round(self, project_id: int) -> Dict[str, Any]:
        """Start a new training round."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get project
            c.execute("SELECT * FROM fl_projects WHERE id = ?", (project_id,))
            project = c.fetchone()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # Get active clients
            c.execute(
                "SELECT * FROM fl_clients WHERE project_id = ? AND status = 'registered'",
                (project_id,))
            clients = c.fetchall()

            if len(clients) < project["min_clients"]:
                raise ValueError(
                    f"Not enough clients. Need {project['min_clients']}, have {len(clients)}")

            # Get current round number
            c.execute(
                "SELECT MAX(round_number) as max_round FROM fl_rounds WHERE project_id = ?",
                (project_id,))
            max_round = c.fetchone()["max_round"] or 0
            round_number = max_round + 1

            # Create round
            c.execute(
                "INSERT INTO fl_rounds (project_id, round_number, num_clients_participated, "
                "model_version, status) VALUES (?, ?, ?, ?, ?)",
                (project_id, round_number, len(clients),
                 f"round-{round_number}", "initiated"))

            round_id = c.lastrowid

            # Create client rounds
            for client in clients:
                c.execute(
                    "INSERT INTO fl_client_rounds (round_id, client_id, status) VALUES (?, ?, ?)",
                    (round_id, client["client_id"], "training"))

                # Update client last_round
                c.execute(
                    "UPDATE fl_clients SET last_round = ?, last_heartbeat = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (round_number, client["id"]))

            # Update project status
            c.execute(
                "UPDATE fl_projects SET status = 'training', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,))

            conn.commit()

            # Select participating clients
            c.execute("SELECT * FROM fl_clients WHERE project_id = ? AND status = 'registered'", (project_id,))
            participating_clients = [dict(row) for row in c.fetchall()]

            # Simulate training start
            self.active_tasks[str(project_id)] = {
                "round_id": round_id,
                "round_number": round_number,
                "started_at": datetime.now().isoformat()
            }

            return {
                "round_id": round_id,
                "round_number": round_number,
                "project_id": project_id,
                "project_name": project["name"],
                "strategy": project["aggregation_strategy"],
                "num_clients": len(participating_clients),
                "clients": participating_clients,
                "status": "initiated"
            }

    def submit_client_result(self, round_id: int, client_id: str,
                            local_accuracy: float, local_loss: float,
                            training_time_ms: float = 0, data_used: int = 0,
                            model_delta_size: int = 0) -> Dict[str, Any]:
        """Submit a client's training result."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Update client round
            c.execute(
                "UPDATE fl_client_rounds SET local_accuracy = ?, local_loss = ?, "
                "training_time_ms = ?, data_used = ?, model_delta_size = ?, status = ? "
                "WHERE round_id = ? AND client_id = ?",
                (local_accuracy, local_loss, training_time_ms, data_used,
                 model_delta_size, "completed", round_id, client_id))

            conn.commit()

            return {
                "round_id": round_id,
                "client_id": client_id,
                "local_accuracy": local_accuracy,
                "local_loss": local_loss,
                "status": "completed"
            }

    def aggregate_round(self, round_id: int, global_accuracy: float = 0,
                       global_loss: float = 0, aggregation_time_ms: float = 0) -> Dict[str, Any]:
        """Complete aggregation for a round."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get round info
            c.execute("SELECT * FROM fl_rounds WHERE id = ?", (round_id,))
            round_info = c.fetchone()
            if not round_info:
                raise ValueError(f"Round {round_id} not found")

            # Get completed clients
            c.execute(
                "SELECT COUNT(*) as count FROM fl_client_rounds "
                "WHERE round_id = ? AND status = 'completed'",
                (round_id,))
            completed = c.fetchone()["count"]

            # Calculate communication size
            c.execute(
                "SELECT COALESCE(SUM(model_delta_size), 0) as total_size "
                "FROM fl_client_rounds WHERE round_id = ?",
                (round_id,))
            comm_size = c.fetchone()["total_size"]

            # Update round
            c.execute(
                "UPDATE fl_rounds SET global_accuracy = ?, global_loss = ?, "
                "aggregation_time_ms = ?, communication_size_bytes = ?, "
                "num_clients_participated = ?, status = ?, completed_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (global_accuracy, global_loss, aggregation_time_ms, comm_size,
                 completed, "completed", round_id))

            # Save global model
            model_version = f"round-{round_info['round_number']}-global"
            c.execute(
                "INSERT INTO fl_global_models (project_id, round_number, model_version, "
                "global_accuracy, global_loss) VALUES (?, ?, ?, ?, ?)",
                (round_info["project_id"], round_info["round_number"],
                 model_version, global_accuracy, global_loss))

            # Update project
            c.execute(
                "UPDATE fl_projects SET updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (round_info["project_id"],))

            conn.commit()

            return {
                "round_id": round_id,
                "round_number": round_info["round_number"],
                "global_accuracy": global_accuracy,
                "global_loss": global_loss,
                "clients_completed": completed,
                "aggregation_time_ms": aggregation_time_ms,
                "communication_size_bytes": comm_size,
                "status": "completed"
            }

    def get_training_progress(self, project_id: int) -> Dict[str, Any]:
        """Get training progress for a project."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get project
            c.execute("SELECT * FROM fl_projects WHERE id = ?", (project_id,))
            project = c.fetchone()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # Get all rounds
            c.execute(
                "SELECT * FROM fl_rounds WHERE project_id = ? ORDER BY round_number",
                (project_id,))
            rounds = []
            for row in c.fetchall():
                round_data = dict(row)

                # Get client results for this round
                c.execute(
                    "SELECT * FROM fl_client_rounds WHERE round_id = ?",
                    (row["id"],))
                round_data["clients"] = [dict(cr) for cr in c.fetchall()]
                rounds.append(round_data)

            # Get global models
            c.execute(
                "SELECT * FROM fl_global_models WHERE project_id = ? ORDER BY round_number DESC",
                (project_id,))
            models = [dict(row) for row in c.fetchall()]

            # Calculate metrics
            completed_rounds = [r for r in rounds if r["status"] == "completed"]
            accuracy_trend = [{"round": r["round_number"], "accuracy": r["global_accuracy"]}
                             for r in completed_rounds if r["global_accuracy"]]
            loss_trend = [{"round": r["round_number"], "loss": r["global_loss"]}
                         for r in completed_rounds if r["global_loss"]]

            return {
                "project": dict(project),
                "total_rounds": len(rounds),
                "completed_rounds": len(completed_rounds),
                "rounds": rounds,
                "global_models": models,
                "accuracy_trend": accuracy_trend,
                "loss_trend": loss_trend,
                "client_participation": self._get_client_participation(project_id)
            }

    def _get_client_participation(self, project_id: int) -> List[Dict[str, Any]]:
        """Get client participation statistics."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute(
                "SELECT flc.client_id, flc.client_name, flc.data_size, flc.contribution_score, "
                "COUNT(fcr.id) as rounds_participated, "
                "COALESCE(AVG(fcr.local_accuracy), 0) as avg_accuracy, "
                "COALESCE(AVG(fcr.training_time_ms), 0) as avg_training_time "
                "FROM fl_clients flc "
                "LEFT JOIN fl_client_rounds fcr ON flc.client_id = fcr.client_id "
                "LEFT JOIN fl_rounds fr ON fcr.round_id = fr.id AND fr.project_id = flc.project_id "
                "WHERE flc.project_id = ? "
                "GROUP BY flc.id",
                (project_id,))

            return [dict(row) for row in c.fetchall()]

    def simulate_training(self, project_id: int, num_rounds: int = 10) -> Dict[str, Any]:
        """Simulate federated training for demonstration purposes."""
        import random
        import time

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Get project
            c.execute("SELECT * FROM fl_projects WHERE id = ?", (project_id,))
            project = c.fetchone()
            if not project:
                raise ValueError(f"Project {project_id} not found")

            # Get clients
            c.execute(
                "SELECT * FROM fl_clients WHERE project_id = ?",
                (project_id,))
            clients = c.fetchall()

            if len(clients) < project["min_clients"]:
                raise ValueError(
                    f"Not enough clients. Need {project['min_clients']}, have {len(clients)}")

            results = []
            base_accuracy = 0.5
            base_loss = 2.0

            for round_num in range(1, num_rounds + 1):
                # Create round
                participating = random.sample(list(clients),
                                           max(project["min_clients"],
                                               random.randint(project["min_clients"], len(clients))))

                c.execute(
                    "INSERT INTO fl_rounds (project_id, round_number, num_clients_participated, "
                    "model_version, status) VALUES (?, ?, ?, ?, ?)",
                    (project_id, round_num, len(participating),
                     f"round-{round_num}", "initiated"))

                round_id = c.lastrowid
                client_results = []

                for client in participating:
                    # Simulate client training
                    local_accuracy = base_accuracy + random.uniform(-0.05, 0.08)
                    local_loss = base_loss - random.uniform(0.05, 0.3)
                    training_time = random.uniform(1000, 5000)
                    data_used = random.randint(100, 1000)

                    c.execute(
                        "INSERT INTO fl_client_rounds (round_id, client_id, local_accuracy, "
                        "local_loss, training_time_ms, data_used, model_delta_size, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (round_id, client["client_id"], local_accuracy, local_loss,
                         training_time, data_used, random.randint(100000, 5000000),
                         "completed"))

                    c.execute(
                        "UPDATE fl_clients SET last_round = ?, last_heartbeat = CURRENT_TIMESTAMP, "
                        "contribution_score = contribution_score + ? WHERE id = ?",
                        (round_num, round(local_accuracy - base_accuracy + 0.1, 4), client["id"]))

                    client_results.append({
                        "client_id": client["client_id"],
                        "local_accuracy": round(local_accuracy, 4),
                        "local_loss": round(local_loss, 4),
                        "training_time_ms": round(training_time, 2)
                    })

                # Aggregate
                global_accuracy = base_accuracy + 0.05 + (round_num * 0.02)
                global_loss = base_loss - 0.15 - (round_num * 0.1)
                aggregation_time = random.uniform(500, 2000)
                comm_size = sum(cr["model_delta_size"] for cr in [
                    {"model_delta_size": random.randint(100000, 5000000)} for _ in participating
                ])

                c.execute(
                    "UPDATE fl_rounds SET global_accuracy = ?, global_loss = ?, "
                    "aggregation_time_ms = ?, communication_size_bytes = ?, "
                    "status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (round(global_accuracy, 4), round(global_loss, 4),
                     round(aggregation_time, 2), comm_size, "completed", round_id))

                # Save global model
                c.execute(
                    "INSERT INTO fl_global_models (project_id, round_number, model_version, "
                    "global_accuracy, global_loss) VALUES (?, ?, ?, ?, ?)",
                    (project_id, round_num, f"round-{round_num}-global",
                     round(global_accuracy, 4), round(global_loss, 4)))

                results.append({
                    "round": round_num,
                    "global_accuracy": round(global_accuracy, 4),
                    "global_loss": round(global_loss, 4),
                    "num_clients": len(participating),
                    "client_results": client_results
                })

                base_accuracy = global_accuracy
                base_loss = global_loss

            # Update project
            c.execute(
                "UPDATE fl_projects SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,))

            conn.commit()

            return {
                "project_id": project_id,
                "project_name": project["name"],
                "total_rounds": num_rounds,
                "final_accuracy": round(base_accuracy, 4),
                "final_loss": round(base_loss, 4),
                "rounds": results,
                "message": "Simulated training completed"
            }

    def delete_project(self, project_id: int) -> bool:
        """Delete a project and all related data."""
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM fl_projects WHERE id = ?", (project_id,))
            conn.commit()
            return True

    def update_client_status(self, project_id: int, client_id: str,
                            status: str) -> Dict[str, Any]:
        """Update client status."""
        valid_statuses = ["registered", "training", "completed", "disconnected", "failed"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute(
                "UPDATE fl_clients SET status = ?, last_heartbeat = CURRENT_TIMESTAMP "
                "WHERE project_id = ? AND client_id = ?",
                (status, project_id, client_id))

            if c.rowcount == 0:
                raise ValueError(f"Client {client_id} not found in project {project_id}")

            conn.commit()

            return {
                "project_id": project_id,
                "client_id": client_id,
                "status": status,
                "message": "Status updated"
            }

    def get_aggregation_strategy_info(self) -> Dict[str, Any]:
        """Get information about available aggregation strategies."""
        return {
            "strategies": {
                "fedavg": {
                    "name": "Federated Averaging",
                    "description": "Standard weighted average of client models based on data size",
                    "privacy_support": True,
                    "heterogeneous_support": False,
                    "communication_efficiency": "Medium"
                },
                "fedprox": {
                    "name": "Federated Proximal",
                    "description": "Adds proximal term to handle heterogeneous systems",
                    "privacy_support": True,
                    "heterogeneous_support": True,
                    "communication_efficiency": "Medium"
                },
                "fednova": {
                    "name": "FedNova",
                    "description": "Normalized averaging for heterogeneous local updates",
                    "privacy_support": True,
                    "heterogeneous_support": True,
                    "communication_efficiency": "High"
                },
                "scaffold": {
                    "name": "SCAFFOLD",
                    "description": "Uses control variates to correct client drift",
                    "privacy_support": True,
                    "heterogeneous_support": True,
                    "communication_efficiency": "Medium"
                },
                "fedbn": {
                    "name": "FedBN",
                    "description": "Keeps BatchNorm layers local for non-IID data",
                    "privacy_support": True,
                    "heterogeneous_support": True,
                    "communication_efficiency": "High"
                },
                "fedopt": {
                    "name": "FedOpt",
                    "description": "Server-side optimizer for improved convergence",
                    "privacy_support": True,
                    "heterogeneous_support": True,
                    "communication_efficiency": "Medium"
                }
            }
        }


fl_service = FederatedLearningService()