import asyncio
import json
import logging
import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from .admin import decide_leave
from .core import valid_line_signature
from .guardrails import check_guardrail
from .intent import classify_intent
from .knowledge import answer_policy
from .leaves import read_balances, submit_leave
from .line_client import announcement_carousel, reply_line
from .rate_limit import enforce_limit
from .schemas import LeaveDecision

router = APIRouter()
LEAVE_TYPES = {"พักร้อน": "vacation", "ป่วย": "sick", "กิจ": "personal"}
LEAVE_LABELS = {value: key for key, value in LEAVE_TYPES.items()}
LIFF_APP_ID = os.getenv("LIFF_APP_ID", "")
_EVENT_LIMIT = asyncio.Semaphore(8)


def parse_leave_command(text: str):
    parts = text.strip().split(maxsplit=4)
    if len(parts) < 3 or parts[0] != "ขอลา" or parts[1] not in LEAVE_TYPES:
        return None

    try:
        start = date.fromisoformat(parts[2])
        end = date.fromisoformat(parts[3]) if len(parts) >= 4 else start
    except ValueError:
        return None

    if end < start:
        return None

    return LEAVE_TYPES[parts[1]], start, end, parts[4].strip() if len(parts) == 5 else ""


@router.post("/line/webhook")
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: Annotated[str | None, Header()] = None,
):
    body = await request.body()

    if not valid_line_signature(body, x_line_signature):
        raise HTTPException(status_code=401, detail="invalid LINE signature")

    await enforce_limit(request.app.state.redis, "line-webhook", "channel", 1200)

    try:
        events = json.loads(body).get("events", [])
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            raise ValueError("invalid events")
    except (ValueError, AttributeError) as error:
        raise HTTPException(status_code=400, detail="invalid webhook payload") from error
    # shortcut: in-process tasks; use a durable inbox worker before requiring crash recovery.
    background_tasks.add_task(
        process_events, request.app.state.mongo, request.app.state.redis, events
    )
    return {"ok": True}


async def process_events(database, redis, events):
    await asyncio.gather(*(process_event(database, redis, event) for event in events))


async def process_event(database, redis, event):
    async with _EVENT_LIMIT:
        event_id = event.get("webhookEventId") or event.get("replyToken", "")
        key = f"line-event:{event_id}"
        claimed = False
        try:
            if not event_id:
                return
            claimed = await redis.set(key, "processing", nx=True, ex=120)
            if not claimed:
                return
            user_id = event.get("source", {}).get("userId")
            if user_id:
                try:
                    await enforce_limit(redis, "line-user", user_id, 20)
                except HTTPException as error:
                    if error.status_code != 429:
                        raise
                    await redis.set(key, "done", ex=86400)
                    return
            await reply_to_event(database, redis, event)
            await redis.set(key, "done", ex=86400)
        except Exception as error:
            logging.getLogger(__name__).error(
                "LINE event processing failed: id=%s error=%s", event_id, type(error).__name__
            )
            if claimed:
                try:
                    await redis.delete(key)
                except Exception:
                    logging.getLogger(__name__).error("Could not release LINE event claim")


async def reply_to_event(database, redis, event):
    is_text_message = (
        event.get("type") == "message" and event.get("message", {}).get("type") == "text"
    )
    if not is_text_message:
        return

    user_id = event.get("source", {}).get("userId")
    reply_token = event.get("replyToken")
    if not user_id or not reply_token:
        return

    response = await handle_message(
        database,
        user_id,
        event["message"]["text"],
        event.get("webhookEventId") or reply_token,
        redis,
    )
    await reply_line(reply_token, response)


