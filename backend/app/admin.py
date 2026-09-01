import secrets
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException

from .core import LINE_CHANNEL_ACCESS_TOKEN, PUBLIC_BASE_URL, db, require_admin, sha256
from .line_client import announcement_message, multicast_line
from .schemas import ActiveUpdate, AnnouncementCreate, EmployeeCreate, LeaveDecision


router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@router.get("/summary")
async def admin_summary(pool: Annotated[asyncpg.Pool, Depends(db)]):
    row = await pool.fetchrow("""
        SELECT
          (SELECT count(*) FROM employees WHERE active) AS active_employees,
          (SELECT count(*) FROM employees WHERE line_user_id IS NOT NULL AND active) AS linked_employees,
          (SELECT count(*) FROM leave_requests WHERE status = 'pending') AS pending_leaves
    """)
    return dict(row)


@router.get("/employees")
async def list_employees(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""
        SELECT id, employee_code, name, work_email, role, active,
               line_user_id IS NOT NULL AS line_linked, line_linked_at
        FROM employees WHERE active ORDER BY employee_code
    """)
    return [dict(row) for row in rows]


@router.post("/employees", status_code=201)
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


@router.post("/employees/{employee_id}/link")
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


@router.patch("/employees/{employee_id}/active")
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


@router.delete("/employees/{employee_id}")
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


@router.get("/announcements")
async def list_announcements(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""
        SELECT id, title, body, published_at
        FROM announcements ORDER BY published_at DESC LIMIT 20
    """)
    return [dict(row) for row in rows]


@router.post("/announcements", status_code=201)
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
            await multicast_line(
                recipients,
                announcement_message(data.title, data.body, announcement["published_at"]),
            )
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"บันทึกประกาศแล้ว แต่ส่ง LINE ไม่สำเร็จ: {error.response.text[:300]}",
        )
    return {**dict(announcement), "recipient_count": len(recipients)}


@router.get("/leaves")
async def list_leaves(pool: Annotated[asyncpg.Pool, Depends(db)]):
    rows = await pool.fetch("""
        SELECT lr.id, e.employee_code, e.name, lr.leave_type, lr.start_date,
               lr.end_date, lr.days, lr.reason, lr.status, lr.created_at
        FROM leave_requests lr JOIN employees e ON e.id = lr.employee_id
        ORDER BY (lr.status = 'pending') DESC, lr.created_at DESC
    """)
    return [dict(row) for row in rows]


@router.post("/leaves/{leave_id}/decision")
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
