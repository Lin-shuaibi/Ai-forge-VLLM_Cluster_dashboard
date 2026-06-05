"""Authentication API endpoints."""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from services.auth_service import (
    auth_service, get_current_user, get_current_active_user,
    require_permission, TokenData, DB_PATH
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register")
async def register_user(
    username: str,
    password: str,
    email: Optional[str] = None,
    role: str = "user"
):
    try:
        user_id = auth_service.create_user(username, password, email, role)
        return {
            "user_id": user_id,
            "username": username,
            "message": "User registered successfully"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"})
    access_token = auth_service.create_access_token(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        }
    }


@router.get("/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_active_user)):
    user = auth_service.get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/api-keys", dependencies=[Depends(require_permission("api_key", "create"))])
async def create_api_key(
    name: str,
    scopes: Optional[List[str]] = None,
    current_user: TokenData = Depends(get_current_user)
):
    key_id, plain_key = auth_service.create_api_key(current_user.user_id, name, scopes)
    return {
        "key_id": key_id,
        "api_key": plain_key,
        "name": name,
        "scopes": scopes,
        "warning": "Save this API key now, it won't be shown again"
    }


@router.get("/api-keys", dependencies=[Depends(require_permission("api_key", "read"))])
async def list_api_keys(current_user: TokenData = Depends(get_current_user)):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT id, name, scopes, expires_at, last_used, created_at "
            "FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (current_user.user_id,))
        keys = [dict(row) for row in c.fetchall()]
        return {"api_keys": keys}


@router.delete("/api-keys/{key_id}", dependencies=[Depends(require_permission("api_key", "delete"))])
async def delete_api_key(
    key_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    with sqlite3.connect(str(DB_PATH)) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM api_keys WHERE id = ? AND user_id = ?",
                 (key_id, current_user.user_id))
        if not c.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        c.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        conn.commit()
    return {"message": "API key deleted"}


@router.get("/permissions/{role}")
async def get_role_permissions(
    role: str,
    current_user: TokenData = Depends(require_permission("permission", "read"))
):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT resource, action FROM permissions WHERE role = ? ORDER BY resource, action",
            (role,))
        permissions = [{"resource": row["resource"], "action": row["action"]} for row in c.fetchall()]
        return {"role": role, "permissions": permissions}


@router.post("/logout")
async def logout(current_user: TokenData = Depends(get_current_user)):
    return {"message": "Logged out successfully"}