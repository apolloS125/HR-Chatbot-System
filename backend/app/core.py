import base64
import hashlib
import hmac
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

import asyncpg
from fastapi import FastAPI, Header, HTTPException, Request


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hr:hr@localhost:5432/hr_chatbot")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
LINE_LOGIN_CHANNEL_ID = os.getenv("LINE_LOGIN_CHANNEL_ID", "")
LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me")
LIFF_SESSION_SECRET = os.getenv("LIFF_SESSION_SECRET", ADMIN_API_KEY)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    yield
    await app.state.db.close()


async def db(request: Request) -> asyncpg.Pool:
    return request.app.state.db


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="invalid admin key")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def valid_line_signature(body: bytes, signature: str | None) -> bool:
    if not signature or not LINE_CHANNEL_SECRET:
        return False
    expected = base64.b64encode(
        hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


def issue_liff_token(line_user_id: str) -> str:
    payload = base64url(f"{line_user_id}:{int(time.time()) + 3600}".encode())
    signature = base64url(hmac.new(LIFF_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_liff_token(token: str) -> str | None:
    try:
        payload, signature = token.split(".", 1)
        expected = base64url(hmac.new(LIFF_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        line_user_id, expires_at = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode().rsplit(":", 1)
        if not hmac.compare_digest(signature, expected) or int(expires_at) < time.time():
            return None
        return line_user_id
    except (ValueError, UnicodeDecodeError):
        return None
