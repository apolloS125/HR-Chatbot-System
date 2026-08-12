from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlencode

import asyncpg
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hr:hr@localhost:5432/hr_chatbot")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
LINE_LOGIN_CHANNEL_ID = os.getenv("LINE_LOGIN_CHANNEL_ID", "")
LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "change-me")

LEAVE_TYPES = {"พักร้อน": "vacation", "ป่วย": "sick", "กิจ": "personal"}
LEAVE_LABELS = {value: key for key, value in LEAVE_TYPES.items()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    yield
    await app.state.db.close()


app = FastAPI(title="HR Chatbot API", version="0.1.0", lifespan=lifespan)


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    work_email: str = Field(min_length=3, max_length=255)
    role: Literal["employee", "hr", "admin"] = "employee"


class ActiveUpdate(BaseModel):
    active: bool


class LeaveDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    decided_by: str = Field(min_length=1, max_length=120)


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)


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


def announcement_bubble(title: str, body: str) -> dict[str, object]:
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0B8F50",
            "paddingAll": "18px",
            "contents": [{
                "type": "text",
                "text": "ประกาศบริษัท",
                "color": "#FFFFFF",
                "weight": "bold",
                "size": "sm",
            }],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "xl", "wrap": True},
                {"type": "separator", "color": "#DDE8E1"},
                {"type": "text", "text": body, "size": "md", "color": "#46544C", "wrap": True},
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "14px",
            "backgroundColor": "#F3F7F4",
            "contents": [{
                "type": "text",
                "text": "ฝ่ายทรัพยากรบุคคล",
                "size": "xs",
                "color": "#708078",
                "align": "end",
            }],
        },
    }


def announcement_message(title: str, body: str) -> dict[str, object]:
    return {
        "type": "flex",
        "altText": f"ประกาศบริษัท: {title}"[:400],
        "contents": announcement_bubble(title, body),
    }


def announcement_carousel(rows: list[asyncpg.Record]) -> dict[str, object]:
    bubbles = [announcement_bubble(row["title"], row["body"]) for row in rows]
    return {
        "type": "flex",
        "altText": "ประกาศล่าสุดจากบริษัท",
        "contents": bubbles[0] if len(bubbles) == 1 else {"type": "carousel", "contents": bubbles},
    }


def business_days(start: date, end: date) -> int:
    if end < start:
        raise ValueError("end date is before start date")
    return sum(
        1 for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    )


def parse_leave_command(text: str) -> tuple[str, date, date, str] | None:
    parts = text.strip().split(maxsplit=4)
    if len(parts) < 4 or parts[0] != "ขอลา" or parts[1] not in LEAVE_TYPES:
        return None
    try:
        start = date.fromisoformat(parts[2])
        end = date.fromisoformat(parts[3])
    except ValueError:
        return None
    reason = parts[4].strip() if len(parts) == 5 else "-"
    if end < start:
        return None
    return LEAVE_TYPES[parts[1]], start, end, reason


async def db(request: Request) -> asyncpg.Pool:
    return request.app.state.db


@app.get("/health")
async def health(pool: Annotated[asyncpg.Pool, Depends(db)]):
    await pool.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/auth/line/start")
