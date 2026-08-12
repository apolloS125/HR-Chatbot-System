import base64
import hashlib
import hmac
import os
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
