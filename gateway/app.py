import sqlite3
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from auth import authenticate, create_key_for, require_admin
from db import get_conn, init_db
from upstream import list_all_tools
from mcp_endpoint import router as mcp_router

app = FastAPI(title="MCP Gateway")
app.include_router(mcp_router)


@app.on_event("startup")
def startup() -> None:
    init_db()


class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    role: Literal["admin", "member"] = "member"


class KeyIn(BaseModel):
    label: str = Field(default="default", max_length=50)


class ServerIn(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9]{1,19}$")
    url: str = Field(pattern=r"^https?://")
    enabled: bool = True


class ServerPatch(BaseModel):
    enabled: bool


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/me")
def me(user: dict = Depends(authenticate)) -> dict:
    return {"id": user["user_id"], "name": user["name"], "role": user["role"]}


@app.post("/api/me/keys")
def create_my_key(body: KeyIn, user: dict = Depends(authenticate)) -> dict:
    key = create_key_for(user["user_id"], body.label)
    return {"api_key": key, "note": "Shown once. Store it now."}


@app.post("/api/users", status_code=201)
def create_user(body: UserIn, _: dict = Depends(require_admin)) -> dict:
    try:
        with get_conn() as conn:
            cur = conn.execute("INSERT INTO users (name, role) VALUES (?, ?)", (body.name, body.role))
    except sqlite3.IntegrityError:
        raise HTTPException(409, f"User '{body.name}' already exists.")
    return {"id": cur.lastrowid, "name": body.name, "role": body.role}


@app.get("/api/users")
def list_users(_: dict = Depends(require_admin)) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name, role, created_at FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/users/{user_id}/keys", status_code=201)
def create_user_key(user_id: int, body: KeyIn, _: dict = Depends(require_admin)) -> dict:
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise HTTPException(404, "No such user.")
    key = create_key_for(user_id, body.label)
    return {"api_key": key, "note": "Shown once. Store it now."}


@app.get("/api/keys")
def list_keys(_: dict = Depends(require_admin)) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT k.id, u.name AS user, k.label, k.prefix, k.created_at, k.revoked_at
               FROM api_keys k JOIN users u ON u.id = k.user_id ORDER BY k.id"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/keys/{key_id}")
def revoke_key(key_id: int, _: dict = Depends(require_admin)) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP WHERE id = ? AND revoked_at IS NULL",
            (key_id,),
        )
    if cur.rowcount == 0:
        raise HTTPException(404, "No active key with that id.")
    return {"revoked": key_id}


SERVER_COLUMNS = "id, name, url, enabled, created_at"  # the credential column is never returned


@app.post("/api/servers", status_code=201)
def add_server(body: ServerIn, _: dict = Depends(require_admin)) -> dict:
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO mcp_servers (name, url, enabled) VALUES (?, ?, ?)",
                (body.name, body.url, int(body.enabled)),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, f"Server '{body.name}' already exists.")
    return {"id": cur.lastrowid, "name": body.name, "url": body.url, "enabled": body.enabled}


@app.get("/api/servers")
def list_servers(_: dict = Depends(require_admin)) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(f"SELECT {SERVER_COLUMNS} FROM mcp_servers ORDER BY id").fetchall()
    return [{**dict(r), "enabled": bool(r["enabled"])} for r in rows]


@app.patch("/api/servers/{server_id}")
def set_server_enabled(server_id: int, body: ServerPatch, _: dict = Depends(require_admin)) -> dict:
    with get_conn() as conn:
        cur = conn.execute("UPDATE mcp_servers SET enabled = ? WHERE id = ?", (int(body.enabled), server_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "No such server.")
    return {"id": server_id, "enabled": body.enabled}


@app.delete("/api/servers/{server_id}")
def remove_server(server_id: int, _: dict = Depends(require_admin)) -> dict:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "No such server.")
    return {"removed": server_id}


@app.get("/api/tools")
async def list_tools(user: dict = Depends(authenticate)) -> dict:
    """One combined menu of every enabled server's tools."""
    with get_conn() as conn:
        rows = conn.execute("SELECT name, url FROM mcp_servers WHERE enabled = 1 ORDER BY id").fetchall()
    tools, servers = await list_all_tools([dict(r) for r in rows])
    return {"tools": tools, "servers": servers}


@app.get("/api/audit")
def list_audit(limit: int = 50, _: dict = Depends(require_admin)) -> list[dict]:
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ts, user_name, server, tool, duration_ms, outcome, detail "
            "FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