async def line_login_start(
    employee_code: str,
    link_code: str,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")

    employee = await pool.fetchrow(
        """
        UPDATE employees
        SET link_code_hash = NULL, link_code_expires_at = NULL
        WHERE employee_code = $1 AND active
          AND link_code_hash = $2 AND link_code_expires_at > now()
        RETURNING id
        """,
        employee_code.upper(), sha256(link_code),
    )
    if not employee:
        raise HTTPException(status_code=400, detail="link is invalid or expired")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64url(hashlib.sha256(verifier.encode()).digest())
    await pool.execute(
        """
        INSERT INTO line_oauth_sessions (state, employee_id, nonce, code_verifier, expires_at)
        VALUES ($1, $2, $3, $4, now() + interval '10 minutes')
        """,
        state, employee["id"], nonce, verifier,
    )
    query = urlencode({
        "response_type": "code",
        "client_id": LINE_LOGIN_CHANNEL_ID,
        "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback",
        "state": state,
        "scope": "openid profile",
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"https://access.line.me/oauth2/v2.1/authorize?{query}")


@app.get("/auth/line/callback", response_class=HTMLResponse)
async def line_login_callback(
    code: str,
    state: str,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    async with pool.acquire() as conn, conn.transaction():
        session = await conn.fetchrow(
            """
            DELETE FROM line_oauth_sessions
            WHERE state = $1 AND expires_at > now()
            RETURNING employee_id, nonce, code_verifier
            """,
            state,
        )
        if not session:
            raise HTTPException(status_code=400, detail="login session is invalid or expired")

        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(
                "https://api.line.me/oauth2/v2.1/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback",
                    "client_id": LINE_LOGIN_CHANNEL_ID,
                    "client_secret": LINE_LOGIN_CHANNEL_SECRET,
                    "code_verifier": session["code_verifier"],
                },
            )
            if token_response.is_error:
                raise HTTPException(status_code=400, detail="LINE token exchange failed")
            id_token = token_response.json().get("id_token")
            verify_response = await client.post(
                "https://api.line.me/oauth2/v2.1/verify",
                data={
                    "id_token": id_token,
                    "client_id": LINE_LOGIN_CHANNEL_ID,
                    "nonce": session["nonce"],
                },
            )
            if verify_response.is_error:
                raise HTTPException(status_code=400, detail="LINE identity verification failed")
            line_user_id = verify_response.json().get("sub")
            if not line_user_id:
                raise HTTPException(status_code=400, detail="LINE user ID is missing")

        linked_employee = await conn.fetchval(
            "SELECT employee_code FROM employees WHERE line_user_id = $1 AND id <> $2",
            line_user_id, session["employee_id"],
        )
        if linked_employee:
            raise HTTPException(status_code=409, detail="LINE account is linked to another employee")
        updated = await conn.fetchval(
            """
            UPDATE employees
            SET line_user_id = $1, line_linked_at = now(),
                link_code_hash = NULL, link_code_expires_at = NULL
            WHERE id = $2 AND active
            RETURNING id
            """,
            line_user_id, session["employee_id"],
        )
        if not updated:
            raise HTTPException(status_code=409, detail="employee account is inactive")

    return HTMLResponse("""
    <!doctype html><html lang="th"><meta charset="utf-8">
    <title>เชื่อมบัญชีสำเร็จ</title>
    <body style="font-family:system-ui;text-align:center;padding:4rem">
      <h1>เชื่อมบัญชีสำเร็จ</h1><p>กลับไปใช้งาน HR Chatbot ใน LINE ได้เลย</p>
    </body></html>
    """)


@app.post("/line/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: Annotated[str | None, Header()] = None,
):
    body = await request.body()
    if not valid_line_signature(body, x_line_signature):
        raise HTTPException(status_code=401, detail="invalid LINE signature")

    payload = json.loads(body)
    for event in payload.get("events", []):
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue
        user_id = event.get("source", {}).get("userId")
        reply_token = event.get("replyToken")
        if not user_id or not reply_token:
            continue
        reply_text = await handle_message(
            request.app.state.db,
            user_id,
            event["message"]["text"],
            event.get("webhookEventId") or reply_token,
        )
        await reply_line(reply_token, reply_text)
    return {"ok": True}


async def handle_message(
    pool: asyncpg.Pool,
    line_user_id: str,
    text: str,
    event_id: str | None = None,
) -> str | dict[str, object]:
    employee = await pool.fetchrow(
        "SELECT id, name FROM employees WHERE line_user_id = $1 AND active",
        line_user_id,
    )
    if not employee:
        return "ยังไม่ได้ยืนยันตัวพนักงาน กรุณาติดต่อ HR เพื่อรับลิงก์เชื่อมบัญชี"

    normalized = text.strip()
    if normalized in {"เมนู", "ช่วยเหลือ", "help"}:
        return menu()

    if normalized == "วันลาคงเหลือ":
        rows = await pool.fetch(
            "SELECT leave_type, remaining_days FROM leave_balances WHERE employee_id = $1 ORDER BY leave_type",
            employee["id"],
        )
        if not rows:
            return "ยังไม่มีข้อมูลวันลาคงเหลือ กรุณาติดต่อ HR"
        lines = [f"{LEAVE_LABELS.get(row['leave_type'], row['leave_type'])}: {row['remaining_days']} วัน" for row in rows]
        return "วันลาคงเหลือ\n" + "\n".join(lines)

    if normalized == "ประกาศ":
        rows = await pool.fetch(
            "SELECT title, body FROM announcements WHERE published_at <= now() ORDER BY published_at DESC LIMIT 3"
        )
        return announcement_carousel(rows) if rows else "ยังไม่มีประกาศ"

    leave = parse_leave_command(normalized)
    if leave:
        leave_type, start, end, reason = leave
        days = business_days(start, end)
        if days == 0:
            return "ช่วงวันที่เลือกไม่มีวันทำงาน"
        async with pool.acquire() as conn, conn.transaction():
            remaining = await conn.fetchval(
                "SELECT remaining_days FROM leave_balances WHERE employee_id = $1 AND leave_type = $2 FOR UPDATE",
                employee["id"], leave_type,
            )
            if remaining is None or Decimal(remaining) < days:
                return "วันลาคงเหลือไม่เพียงพอ"
            request_id = await conn.fetchval(
                """
                INSERT INTO leave_requests
                    (employee_id, leave_type, start_date, end_date, days, reason, source_event_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (source_event_id) DO UPDATE
                SET source_event_id = EXCLUDED.source_event_id
                RETURNING id
                """,
                employee["id"], leave_type, start, end, days, reason, event_id,
            )
        return f"ส่งคำขอลา #{request_id} แล้ว จำนวน {days} วัน รอ HR อนุมัติ"

    faq = await pool.fetchval(
        "SELECT answer FROM faqs WHERE active AND $1 ILIKE '%' || keyword || '%' ORDER BY length(keyword) DESC LIMIT 1",
        normalized,
    )
    return faq or "ไม่พบคำตอบในฐานข้อมูล HR\n\n" + menu()


def menu() -> str:
    return (
        "เมนู HR\n"
        "• วันลาคงเหลือ\n"
        "• ประกาศ\n"
        "• ขอลา <พักร้อน|ป่วย|กิจ> <วันเริ่ม> <วันสิ้นสุด> <เหตุผล>\n"
        "ตัวอย่าง: ขอลา พักร้อน 2026-08-20 2026-08-21 ธุระครอบครัว"
    )


async def reply_line(reply_token: str, message: str | dict[str, object]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return
    line_message = {"type": "text", "text": message[:5000]} if isinstance(message, str) else message
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},
            json={"replyToken": reply_token, "messages": [line_message]},
        )
        response.raise_for_status()


async def multicast_line(user_ids: list[str], message: dict[str, object]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="LINE Messaging API is not configured")
    async with httpx.AsyncClient(timeout=15) as client:
        for offset in range(0, len(user_ids), 500):
            response = await client.post(
                "https://api.line.me/v2/bot/message/multicast",
                headers={
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                    "X-Line-Retry-Key": str(uuid.uuid4()),
                },
                json={"to": user_ids[offset:offset + 500], "messages": [message]},
            )
            response.raise_for_status()


@app.get("/api/admin/summary", dependencies=[Depends(require_admin)])
async def admin_summary(pool: Annotated[asyncpg.Pool, Depends(db)]):
    row = await pool.fetchrow("""
        SELECT
          (SELECT count(*) FROM employees WHERE active) AS active_employees,
          (SELECT count(*) FROM employees WHERE line_user_id IS NOT NULL AND active) AS linked_employees,
          (SELECT count(*) FROM leave_requests WHERE status = 'pending') AS pending_leaves
    """)
    return dict(row)


@app.get("/api/admin/employees", dependencies=[Depends(require_admin)])
async def list_employees(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""
        SELECT id, employee_code, name, work_email, role, active,
               line_user_id IS NOT NULL AS line_linked, line_linked_at
        FROM employees WHERE active ORDER BY employee_code
    """)
    return [dict(row) for row in rows]


@app.post("/api/admin/employees", status_code=201, dependencies=[Depends(require_admin)])
async def create_employee(data: EmployeeCreate, pool: Annotated[asyncpg.Pool, Depends(db)]):
    try:
        async with pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO employees (employee_code, name, work_email, role)
                VALUES ($1, $2, lower($3), $4)
                RETURNING id, employee_code, name, work_email, role, active
                """,
                data.employee_code.upper(), data.name, data.work_email, data.role,
            )
            await conn.executemany(
                "INSERT INTO leave_balances (employee_id, leave_type, remaining_days) VALUES ($1, $2, $3)",
                [(row["id"], "vacation", 10), (row["id"], "sick", 30), (row["id"], "personal", 5)],
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="employee code or email already exists")
    return dict(row)


@app.post("/api/admin/employees/{employee_id}/link", dependencies=[Depends(require_admin)])
async def issue_link_code(employee_id: int, pool: Annotated[asyncpg.Pool, Depends(db)]):
    code = secrets.token_urlsafe(12)
    employee_code = await pool.fetchval(
        """
        UPDATE employees
        SET link_code_hash = $1, link_code_expires_at = now() + interval '30 minutes'
        WHERE id = $2 AND active
        RETURNING employee_code
        """,
        sha256(code), employee_id,
    )
    if not employee_code:
        raise HTTPException(status_code=404, detail="active employee not found")
    query = urlencode({"employee_code": employee_code, "link_code": code})
    return {"expires_in_minutes": 30, "link": f"{PUBLIC_BASE_URL}/auth/line/start?{query}"}


@app.patch("/api/admin/employees/{employee_id}/active", dependencies=[Depends(require_admin)])
async def set_employee_active(
    employee_id: int,
    data: ActiveUpdate,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    changed = await pool.fetchval(
        "UPDATE employees SET active = $1 WHERE id = $2 RETURNING id",
        data.active, employee_id,
    )
    if not changed:
        raise HTTPException(status_code=404, detail="employee not found")
    return {"ok": True}


@app.delete("/api/admin/employees/{employee_id}", dependencies=[Depends(require_admin)])
async def delete_employee(employee_id: int, pool: Annotated[asyncpg.Pool, Depends(db)]):
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("DELETE FROM leave_requests WHERE employee_id = $1", employee_id)
        deleted = await conn.fetchval(
            "DELETE FROM employees WHERE id = $1 RETURNING id",
            employee_id,
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="employee not found")
    return {"ok": True}


@app.get("/api/admin/announcements", dependencies=[Depends(require_admin)])
async def list_announcements(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""
        SELECT id, title, body, published_at
        FROM announcements ORDER BY published_at DESC LIMIT 20
    """)
    return [dict(row) for row in rows]


@app.post("/api/admin/announcements", status_code=201, dependencies=[Depends(require_admin)])
async def create_announcement(
    data: AnnouncementCreate,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    rows = await pool.fetch(
        "SELECT line_user_id FROM employees WHERE active AND line_user_id IS NOT NULL"
    )
    recipients = [row["line_user_id"] for row in rows]
    if recipients and not LINE_CHANNEL_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="LINE Messaging API is not configured")

    announcement = await pool.fetchrow(
        """
        INSERT INTO announcements (title, body)
        VALUES ($1, $2) RETURNING id, title, body, published_at
        """,
        data.title, data.body,
    )
    try:
        if recipients:
            await multicast_line(recipients, announcement_message(data.title, data.body))
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"บันทึกประกาศแล้ว แต่ส่ง LINE ไม่สำเร็จ: {error.response.text[:300]}",
        )
    return {**dict(announcement), "recipient_count": len(recipients)}


@app.get("/api/admin/leaves", dependencies=[Depends(require_admin)])
async def list_leaves(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""
        SELECT lr.id, e.employee_code, e.name, lr.leave_type, lr.start_date,
               lr.end_date, lr.days, lr.reason, lr.status, lr.created_at
        FROM leave_requests lr JOIN employees e ON e.id = lr.employee_id
        ORDER BY (lr.status = 'pending') DESC, lr.created_at DESC
    """)
    return [dict(row) for row in rows]


@app.post("/api/admin/leaves/{leave_id}/decision", dependencies=[Depends(require_admin)])
async def decide_leave(
    leave_id: int,
    data: LeaveDecision,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    async with pool.acquire() as conn, conn.transaction():
        leave = await conn.fetchrow(
            "SELECT employee_id, leave_type, days, status FROM leave_requests WHERE id = $1 FOR UPDATE",
            leave_id,
        )
        if not leave:
            raise HTTPException(status_code=404, detail="leave request not found")
        if leave["status"] != "pending":
            raise HTTPException(status_code=409, detail="leave request was already decided")
        if data.decision == "approved":
            remaining = await conn.fetchval(
                "SELECT remaining_days FROM leave_balances WHERE employee_id = $1 AND leave_type = $2 FOR UPDATE",
                leave["employee_id"], leave["leave_type"],
            )
            if remaining is None or Decimal(remaining) < leave["days"]:
                raise HTTPException(status_code=409, detail="leave balance is insufficient")
            await conn.execute(
                "UPDATE leave_balances SET remaining_days = remaining_days - $1 WHERE employee_id = $2 AND leave_type = $3",
                leave["days"], leave["employee_id"], leave["leave_type"],
            )
        await conn.execute(
            """
            UPDATE leave_requests
            SET status = $1, decided_by = $2, decided_at = now()
            WHERE id = $3
            """,
            data.decision, data.decided_by, leave_id,
        )
    return {"ok": True}
