"""Marketplace service for model templates."""
import sqlite3
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from .modelscope_service import modelscope_service

class MarketplaceService:
    def __init__(self, db_path: str = "marketplace.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
CREATE TABLE IF NOT EXISTS model_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    tags TEXT,
    downloads INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    author TEXT,
    framework TEXT,
    task TEXT,
    is_public BOOLEAN DEFAULT 1,
    model_card TEXT,
    recommended_config TEXT,
    source TEXT DEFAULT 'modelscope',
    created_date TEXT DEFAULT CURRENT_TIMESTAMP
)
        """)

        cursor.execute("""
CREATE TABLE IF NOT EXISTS user_favorites (
    user_id TEXT,
    model_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, model_id)
)
        """)

        conn.commit()
        conn.close()

    async def get_templates(self, source: str = "all", category: str = None,
                          search: str = None, page: int = 1, per_page: int = 20) -> List[Dict]:
        """Get model templates from specified source."""
        if source == "modelscope" or source == "all":
            modelscope_models = await modelscope_service.search_models(
                query=search or "",
                page=page,
                per_page=per_page
            )

            if source == "modelscope":
                return modelscope_models

            local_templates = self._get_local_templates(category, search, page, per_page)
            return modelscope_models + local_templates
        else:
            return self._get_local_templates(category, search, page, per_page)

    def _get_local_templates(self, category: str = None, search: str = None,
                           page: int = 1, per_page: int = 20) -> List[Dict]:
        """Get local templates from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM model_templates WHERE source != 'modelscope'"
        params = []

        if category and category != "all":
            query += " AND category = ?"
            params.append(category)

        if search:
            query += " AND (name LIKE ? OR description LIKE ? OR tags LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        offset = (page - 1) * per_page
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        templates = []
        for row in rows:
            template = {
                "id": row[0],
                "name": row[1],
                "model_name": row[2],
                "description": row[3],
                "category": row[4],
                "tags": json.loads(row[5]) if row[5] else [],
                "downloads": row[6],
                "likes": row[7],
                "created_at": row[8],
                "updated_at": row[9],
                "author": row[10],
                "framework": row[11],
                "task": row[12],
                "is_public": bool(row[13]),
                "model_card": row[14],
                "recommended_config": json.loads(row[15]) if row[15] else {},
                "source": row[16]
            }
            templates.append(template)

        conn.close()
        return templates

    async def get_popular_models(self, limit: int = 20, source: str = "all") -> List[Dict]:
        """Get popular models."""
        if source == "modelscope" or source == "all":
            modelscope_popular = await modelscope_service.get_popular_models(limit=limit)

            if source == "modelscope":
                return modelscope_popular

            local_popular = self._get_local_popular(limit)
            return modelscope_popular + local_popular[:limit // 2]
        else:
            return self._get_local_popular(limit)

    def _get_local_popular(self, limit: int) -> List[Dict]:
        """Get local popular models by downloads."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
SELECT * FROM model_templates
WHERE source != 'modelscope'
ORDER BY downloads DESC
LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        templates = []
        for row in rows:
            template = {
                "id": row[0],
                "name": row[1],
                "model_name": row[2],
                "description": row[3],
                "category": row[4],
                "tags": json.loads(row[5]) if row[5] else [],
                "downloads": row[6],
                "likes": row[7],
                "created_at": row[8],
                "updated_at": row[9],
                "author": row[10],
                "framework": row[11],
                "task": row[12],
                "is_public": bool(row[13]),
                "model_card": row[14],
                "recommended_config": json.loads(row[15]) if row[15] else {},
                "source": row[16]
            }
            templates.append(template)

        conn.close()
        return templates

    async def get_model_details(self, model_id: str) -> Optional[Dict]:
        """Get model details by ID."""
        if model_id.startswith("modelscope:"):
            details = await modelscope_service.get_model_details(model_id)
            if details:
                details["source"] = "modelscope"
                return details
            return None

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM model_templates WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "id": row[0],
                "name": row[1],
                "model_name": row[2],
                "description": row[3],
                "category": row[4],
                "tags": json.loads(row[5]) if row[5] else [],
                "downloads": row[6],
                "likes": row[7],
                "created_at": row[8],
                "updated_at": row[9],
                "author": row[10],
                "framework": row[11],
                "task": row[12],
                "is_public": bool(row[13]),
                "model_card": row[14],
                "recommended_config": json.loads(row[15]) if row[15] else {},
                "source": row[16]
            }

        return None

    async def get_model_files(self, model_id: str) -> List[Dict]:
        """Get model files by ID."""
        if model_id.startswith("modelscope:"):
            return await modelscope_service.get_model_files(model_id)
        return []

    def add_local_template(self, template: Dict) -> bool:
        """Add a local template to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
INSERT OR REPLACE INTO model_templates
(id, name, model_name, description, category, tags, downloads, likes,
 created_at, updated_at, author, framework, task, is_public, model_card,
 recommended_config, source)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template.get("id", f"local_{datetime.now().timestamp()}"),
                template.get("name", ""),
                template.get("model_name", ""),
                template.get("description", ""),
                template.get("category", "llm"),
                json.dumps(template.get("tags", [])),
                template.get("downloads", 0),
                template.get("likes", 0),
                template.get("created_at", datetime.now().isoformat()),
                template.get("updated_at", datetime.now().isoformat()),
                template.get("author", ""),
                template.get("framework", ""),
                template.get("task", ""),
                int(template.get("is_public", True)),
                template.get("model_card", ""),
                json.dumps(template.get("recommended_config", {})),
                "local"
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding local template: {e}")
            return False

    def add_favorite(self, user_id: str, model_id: str) -> bool:
        """Add model to user favorites."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
INSERT OR IGNORE INTO user_favorites (user_id, model_id)
VALUES (?, ?)
            """, (user_id, model_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding favorite: {e}")
            return False

    def remove_favorite(self, user_id: str, model_id: str) -> bool:
        """Remove model from user favorites."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
DELETE FROM user_favorites
WHERE user_id = ? AND model_id = ?
            """, (user_id, model_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error removing favorite: {e}")
            return False

    def get_user_favorites(self, user_id: str) -> List[str]:
        """Get user's favorite model IDs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
SELECT model_id FROM user_favorites
WHERE user_id = ?
        """, (user_id,))

        favorites = [row[0] for row in cursor.fetchall()]
        conn.close()
        return favorites

    def get_categories(self) -> List[str]:
        """Get available categories."""
        return ["llm", "vision", "audio", "multimodal", "other"]

    def get_sources(self) -> List[str]:
        """Get available sources."""
        return ["all", "modelscope", "local"]


# Global instance
marketplace_service = MarketplaceService()
# Alias for backward compatibility
model_marketplace_service = marketplace_service

