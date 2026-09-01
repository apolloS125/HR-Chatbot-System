import secrets
from datetime import date
from pathlib import Path
from typing import Annotated

import asyncpg
import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .core import LINE_LOGIN_CHANNEL_ID, PUBLIC_BASE_URL, db, issue_liff_token, read_liff_token
from .leaves import submit_leave
from .schemas import LiffLeaveCreate, LiffSessionCreate


router = APIRouter(prefix="/api/liff")
UPLOAD_DIR = Path("uploads")
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}


async def current_employee(
    authorization: Annotated[str | None, Header()] = None,
    pool: asyncpg.Pool = Depends(db),
) -> asyncpg.Record:
    token = authorization.removeprefix("Bearer ") if authorization else ""
    line_user_id = read_liff_token(token)
    if not line_user_id:
        raise HTTPException(status_code=401, detail="LIFF session is invalid or expired")
    employee = await pool.fetchrow(
        "SELECT id, employee_code, name FROM employees WHERE line_user_id = $1 AND active",
        line_user_id,
    )
    if not employee:
        raise HTTPException(status_code=403, detail="ไม่พบบัญชีพนักงานที่เชื่อมกับ LINE นี้")
    return employee


@router.post("/session")
async def create_session(data: LiffSessionCreate, pool: Annotated[asyncpg.Pool, Depends(db)]):
    if not LINE_LOGIN_CHANNEL_ID:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.line.me/oauth2/v2.1/verify",
            data={"id_token": data.id_token, "client_id": LINE_LOGIN_CHANNEL_ID},
        )
    if response.is_error or not (line_user_id := response.json().get("sub")):
        raise HTTPException(status_code=401, detail="LINE identity verification failed")
    employee = await pool.fetchrow("SELECT name FROM employees WHERE line_user_id = $1 AND active", line_user_id)
    if not employee:
        raise HTTPException(status_code=403, detail="ยังไม่ได้ยืนยันตัวพนักงาน กรุณาติดต่อ HR")
    return {"token": issue_liff_token(line_user_id), "name": employee["name"]}


@router.get("/me")
async def me(employee: Annotated[asyncpg.Record, Depends(current_employee)]):
    return dict(employee)


@router.get("/balances")
async def balances(employee: Annotated[asyncpg.Record, Depends(current_employee)], pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("SELECT leave_type, remaining_days FROM leave_balances WHERE employee_id = $1 ORDER BY leave_type", employee["id"])
    return [dict(row) for row in rows]


@router.get("/leaves")
async def leaves(employee: Annotated[asyncpg.Record, Depends(current_employee)], pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""SELECT id, leave_type, start_date, end_date, days, reason, attachment_url, status, created_at
        FROM leave_requests WHERE employee_id = $1 ORDER BY created_at DESC""", employee["id"])
    return [dict(row) for row in rows]


@router.get("/announcements")
async def announcements(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("SELECT id, title, body, published_at FROM announcements WHERE published_at <= now() ORDER BY published_at DESC LIMIT 20")
    return [dict(row) for row in rows]


@router.post("/attachments", status_code=201)
async def upload_attachment(
    file: Annotated[UploadFile, File()],
    employee: Annotated[asyncpg.Record, Depends(current_employee)],
    authorization: Annotated[str | None, Header()] = None,
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="รองรับเฉพาะ PDF, JPG และ PNG")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="ไฟล์ต้องไม่เกิน 10 MB")
    UPLOAD_DIR.mkdir(exist_ok=True)
    suffix = Path(file.filename or "file").suffix.lower()
    filename = f"{employee['id']}-{secrets.token_urlsafe(12)}{suffix}"
    (UPLOAD_DIR / filename).write_bytes(content)
    token = authorization.removeprefix("Bearer ") if authorization else ""
    return {"url": f"{PUBLIC_BASE_URL}/api/liff/attachments/{filename}?token={token}", "name": file.filename}


@router.get("/attachments/{filename}")
async def attachment(filename: str, token: str, pool: Annotated[asyncpg.Pool, Depends(db)]):
    line_user_id = read_liff_token(token)
    employee_id = filename.split("-", 1)[0]
    if not line_user_id or not employee_id.isdigit():
        raise HTTPException(status_code=401, detail="LIFF session is invalid or expired")
    employee = await pool.fetchval("SELECT id FROM employees WHERE id = $1 AND line_user_id = $2 AND active", int(employee_id), line_user_id)
    if not employee:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เข้าถึงเอกสาร")
    path = UPLOAD_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return FileResponse(path)


@router.post("/leaves", status_code=201)
async def create_leave(data: LiffLeaveCreate, employee: Annotated[asyncpg.Record, Depends(current_employee)], pool: Annotated[asyncpg.Pool, Depends(db)]):
    try:
        start, end = date.fromisoformat(data.start_date), date.fromisoformat(data.end_date)
        request_id, days = await submit_leave(pool, employee["id"], data.leave_type, start, end, data.reason, attachment_url=data.attachment_url)
    except ValueError:
        raise HTTPException(status_code=422, detail="รูปแบบวันที่ไม่ถูกต้อง")
    return {"id": request_id, "days": days, "status": "pending"}