async def handle_message(
    database,
    line_user_id: str,
    text: str,
    event_id: str | None = None,
    redis=None,
):
    employee = await database.employees.find_one({"line_user_id": line_user_id, "active": True})
    if not employee:
        return "ยังไม่ได้ยืนยันตัวพนักงาน กรุณาติดต่อ HR เพื่อรับลิงก์เชื่อมบัญชี"

    normalized = text.strip()
    parts = normalized.split(maxsplit=1)

    if parts and parts[0] in {"อนุมัติ", "ปฏิเสธ"}:
        if employee.get("role") not in {"hr", "admin"}:
            return "เฉพาะ HR และ Admin พิจารณาคำขอลาได้"
        if len(parts) != 2 or not parts[1].startswith("LR-"):
            return "ใช้คำสั่ง อนุมัติ <รหัสคำขอ LR-...> หรือ ปฏิเสธ <รหัสคำขอ LR-...>"

        try:
            decision = "approved" if parts[0] == "อนุมัติ" else "rejected"
            actor = {"id": employee["_id"], "role": employee["role"]}
            result = await decide_leave(
                parts[1], LeaveDecision(decision=decision), database, redis, actor
            )
        except HTTPException as error:
            return str(error.detail)

        response = f"บันทึกผลคำขอ #{parts[1]} แล้ว"
        if result["notification_status"] == "failed":
            response += " แต่ส่งแจ้งผลไม่สำเร็จ ส่งอีกครั้งจาก Dashboard ได้"
        return response

    if normalized == "คำขอลารออนุมัติ":
        if employee.get("role") not in {"hr", "admin"}:
            return "เฉพาะ HR และ Admin ดูคำขอของพนักงานได้"

        rows = [
            item
            async for item in database.leave_requests.find({"status": "pending"})
            .sort("created_at", 1)
            .limit(10)
        ]
        if not rows:
            return "ไม่มีคำขอที่รออนุมัติ"

        return "\n".join(
            f"{item['_id']} · {item['employee_code']} · "
            f"{item['start_date']} – {item['end_date']} ({item['days']} วัน)"
            for item in rows
        )

    if normalized == "ขอลา" and LIFF_APP_ID:
        return menu()
    if normalized.startswith("ขอลา") and not parse_leave_command(normalized):
        return "รูปแบบคำขอลาไม่ถูกต้อง\nขอลา <พักร้อน|ป่วย|กิจ> <YYYY-MM-DD> <YYYY-MM-DD> <เหตุผล>"

    known_commands = {"เมนู", "ช่วยเหลือ", "help", "วันลาคงเหลือ", "ประกาศ"}
    if normalized not in known_commands and not normalized.startswith("ขอลา"):
        refusal = await check_guardrail(normalized)
        if refusal:
            return refusal
        intent = await classify_intent(normalized)
        intent_commands = {
            "balance": "วันลาคงเหลือ",
            "announcements": "ประกาศ",
            "menu": "เมนู",
        }
        normalized = intent_commands.get(intent, normalized)

    if normalized in {"เมนู", "ช่วยเหลือ", "help"}:
        return menu()

    if normalized == "วันลาคงเหลือ":
        balances = await read_balances(database, employee["_id"])
        balance_lines = [
            f"{LEAVE_LABELS[leave_type]}: {days} วัน" for leave_type, days in balances.items()
        ]
        return "วันลาคงเหลือ\n" + "\n".join(balance_lines)

    if normalized == "ประกาศ":
        announcements = database.announcements.find({}).sort("published_at", -1).limit(3)
        rows = [row async for row in announcements]
        return announcement_carousel(rows) if rows else "ยังไม่มีประกาศ"

    leave = parse_leave_command(normalized)
    if leave:
        try:
            request_id, days = await submit_leave(
                database,
                employee["_id"],
                *leave,
                source_event_id=event_id,
            )
            return f"ส่งคำขอลา #{request_id} แล้ว จำนวน {days} วัน รอ HR อนุมัติ"
        except HTTPException as error:
            return str(error.detail)
        except ValueError:
            return "ช่วงวันที่ลาไม่ถูกต้อง"

    answer = await answer_policy(database, normalized, redis)
    if answer:
        return answer
    response = menu()
    not_found = "ไม่พบคำตอบในฐานข้อมูล HR กรุณาติดต่อ HR หรือเลือกบริการจากเมนู"
    if isinstance(response, str):
        return f"{not_found}\n\n{response}"
    return {**response, "text": f"{not_found}\n\n{response['text']}"}


def menu() -> str | dict:
    if not LIFF_APP_ID:
        return "เมนู HR\n• วันลาคงเหลือ\n• ประกาศ\n• ขอลา <พักร้อน|ป่วย|กิจ> <วันเริ่ม> <วันสิ้นสุด> <เหตุผล>"
    return {
        "type": "text",
        "text": "เมนู HR: เลือกบริการด้านล่าง หรือกดขอลาเพื่อกรอกแบบฟอร์ม",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {"type": "message", "label": "วันลาคงเหลือ", "text": "วันลาคงเหลือ"},
                },
                {
                    "type": "action",
                    "action": {"type": "message", "label": "ประกาศ", "text": "ประกาศ"},
                },
                {
                    "type": "action",
                    "action": {
                        "type": "uri",
                        "label": "ขอลา",
                        "uri": f"https://liff.line.me/{LIFF_APP_ID}",
                    },
                },
            ],
        },
    }
