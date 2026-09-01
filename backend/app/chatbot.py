import json
from datetime import date
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Request

from .core import valid_line_signature
from .knowledge import answer_policy
from .leaves import business_days, submit_leave
from .line_client import announcement_carousel, reply_line


router = APIRouter()
LEAVE_TYPES = {"พักร้อน": "vacation", "ป่วย": "sick", "กิจ": "personal"}
LEAVE_LABELS = {value: key for key, value in LEAVE_TYPES.items()}


def parse_leave_command(text: str) -> tuple[str, date, date, str] | None:
    parts = text.strip().split(maxsplit=4)
    if len(parts) < 3 or parts[0] != "ขอลา" or parts[1] not in LEAVE_TYPES:
        return None
    try:
        start = date.fromisoformat(parts[2])
        end = date.fromisoformat(parts[3]) if len(parts) >= 4 else start
    except ValueError:
        return None
    reason = parts[4].strip() if len(parts) == 5 else ""
    if end < start:
        return None
    return LEAVE_TYPES[parts[1]], start, end, reason


@router.post("/line/webhook")
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
        reply_message = await handle_message(
            request.app.state.db,
            user_id,
            event["message"]["text"],
            event.get("webhookEventId") or reply_token,
        )
        await reply_line(reply_token, reply_message)
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
            "SELECT title, body, published_at FROM announcements WHERE published_at <= now() ORDER BY published_at DESC LIMIT 3"
        )
        return announcement_carousel(rows) if rows else "ยังไม่มีประกาศ"

    leave = parse_leave_command(normalized)
    if leave:
        leave_type, start, end, reason = leave
        try:
            request_id, days = await submit_leave(
                pool, employee["id"], leave_type, start, end, reason, event_id,
            )
        except HTTPException as error:
            return str(error.detail)
        return f"ส่งคำขอลา #{request_id} แล้ว จำนวน {days} วัน รอ HR อนุมัติ"

    answer = await answer_policy(pool, normalized)
    return answer or "ไม่พบคำตอบในฐานข้อมูล HR\n\n" + menu()


def menu() -> str:
    return (
        "เมนู HR\n"
        "• วันลาคงเหลือ\n"
        "• ประกาศ\n"
        "• ขอลา <พักร้อน|ป่วย|กิจ> <วันเริ่ม> <วันสิ้นสุด> <เหตุผล>\n"
        "ตัวอย่าง: ขอลา พักร้อน 2026-08-20 2026-08-21 ธุระครอบครัว"
    )
