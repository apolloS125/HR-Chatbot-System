import base64
import asyncio
import hashlib
import hmac
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis

from .vector_store import ensure_policy_index

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
HR_USERNAME = os.getenv("HR_USERNAME", "hr")
HR_PASSWORD = os.getenv("HR_PASSWORD", "change-me")
LIFF_SESSION_SECRET = os.getenv("LIFF_SESSION_SECRET", ADMIN_API_KEY)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if any(value in {"", "change-me"} or value.startswith("change-this-") for value in (ADMIN_API_KEY, LIFF_SESSION_SECRET, HR_PASSWORD)):
        raise RuntimeError("Configure ADMIN_API_KEY, LIFF_SESSION_SECRET and HR_PASSWORD before starting")
    app.state.mongo_client = AsyncIOMotorClient(MONGODB_URL)
    app.state.mongo = app.state.mongo_client[MONGODB_DATABASE]
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.mongo.command("ping")
    hello = await app.state.mongo.command("hello")
    if not hello.get("setName") and hello.get("msg") != "isdbgrid":
        raise RuntimeError("MongoDB requires a replica set for leave transactions; start it with compose")
    await app.state.redis.ping()
    await app.state.mongo.employees.create_index("work_email", unique=True)
    await app.state.mongo.employees.create_index("line_user_id", unique=True, sparse=True)
    await app.state.mongo.leave_requests.create_index("source_event_id", unique=True, sparse=True)
    await app.state.mongo.leave_requests.create_index([("employee_code", 1), ("status", 1), ("start_date", 1)])
    await app.state.mongo.line_oauth_sessions.create_index("expires_at", expireAfterSeconds=0)
    await app.state.mongo.employees.update_one({"_id": "E001"}, {"$setOnInsert": {"name": "พนักงานตัวอย่าง", "work_email": "employee@example.com", "role": "employee", "active": True, "balances": {"vacation": 10, "sick": 30, "personal": 5}}}, upsert=True)
    await app.state.mongo.faqs.update_one({"_id": "work-hours"}, {"$setOnInsert": {"keyword": "เวลาทำงาน", "question": "บริษัททำงานกี่โมง", "answer": "เวลาทำงานปกติคือ 09:00–18:00 น. วันจันทร์ถึงวันศุกร์", "active": True}}, upsert=True)
    # Weaviate is a rebuildable index, never source of truth.
    try:
        policies = [policy async for policy in app.state.mongo.faqs.find({"active": True})]
        async with httpx.AsyncClient(base_url=WEAVIATE_URL, timeout=3) as client:
            await ensure_policy_index(client, policies)
    except (httpx.HTTPError, ValueError, KeyError):
        logging.getLogger(__name__).warning("Policy index unavailable; using local search", exc_info=True)
    yield
    app.state.mongo_client.close()
    await app.state.redis.aclose()


async def db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.mongo

async def cache(request: Request) -> Redis:
    return request.app.state.redis

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split(":", 1)
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


async def require_admin(x_admin_key: Annotated[str | None, Header()] = None, authorization: Annotated[str | None, Header()] = None, database=Depends(db)):
    if authorization and authorization.startswith("Basic "):
        try:
            username, password = base64.b64decode(authorization[6:], validate=True).decode().split(":", 1)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(status_code=401, detail="invalid credentials")
        if hmac.compare_digest(username.encode(), HR_USERNAME.encode()) and hmac.compare_digest(password.encode(), HR_PASSWORD.encode()):
            return {"id": HR_USERNAME, "role": "admin"}
        employee = await database.employees.find_one({"_id": username.upper(), "active": True})
        if employee and check_password(password, employee.get("password_hash", "")):
            if employee["role"] not in {"hr", "admin"}:
                raise HTTPException(status_code=403, detail="HR access required")
            return {"id": employee["_id"], "role": employee["role"]}
    elif x_admin_key and hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        return {"id": "api-key", "role": "admin"}
    raise HTTPException(status_code=401, detail="invalid credentials")


async def transaction(database, operation):
    async with await database.client.start_session() as session:
        return await session.with_transaction(operation)


async def audit(database, actor, action, subject, session=None):
    from datetime import datetime, timezone
    await database.audit_logs.insert_one({"actor": actor["id"], "action": action, "subject": subject, "created_at": datetime.now(timezone.utc)}, session=session)


def document_view(item):
    private = {"_id", "attachment_url", "deliveries", "delivery_lease", "notification_to", "notification_key"}
    result = {"id": str(item["_id"]), **{key: value for key, value in item.items() if key not in private}}
    if not result.get("attachment_id") and item.get("attachment_url"):
        # Read legacy attachments without returning the expired session token.
        from urllib.parse import urlsplit
        match = re.fullmatch(r"/api/liff/attachments/(F-[a-f0-9]+)", urlsplit(item["attachment_url"]).path)
        if match:
            result["attachment_id"] = match[1]
    return result


async def file_response(database, file_id, employee_code=None):
    from fastapi.responses import Response
    from urllib.parse import quote
    query = {"_id": file_id}
    if employee_code:
        query["employee_code"] = employee_code
    file = await database.files.find_one(query)
    if not file:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return Response(await seaweed_read(file["fid"]), media_type=file["content_type"], headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file['name'])}", "Cache-Control": "private, no-store"})

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


async def seaweed_location(fid: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{SEAWEED_MASTER_URL}/dir/lookup", params={"volumeId": fid.partition(",")[0]})
        response.raise_for_status()
        return response.json()["locations"][0]["url"]


async def seaweed_read(fid: str) -> bytes:
    volume_url = await seaweed_location(fid)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"http://{volume_url}/{fid}")
        response.raise_for_status()
        return response.content


async def seaweed_delete(fid: str) -> None:
    volume_url = await seaweed_location(fid)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.delete(f"http://{volume_url}/{fid}")
        response.raise_for_status()


async def storage_health() -> None:
    async with httpx.AsyncClient(timeout=3) as client:
        weaviate, seaweed = await asyncio.gather(
            client.get(f"{WEAVIATE_URL}/v1/.well-known/ready"),
            client.get(f"{SEAWEED_MASTER_URL}/cluster/status"),
        )
        weaviate.raise_for_status()
        seaweed.raise_for_status()
