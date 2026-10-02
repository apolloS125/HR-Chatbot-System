import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request

from .core import valid_line_signature
from .knowledge import answer_policy
from .intent import classify_intent
from .admin import decide_leave
from .schemas import LeaveDecision
from .leaves import business_days, read_balances, submit_leave
from .line_client import announcement_carousel, reply_line

router = APIRouter()
LEAVE_TYPES = {"พักร้อน": "vacation", "ป่วย": "sick", "กิจ": "personal"}
LEAVE_LABELS = {value: key for key, value in LEAVE_TYPES.items()}


def parse_leave_command(text: str):
    parts = text.strip().split(maxsplit=4)
    if len(parts) < 3 or parts[0] != "ขอลา" or parts[1] not in LEAVE_TYPES:
        return None
    try:
        start = date.fromisoformat(parts[2]); end = date.fromisoformat(parts[3]) if len(parts) >= 4 else start
    except ValueError:
        return None
    if end < start: return None
    return LEAVE_TYPES[parts[1]], start, end, parts[4].strip() if len(parts) == 5 else ""


@router.post("/line/webhook")
async def line_webhook(request: Request, x_line_signature: Annotated[str | None, Header()] = None):
    body = await request.body()
    if not valid_line_signature(body, x_line_signature): raise HTTPException(status_code=401, detail="invalid LINE signature")
    for event in json.loads(body).get("events", []):
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            user_id, reply_token = event.get("source", {}).get("userId"), event.get("replyToken")
            if user_id and reply_token: await reply_line(reply_token, await handle_message(request.app.state.mongo, user_id, event["message"]["text"], event.get("webhookEventId") or reply_token, request.app.state.redis))
    return {"ok": True}


async def handle_message(database, line_user_id: str, text: str, event_id: str | None = None, redis=None):
    employee = await database.employees.find_one({"line_user_id": line_user_id, "active": True})
    if not employee: return "ยังไม่ได้ยืนยันตัวพนักงาน กรุณาติดต่อ HR เพื่อรับลิงก์เชื่อมบัญชี"
    normalized = text.strip()
    parts = normalized.split(maxsplit=1)
    if parts and parts[0] in {"อนุมัติ", "ปฏิเสธ"}:
        if employee.get("role") not in {"hr", "admin"}:
            return "เฉพาะ HR และ Admin พิจารณาคำขอลาได้"
        if len(parts) != 2 or not parts[1].startswith("LR-"):
            return "ใช้คำสั่ง อนุมัติ <รหัสคำขอ LR-...> หรือ ปฏิเสธ <รหัสคำขอ LR-...>"
        try:
            result = await decide_leave(parts[1], LeaveDecision(decision="approved" if parts[0] == "อนุมัติ" else "rejected"), database, redis, {"id": employee["_id"], "role": employee["role"]})
            return f"บันทึกผลคำขอ #{parts[1]} แล้ว" + (" แต่ส่งแจ้งผลไม่สำเร็จ ส่งอีกครั้งจาก Dashboard ได้" if result["notification_status"] == "failed" else "")
        except HTTPException as error:
            return str(error.detail)
    if normalized == "คำขอลารออนุมัติ":
        if employee.get("role") not in {"hr", "admin"}:
            return "เฉพาะ HR และ Admin ดูคำขอของพนักงานได้"
        rows = [item async for item in database.leave_requests.find({"status": "pending"}).sort("created_at", 1).limit(10)]
        return "\n".join(f"{item['_id']} · {item['employee_code']} · {item['start_date']} – {item['end_date']} ({item['days']} วัน)" for item in rows) or "ไม่มีคำขอที่รออนุมัติ"
    if normalized.startswith("ขอลา") and not parse_leave_command(normalized):
        return "รูปแบบคำขอลาไม่ถูกต้อง\nขอลา <พักร้อน|ป่วย|กิจ> <YYYY-MM-DD> <YYYY-MM-DD> <เหตุผล>"
    if normalized not in {"เมนู", "ช่วยเหลือ", "help", "วันลาคงเหลือ", "ประกาศ"} and not normalized.startswith("ขอลา"):
        intent = await classify_intent(normalized)
        normalized = {"balance": "วันลาคงเหลือ", "announcements": "ประกาศ", "menu": "เมนู"}.get(intent, normalized)
    if normalized in {"เมนู", "ช่วยเหลือ", "help"}: return menu()
    if normalized == "วันลาคงเหลือ":
        balances = await read_balances(database, employee["_id"])
        return "วันลาคงเหลือ\n" + "\n".join(f"{LEAVE_LABELS[k]}: {v} วัน" for k, v in balances.items())
    if normalized == "ประกาศ":
        rows = [row async for row in database.announcements.find({}).sort("published_at", -1).limit(3)]
        return announcement_carousel(rows) if rows else "ยังไม่มีประกาศ"
    leave = parse_leave_command(normalized)
    if leave:
        try:
            request_id, days = await submit_leave(database, employee["_id"], *leave, source_event_id=event_id)
            return f"ส่งคำขอลา #{request_id} แล้ว จำนวน {days} วัน รอ HR อนุมัติ"
        except HTTPException as error: return str(error.detail)
        except ValueError: return "ช่วงวันที่ลาไม่ถูกต้อง"
    return await answer_policy(database, normalized) or "ไม่พบคำตอบในฐานข้อมูล HR\n\n" + menu()


def menu() -> str:
    return "เมนู HR\n• วันลาคงเหลือ\n• ประกาศ\n• ขอลา <พักร้อน|ป่วย|กิจ> <วันเริ่ม> <วันสิ้นสุด> <เหตุผล>"
