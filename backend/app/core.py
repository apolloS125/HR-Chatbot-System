import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import quote, urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .observability import shutdown_tracing
from .vector_store import WEAVIATE_API_KEY, ensure_policy_index, weaviate_headers

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "hr_chatbot")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080")
SEAWEED_MASTER_URL = os.getenv("SEAWEED_MASTER_URL", "http://localhost:9333")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
LINE_LOGIN_CHANNEL_ID = os.getenv("LINE_LOGIN_CHANNEL_ID", "")
LIFF_CHANNEL_ID = os.getenv("LIFF_CHANNEL_ID") or LINE_LOGIN_CHANNEL_ID
LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
HR_USERNAME = os.getenv("HR_USERNAME", "hr")
HR_PASSWORD = os.getenv("HR_PASSWORD", "")
LIFF_SESSION_SECRET = os.getenv("LIFF_SESSION_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://ai.psu.blue/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-6-luna")


def validate_secrets() -> None:
    required = {
        "ADMIN_API_KEY": (ADMIN_API_KEY, 32),
        "LIFF_SESSION_SECRET": (LIFF_SESSION_SECRET, 32),
        "HR_PASSWORD": (HR_PASSWORD, 12),
        "WEAVIATE_API_KEY": (WEAVIATE_API_KEY, 32),
    }
    for name, (value, minimum) in required.items():
        if len(value) < minimum or len(set(value)) < 8 or value.startswith("change-"):
            raise RuntimeError(f"Configure a strong {name} before starting")
    if LIFF_SESSION_SECRET in {ADMIN_API_KEY, HR_PASSWORD}:
        raise RuntimeError("LIFF_SESSION_SECRET must be independent of admin credentials")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secrets()

    app.state.mongo_client = AsyncIOMotorClient(MONGODB_URL)
    app.state.mongo = app.state.mongo_client[MONGODB_DATABASE]
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await app.state.mongo.command("ping")
    hello = await app.state.mongo.command("hello")
    if not hello.get("setName") and hello.get("msg") != "isdbgrid":
        raise RuntimeError(
            "MongoDB requires a replica set for leave transactions; start it with compose"
        )
    await app.state.redis.ping()
    await app.state.mongo.employees.create_index("work_email", unique=True)
    await app.state.mongo.employees.create_index("line_user_id", unique=True, sparse=True)
    await app.state.mongo.leave_requests.create_index("source_event_id", unique=True, sparse=True)
    await app.state.mongo.leave_requests.create_index(
        [("employee_code", 1), ("status", 1), ("start_date", 1)]
    )
    await app.state.mongo.line_oauth_sessions.create_index("expires_at", expireAfterSeconds=0)
    sample_employee = {
        "name": "พนักงานตัวอย่าง",
        "work_email": "employee@example.com",
        "role": "employee",
        "active": True,
        "balances": {"vacation": 10, "sick": 30, "personal": 5},
    }
    await app.state.mongo.employees.update_one(
        {"_id": "E001"},
        {"$setOnInsert": sample_employee},
        upsert=True,
    )
    sample_faq = {
        "keyword": "เวลาทำงาน",
        "question": "บริษัททำงานกี่โมง",
        "answer": "เวลาทำงานปกติคือ 09:00–18:00 น. วันจันทร์ถึงวันศุกร์",
        "active": True,
    }
    await app.state.mongo.faqs.update_one(
        {"_id": "work-hours"},
        {"$setOnInsert": sample_faq},
        upsert=True,
    )
    # Weaviate is a rebuildable index, never source of truth.
    try:
        policies = [policy async for policy in app.state.mongo.faqs.find({"active": True})]
        async with httpx.AsyncClient(base_url=WEAVIATE_URL, timeout=3) as client:
            await ensure_policy_index(client, policies)
    except (httpx.HTTPError, ValueError, KeyError):
        logging.getLogger(__name__).warning(
            "Policy index unavailable; using local search", exc_info=True
        )
    yield
    app.state.mongo_client.close()
    await app.state.redis.aclose()
    await asyncio.to_thread(shutdown_tracing)


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
        actual = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=16384,
            r=8,
            p=1,
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


