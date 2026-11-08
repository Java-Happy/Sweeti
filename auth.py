import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import Header, HTTPException

from storage import DB_PATH

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
PASSWORD_ITERATIONS = 310_000
SECRET_PATH = Path(__file__).with_name(".auth_secret")


def _connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    with _connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")


def hash_password(password, salt=None):
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, PASSWORD_ITERATIONS
    )
    return salt_bytes.hex(), digest.hex()


def verify_password(password, salt, expected_hash):
    _, actual_hash = hash_password(password, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def create_user(username, password, role="member"):
    from datetime import datetime, timezone

    salt, password_hash = hash_password(password)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        cursor = conn.execute(
            """INSERT INTO users (username, password_salt, password_hash, role, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (username, salt, password_hash, role, created_at),
        )
        return {"id": cursor.lastrowid, "username": username, "role": role, "created_at": created_at}


def _secret():
    configured = os.getenv("CRYPTO_RADAR_AUTH_SECRET")
    if configured:
        if len(configured) < 32:
            raise RuntimeError("CRYPTO_RADAR_AUTH_SECRET must contain at least 32 characters")
        return configured.encode("utf-8")

    if not SECRET_PATH.exists():
        try:
            SECRET_PATH.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        except FileExistsError:
            pass
    return SECRET_PATH.read_text(encoding="utf-8").strip().encode("utf-8")


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def issue_token(user):
    payload = {
        "sub": int(user["id"]),
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    encoded = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest())
    return encoded + "." + signature


def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization[7:].strip()
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = _b64(
            hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="登录状态无效或已过期")

    with _connection() as conn:
        row = conn.execute(
            "SELECT id, username, role, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="账号不存在")
    return dict(row)


def authenticate(username, password):
    with _connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_salt, password_hash, role, created_at "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None or not verify_password(password, row["password_salt"], row["password_hash"]):
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "created_at": row["created_at"],
    }
