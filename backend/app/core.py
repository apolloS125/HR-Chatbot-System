import base64
import hashlib
import hmac
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "hr_chatbot")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
SEAWEED_MASTER_URL = os.getenv("SEAWEED_MASTER_URL", "http://localhost:9333")
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
    app.state.mongo_client = AsyncIOMotorClient(MONGODB_URL)
    app.state.mongo = app.state.mongo_client[MONGODB_DATABASE]
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.mongo.command("ping")
    await app.state.redis.ping()
    await app.state.mongo.employees.create_index("work_email", unique=True)
    await app.state.mongo.employees.create_index("line_user_id", unique=True, sparse=True)
    await app.state.mongo.leave_requests.create_index("source_event_id", unique=True, sparse=True)
    await app.state.mongo.employees.update_one({"_id": "E001"}, {"$setOnInsert": {"name": "พนักงานตัวอย่าง", "work_email": "employee@example.com", "role": "employee", "active": True, "balances": {"vacation": 10, "sick": 30, "personal": 5}}}, upsert=True)
    await app.state.mongo.faqs.update_one({"_id": "work-hours"}, {"$setOnInsert": {"keyword": "เวลาทำงาน", "question": "บริษัททำงานกี่โมง", "answer": "เวลาทำงานปกติคือ 09:00–18:00 น. วันจันทร์ถึงวันศุกร์", "active": True}}, upsert=True)
    # Weaviate is a rebuildable index, never source of truth.
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(f"{WEAVIATE_URL}/v1/schema", json={"class": "HrPolicy", "vectorizer": "none", "properties": [{"name": "mongoId", "dataType": ["text"]}, {"name": "answer", "dataType": ["text"]}]})
            await client.post(f"{WEAVIATE_URL}/v1/objects", json={"class": "HrPolicy", "properties": {"mongoId": "work-hours", "answer": "เวลาทำงานปกติคือ 09:00–18:00 น. วันจันทร์ถึงวันศุกร์"}})
    except httpx.HTTPError:
        pass
    yield
    app.state.mongo_client.close()
    await app.state.redis.aclose()


async def db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.mongo

async def cache(request: Request) -> Redis:
    return request.app.state.redis

def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="invalid admin key")

def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

def valid_line_signature(body: bytes, signature: str | None) -> bool:
    expected = base64.b64encode(hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()).decode()
    return bool(signature and LINE_CHANNEL_SECRET and hmac.compare_digest(expected, signature))

def issue_liff_token(line_user_id: str) -> str:
    payload = base64url(f"{line_user_id}:{int(time.time()) + 3600}".encode())
    signature = base64url(hmac.new(LIFF_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"

def read_liff_token(token: str) -> str | None:
    try:
        payload, signature = token.split(".", 1)
        expected = base64url(hmac.new(LIFF_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        user_id, expires_at = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode().rsplit(":", 1)
        return user_id if hmac.compare_digest(signature, expected) and int(expires_at) >= time.time() else None
    except (ValueError, UnicodeDecodeError):
        return None

async def seaweed_upload(name: str, content: bytes, content_type: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{SEAWEED_MASTER_URL}/dir/assign")
        response.raise_for_status()
        assigned = response.json()
        upload = await client.post(f"http://{assigned['url']}/{assigned['fid']}", files={"file": (name, content, content_type)})
        upload.raise_for_status()
    return assigned["fid"]


async def seaweed_read(fid: str) -> bytes:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"http://seaweedfs:9333/{fid}")
        response.raise_for_status()
        return response.content