async def authenticate_admin(
    authorization: str | None,
    x_admin_key: str | None,
    database,
    redis,
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if len(token) != 43:
            raise HTTPException(status_code=401, detail="invalid credentials")
        stored = await redis.get(f"dashboard-session:{sha256(token)}")
        if not stored:
            raise HTTPException(status_code=401, detail="session expired")
        session = json.loads(stored)
        if session["bootstrap"]:
            if session["version"] == sha256(HR_PASSWORD) and session["id"] == HR_USERNAME:
                return {"id": HR_USERNAME, "role": "admin", "bootstrap": True}
        else:
            employee = await database.employees.find_one(
                {"_id": session["id"], "active": True, "role": {"$in": ["hr", "admin"]}}
            )
            if employee and session["version"] == sha256(employee.get("password_hash", "")):
                return {"id": employee["_id"], "role": employee["role"]}
        raise HTTPException(status_code=401, detail="session expired")
    if authorization and authorization.startswith("Basic "):
        try:
            username, password = (
                base64.b64decode(authorization[6:], validate=True).decode().split(":", 1)
            )
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(status_code=401, detail="invalid credentials")
        if len(username) > 120 or len(password) > 128:
            raise HTTPException(status_code=401, detail="invalid credentials")
        valid_hr_login = (
            bool(HR_PASSWORD)
            and hmac.compare_digest(username.encode(), HR_USERNAME.encode())
            and hmac.compare_digest(password.encode(), HR_PASSWORD.encode())
        )
        if valid_hr_login:
            return {"id": HR_USERNAME, "role": "admin", "bootstrap": True}
        employee = await database.employees.find_one({"_id": username.upper(), "active": True})
        if employee and await asyncio.to_thread(
            check_password, password, employee.get("password_hash", "")
        ):
            if employee["role"] not in {"hr", "admin"}:
                raise HTTPException(status_code=403, detail="HR access required")
            return {"id": employee["_id"], "role": employee["role"]}
    elif (
        x_admin_key
        and ADMIN_API_KEY
        and hmac.compare_digest(x_admin_key.encode(), ADMIN_API_KEY.encode())
    ):
        return {"id": "api-key", "role": "admin"}
    raise HTTPException(status_code=401, detail="invalid credentials")


_RESERVE_LOGIN = """
local ip = tonumber(redis.call('GET', KEYS[1]) or '0')
local account = tonumber(redis.call('GET', KEYS[2]) or '0')
if ip >= 60 or account >= 10 then return 0 end
for _, key in ipairs(KEYS) do
    if redis.call('INCR', key) == 1 then redis.call('EXPIRE', key, 300) end
end
return 1
"""
_RELEASE_LOGIN = """
for _, key in ipairs(KEYS) do
    if tonumber(redis.call('GET', key) or '0') > 0 then redis.call('DECR', key) end
end
return 1
"""


async def require_admin(
    request: Request,
    x_admin_key: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    database=Depends(db),
    redis=Depends(cache),
):
    peer = request.client.host if request.client else "unknown"
    account = f"anonymous:{peer}"
    if authorization and len(authorization) > 12000:
        raise HTTPException(status_code=401, detail="invalid credentials")
    if authorization and authorization.startswith("Bearer "):
        account = f"session:{sha256(authorization[7:])}"
    elif x_admin_key:
        account = f"api-key:{sha256(x_admin_key)}"
    elif authorization and authorization.startswith("Basic "):
        try:
            account = (
                base64.b64decode(authorization[6:], validate=True).decode().split(":", 1)[0].upper()
            )
        except (ValueError, UnicodeDecodeError):
            pass
    keys = (f"login-ip:{sha256(peer)}", f"login-account:{sha256(account)}")
    try:
        if not await redis.eval(_RESERVE_LOGIN, 2, *keys):
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts; try again in 5 minutes",
                headers={"Retry-After": "300"},
            )
        actor = await authenticate_admin(authorization, x_admin_key, database, redis)
        await redis.eval(_RELEASE_LOGIN, 2, *keys)
        return actor
    except RedisError as error:
        raise HTTPException(status_code=503, detail="Authentication unavailable") from error


