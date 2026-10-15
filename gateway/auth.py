import hashlib
import secrets

from fastapi import Depends, Header, HTTPException

from db import get_conn


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_key_for(user_id: int, label: str) -> str:
    key = "gw_" + secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (user_id, label, prefix, key_hash) VALUES (?, ?, ?, ?)",
            (user_id, label, key[:7], hash_key(key)),
        )
    return key


def authenticate(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing API key. Send 'Authorization: Bearer <key>'.")
    key = authorization[7:].strip()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT u.id AS user_id, u.name, u.role, k.id AS key_id
               FROM api_keys k JOIN users u ON u.id = k.user_id
               WHERE k.key_hash = ? AND k.revoked_at IS NULL""",
            (hash_key(key),),
        ).fetchone()
    if row is None:
        raise HTTPException(401, "Invalid or revoked API key.")
    return dict(row)


def require_admin(user: dict = Depends(authenticate)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Admin role required.")
    return user
