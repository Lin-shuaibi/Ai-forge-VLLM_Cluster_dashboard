"""ModelScope API integration service."""
import httpx
import asyncio
from typing import List, Dict, Optional
import json
from datetime import datetime

class ModelScopeService:
    def __init__(self):
        self.base_url = "https://www.modelscope.cn/api/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    async def _make_put_request(self, endpoint: str, data: Optional[Dict] = None):
        """Make HTTP PUT request to ModelScope API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}{endpoint}"
                response = await client.put(url, json=data or {}, headers=self.headers)
                response.raise_for_status()
                resp_data = response.json()
                if resp_data.get("Success") and "Data" in resp_data:
                    resp_data = resp_data["Data"]
                return resp_data
        except Exception as e:
            print(f"ModelScope PUT error: {e}")
            return None

    async def _make_get_request(self, endpoint: str):
        """Make HTTP GET request to ModelScope API."""
        cache_key = f"GET:{endpoint}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now().timestamp() - timestamp) < self.cache_ttl:
                return cached_data

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.base_url}{endpoint}"
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                resp_data = response.json()
                if resp_data.get("Success") and "Data" in resp_data:
                    resp_data = resp_data["Data"]
                self.cache[cache_key] = (resp_data, datetime.now().timestamp())
                return resp_data
        except Exception as e:
            print(f"ModelScope GET error: {e}")
            return None

    async def search_models(self, query: str, page: int = 1, per_page: int = 20) -> List[Dict]:
        # ModelScope API: "search" param is broken, use "name" for actual filtering
        data = {
            "page_number": page,
            "page_size": per_page
        }
        if query:
            data["name"] = query

        result = await self._make_put_request("/models", data=data)
        if not result or "Models" not in result:
            return []

        models = result.get("Models", [])
        formatted = []
        for m in models:
            raw_name = m.get("Name", "")
            path = m.get("Path", "")
            # Build full name: Path/Name (e.g., stepfun-ai/Step-3.7-Flash)
            # Use -- as separator in ID to avoid URL routing issues with /
            full_name = f"{path}/{raw_name}" if path else raw_name
            safe_id = f"{path}--{raw_name}" if path else raw_name
            name = full_name
            desc = m.get("Description", "")
            if isinstance(desc, str) and len(desc) > 200:
                desc = desc[:200]

            frameworks = m.get("Frameworks", "")
            if isinstance(frameworks, str) and frameworks:
                try:
                    fw_list = json.loads(frameworks)
                except:
                    fw_list = []
            elif isinstance(frameworks, list):
                fw_list = frameworks
            else:
                fw_list = []
            framework = fw_list[0] if fw_list else ""

            libraries = m.get("Libraries", "")
            if isinstance(libraries, str) and libraries:
                try:
                    tags = json.loads(libraries)
                except:
                    tags = []
            elif isinstance(libraries, list):
                tags = libraries
            else:
                tags = []
            tags = tags[:5]

            downloads = m.get("Downloads", 0)
            if isinstance(downloads, str):
                try:
                    downloads = int(downloads)
                except:
                    downloads = 0

            # Use safe ID with -- separator
            model_id = f"modelscope:{safe_id}" if safe_id else str(m.get("Id", ""))

            formatted.append({
                "id": model_id,
                "name": name,
                "model_name": name,
                "description": desc if isinstance(desc, str) else "",
                "category": self._infer_category(m),
                "tags": tags,
                "downloads": downloads,
                "likes": 0,
                "author": m.get("CreatedBy", ""),
                "framework": framework,
                "task": "",
                "model_card": f"https://modelscope.cn/models/{name}",
                "source": "modelscope",
                "created_date": self._parse_time(m.get("CreatedTime"))
            })
        return formatted

    async def get_model_details(self, model_id: str) -> Optional[Dict]:
        """Get model details by ModelScope name (namespace/model-name)."""
        # Strip prefix if present
        if model_id.startswith("modelscope:"):
            model_id = model_id[11:]
        # Convert -- back to / for API call
        model_id = model_id.replace("--", "/")
        endpoint = f"/models/{model_id}"
        result = await self._make_get_request(endpoint)
        if not result:
            return None

        # API returns short name (e.g. "Qwen3-0.6B"), use full path for download CLI compatibility
        name = model_id  # full path like "Qwen/Qwen3-0.6B"
        desc = result.get("Description", "")
        if isinstance(desc, str) and len(desc) > 500:
            desc = desc[:500]

        frameworks = result.get("Frameworks", "")
        if isinstance(frameworks, str) and frameworks:
            try:
                fw_list = json.loads(frameworks)
            except:
                fw_list = []
        elif isinstance(frameworks, list):
            fw_list = frameworks
        else:
            fw_list = []

        libraries = result.get("Libraries", "")
        if isinstance(libraries, str) and libraries:
            try:
                tags = json.loads(libraries)
            except:
                tags = []
        elif isinstance(libraries, list):
            tags = libraries
        else:
            tags = []

        downloads = result.get("Downloads", 0)
        if isinstance(downloads, str):
            try:
                downloads = int(downloads)
            except:
                downloads = 0

        model_info = result.get("ModelInfos", {})
        files = []
        for fmt_name, fmt_data in model_info.items():
            if isinstance(fmt_data, dict) and "files" in fmt_data:
                for f in fmt_data["files"]:
                    files.append({
                        "name": f.get("name", ""),
                        "size": f.get("size", 0),
                        "sha256": f.get("sha256", ""),
                        "format": fmt_name
                    })

        # Use safe ID with -- separator
        safe_id = name.replace("/", "--")
        return {
            "id": f"modelscope:{safe_id}",
            "name": name,
            "model_name": name,
            "description": desc if isinstance(desc, str) else "",
            "category": self._infer_category(result),
            "tags": tags[:5],
            "downloads": downloads,
            "likes": 0,
            "author": result.get("CreatedBy", ""),
            "framework": fw_list[0] if fw_list else "",
            "task": "",
            "model_card": f"https://modelscope.cn/models/{name}",
            "recommended_config": {},
            "source": "modelscope",
            "files": files,
            "config": {}
        }

    async def get_model_files(self, model_id: str) -> List[Dict]:
        """Get model files by ModelScope name."""
        if model_id.startswith("modelscope:"):
            model_id = model_id[11:]
        # Convert -- back to / for API call
        model_id = model_id.replace("--", "/")
        endpoint = f"/models/{model_id}"
        result = await self._make_get_request(endpoint)
        if not result:
            return []

        model_info = result.get("ModelInfos", {})
        files = []
        for fmt_name, fmt_data in model_info.items():
            if isinstance(fmt_data, dict) and "files" in fmt_data:
                for f in fmt_data["files"]:
                    files.append({
                        "name": f.get("name", ""),
                        "size": f.get("size", 0),
                        "sha256": f.get("sha256", ""),
                        "format": fmt_name
                    })
        return files

    async def get_popular_models(self, limit: int = 20) -> List[Dict]:
        """Get popular/hot models."""
        return await self.search_models("", page=1, per_page=limit)

    def _infer_category(self, model: Dict) -> str:
        model_type = model.get("ModelType", "")
        if isinstance(model_type, list):
            model_type = " ".join(model_type)
        mt_lower = str(model_type).lower()

        if any(t in mt_lower for t in ["llm", "text", "qwen", "glm", "chat", "language"]):
            return "llm"
        elif any(t in mt_lower for t in ["vision", "image", "cv", "video"]):
            return "vision"
        elif any(t in mt_lower for t in ["audio", "speech", "tts", "asr"]):
            return "audio"
        elif any(t in mt_lower for t in ["multimodal", "multi-modal", "multi_modal"]):
            return "multimodal"
        return "other"

    def _parse_time(self, ts) -> Optional[str]:
        if not ts:
            return None
        try:
            ts_int = int(ts)
            return datetime.fromtimestamp(ts_int).isoformat()
        except:
            return None


# Global instance
modelscope_service = ModelScopeService()