async def create_dashboard_session(actor, database, redis) -> str:
    if actor["id"] == "api-key":
        raise HTTPException(status_code=403, detail="Use personal credentials for Dashboard login")
    bootstrap = actor.get("bootstrap", False)
    employee = None if bootstrap else await database.employees.find_one({"_id": actor["id"]})
    version = HR_PASSWORD if bootstrap else employee.get("password_hash", "")
    token = secrets.token_urlsafe(32)
    value = {"id": actor["id"], "bootstrap": bootstrap, "version": sha256(version)}
    await redis.set(f"dashboard-session:{sha256(token)}", json.dumps(value), ex=3600)
    return token


async def transaction(database, operation):
    async with await database.client.start_session() as session:
        return await session.with_transaction(operation)


async def audit(database, actor, action, subject, session=None):
    record = {
        "actor": actor["id"],
        "action": action,
        "subject": subject,
        "created_at": datetime.now(timezone.utc),
    }
    await database.audit_logs.insert_one(record, session=session)


def document_view(item):
    private = {
        "_id",
        "attachment_url",
        "deliveries",
        "delivery_lease",
        "notification_to",
        "notification_key",
    }
    result = {
        "id": str(item["_id"]),
        **{key: value for key, value in item.items() if key not in private},
    }
    if not result.get("attachment_id") and item.get("attachment_url"):
        # Read legacy attachments without returning the expired session token.
        match = re.fullmatch(
            r"/api/liff/attachments/(F-[a-f0-9]+)", urlsplit(item["attachment_url"]).path
        )
        if match:
            result["attachment_id"] = match[1]
    return result


async def file_response(database, file_id, employee_code=None):
    query = {"_id": file_id}
    if employee_code:
        query["employee_code"] = employee_code
    file = await database.files.find_one(query)
    if not file:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file['name'])}",
        "Cache-Control": "private, no-store",
    }
    return Response(
        await seaweed_read(file["fid"]),
        media_type=file["content_type"],
        headers=headers,
    )


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def valid_line_signature(body: bytes, signature: str | None) -> bool:
    expected = base64.b64encode(
        hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return bool(
        signature
        and LINE_CHANNEL_SECRET
        and hmac.compare_digest(expected.encode(), signature.encode())
    )


def issue_liff_token(line_user_id: str) -> str:
    payload = base64url(f"{line_user_id}:{int(time.time()) + 3600}".encode())
    signature = base64url(
        hmac.new(LIFF_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    )
    return f"{payload}.{signature}"


def read_liff_token(token: str) -> str | None:
    if len(token) > 2048 or not token.isascii():
        return None
    try:
        payload, signature = token.split(".", 1)
        expected = base64url(
            hmac.new(LIFF_SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
        )
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
        user_id, expires_at = decoded.rsplit(":", 1)
        return (
            user_id
            if hmac.compare_digest(signature, expected) and int(expires_at) >= time.time()
            else None
        )
    except (ValueError, UnicodeDecodeError):
        return None


async def seaweed_upload(name: str, content: bytes, content_type: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{SEAWEED_MASTER_URL}/dir/assign")
        response.raise_for_status()
        assigned = response.json()
        upload_url = f"http://{assigned['url']}/{assigned['fid']}"
        upload = await client.post(
            upload_url,
            files={"file": (name, content, content_type)},
        )
        upload.raise_for_status()
    return assigned["fid"]


async def seaweed_location(fid: str) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SEAWEED_MASTER_URL}/dir/lookup",
            params={"volumeId": fid.partition(",")[0]},
        )
        response.raise_for_status()
        return response.json()["locations"][0]["url"]


async def seaweed_read(fid: str) -> bytes:
    volume_url = await seaweed_location(fid)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"http://{volume_url}/{fid}")
        response.raise_for_status()
        return response.content


async def seaweed_delete(fid: str) -> None:
    try:
        volume_url = await seaweed_location(fid)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            return
        raise
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.delete(f"http://{volume_url}/{fid}")
        if response.status_code == 404:
            return
        response.raise_for_status()


async def storage_health() -> None:
    async with httpx.AsyncClient(timeout=3) as client:
        weaviate, seaweed = await asyncio.gather(
            client.get(f"{WEAVIATE_URL}/v1/.well-known/ready", headers=weaviate_headers()),
            client.get(f"{SEAWEED_MASTER_URL}/cluster/status"),
        )
        weaviate.raise_for_status()
        seaweed.raise_for_status()
