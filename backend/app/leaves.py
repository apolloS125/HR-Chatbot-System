from datetime import date, timedelta
from decimal import Decimal

import asyncpg
from fastapi import HTTPException


def business_days(start: date, end: date) -> int:
    if end < start:
        raise ValueError("end date is before start date")
    return sum(1 for offset in range((end - start).days + 1) if (start + timedelta(days=offset)).weekday() < 5)


async def submit_leave(
    pool: asyncpg.Pool,
    employee_id: int,
    leave_type: str,
    start: date,
    end: date,
    reason: str,
    source_event_id: str | None = None,
    attachment_url: str | None = None,
) -> tuple[int, int]:
    days = business_days(start, end)
    if not days:
        raise HTTPException(status_code=422, detail="ช่วงวันที่เลือกไม่มีวันทำงาน")
    async with pool.acquire() as conn, conn.transaction():
        remaining = await conn.fetchval(
            "SELECT remaining_days FROM leave_balances WHERE employee_id = $1 AND leave_type = $2 FOR UPDATE",
            employee_id, leave_type,
        )
        if remaining is None or Decimal(remaining) < days:
            raise HTTPException(status_code=409, detail="วันลาคงเหลือไม่เพียงพอ")
        request_id = await conn.fetchval(
            """
            INSERT INTO leave_requests
                (employee_id, leave_type, start_date, end_date, days, reason, attachment_url, source_event_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (source_event_id) DO UPDATE SET source_event_id = EXCLUDED.source_event_id
            RETURNING id
            """,
            employee_id, leave_type, start, end, days, reason, attachment_url, source_event_id,
        )
    return request_id, days
