"""Authentication and authorization service."""
import hashlib
import json
import secrets
import time
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "vllm_dashboard.db"
SECRET_KEY = "vllm-dashboard-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()


class TokenData:
    def __init__(self, username: str, role: str, user_id: str):
        self.username = username
        self.role = role
        self.user_id = user_id


class AuthService:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()

            c.execute("CREATE TABLE IF NOT EXISTS users ("
                "id TEXT PRIMARY KEY, "
                "username TEXT UNIQUE NOT NULL, "
                "email TEXT UNIQUE, "
                "password_hash TEXT NOT NULL, "
                "role TEXT NOT NULL DEFAULT 'user', "
                "is_active BOOLEAN DEFAULT 1, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "last_login TIMESTAMP, "
                "metadata TEXT)")

            c.execute("CREATE TABLE IF NOT EXISTS api_keys ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "key_hash TEXT NOT NULL, "
                "name TEXT, "
                "scopes TEXT, "
                "expires_at TIMESTAMP, "
                "last_used TIMESTAMP, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)")

            c.execute("CREATE TABLE IF NOT EXISTS sessions ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT NOT NULL, "
                "token_hash TEXT NOT NULL, "
                "user_agent TEXT, "
                "ip_address TEXT, "
                "expires_at TIMESTAMP NOT NULL, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE)")

            c.execute("CREATE TABLE IF NOT EXISTS permissions ("
                "id TEXT PRIMARY KEY, "
                "role TEXT NOT NULL, "
                "resource TEXT NOT NULL, "
                "action TEXT NOT NULL, "
                "UNIQUE(role, resource, action))")

            c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
            if c.fetchone()[0] == 0:
                password_hash = self._hash_password("admin123")
                c.execute(
                    "INSERT INTO users (id, username, password_hash, role) VALUES (?, ?, ?, ?)",
                    (secrets.token_hex(16), "admin", password_hash, "admin"))

            default_permissions = [
                ("admin", "*", "create"),
                ("admin", "*", "read"),
                ("admin", "*", "update"),
                ("admin", "*", "delete"),
                ("admin", "*", "execute"),
                ("user", "cluster", "read"),
                ("user", "model", "read"),
                ("user", "benchmark", "read"),
                ("user", "download", "read"),
                ("user", "chat", "execute"),
            ]
            for role, resource, action in default_permissions:
                c.execute(
                    "INSERT OR IGNORE INTO permissions (id, role, resource, action) VALUES (?, ?, ?, ?)",
                    (f"{role}_{resource}_{action}", role, resource, action))

            conn.commit()

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        if not password_hash or "$" not in password_hash:
            return False
        salt, hash_value = password_hash.split("$", 1)
        return hash_value == hashlib.sha256((salt + password).encode()).hexdigest()

    def create_user(self, username: str, password: str, email: str = None, role: str = "user") -> str:
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            if c.fetchone():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
            if email:
                c.execute("SELECT id FROM users WHERE email = ?", (email,))
                if c.fetchone():
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
            user_id = secrets.token_hex(16)
            password_hash = self._hash_password(password)
            c.execute(
                "INSERT INTO users (id, username, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, email, password_hash, role))
            conn.commit()
            return user_id

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT id, username, email, password_hash, role, is_active FROM users WHERE username = ?",
                (username,))
            user = c.fetchone()
            if not user:
                return None
            if not self._verify_password(password, user["password_hash"]):
                return None
            if not user["is_active"]:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")
            c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
            conn.commit()
            return dict(user)

    def create_access_token(self, user: Dict) -> str:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + expires_delta
        to_encode = {
            "sub": user["username"],
            "user_id": user["id"],
            "role": user["role"],
            "exp": expire
        }
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Optional[TokenData]:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            user_id = payload.get("user_id")
            role = payload.get("role")
            if username is None or user_id is None:
                return None
            return TokenData(username=username, role=role, user_id=user_id)
        except jwt.PyJWTError:
            return None

    def check_permission(self, role: str, resource: str, action: str) -> bool:
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM permissions WHERE role = ? AND resource = ? AND action = ?",
                     (role, resource, action))
            if c.fetchone():
                return True
            c.execute("SELECT 1 FROM permissions WHERE role = ? AND resource = '*' AND action = ?",
                     (role, action))
            return c.fetchone() is not None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT id, username, email, role, is_active, created_at, last_login FROM users WHERE id = ?",
                (user_id,))
            user = c.fetchone()
            return dict(user) if user else None

    def create_api_key(self, user_id: str, name: str, scopes: List[str] = None) -> Tuple[str, str]:
        plain_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        key_id = secrets.token_hex(16)
        with sqlite3.connect(str(DB_PATH)) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO api_keys (id, user_id, key_hash, name, scopes) VALUES (?, ?, ?, ?, ?)",
                (key_id, user_id, key_hash, name, json.dumps(scopes) if scopes else None))
            conn.commit()
        return key_id, plain_key

    def verify_api_key(self, api_key: str) -> Optional[Dict]:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT ak.id, ak.user_id, ak.name, ak.scopes, u.username, u.role "
                "FROM api_keys ak JOIN users u ON ak.user_id = u.id "
                "WHERE ak.key_hash = ? AND (ak.expires_at IS NULL OR ak.expires_at > CURRENT_TIMESTAMP)",
                (key_hash,))
            result = c.fetchone()
            if not result:
                return None
            c.execute("UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (result["id"],))
            conn.commit()
            return dict(result)


auth_service = AuthService()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    token_data = auth_service.verify_token(credentials.credentials)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"})
    return token_data


async def get_current_active_user(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    return current_user


def require_permission(resource: str, action: str):
    def permission_dependency(current_user: TokenData = Depends(get_current_user)):
        if not auth_service.check_permission(current_user.role, resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return permission_dependency