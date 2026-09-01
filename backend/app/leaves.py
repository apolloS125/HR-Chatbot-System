from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError


def business_days(start: date, end: date) -> int:
    if end < start:
        raise ValueError("end date is before start date")
    return sum((start + timedelta(days=offset)).weekday() < 5 for offset in range((end - start).days + 1))


async def submit_leave(database, employee_code: str, leave_type: str, start: date, end: date, reason: str, source_event_id: str | None = None, attachment_url: str | None = None):
    days = business_days(start, end)
    if not days:
        raise HTTPException(status_code=422, detail="ช่วงวันที่เลือกไม่มีวันทำงาน")
    employee = await database.employees.find_one({"_id": employee_code, "active": True})
    if not employee:
        raise HTTPException(status_code=404, detail="employee not found")
    balance = employee["balances"].get(leave_type, 0)
    if balance < days:
        raise HTTPException(status_code=409, detail="วันลาคงเหลือไม่เพียงพอ")
    if source_event_id:
        existing = await database.leave_requests.find_one({"source_event_id": source_event_id})
        if existing:
            return existing["_id"], existing["days"]
    request_id = f"LR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    document = {"_id": request_id, "employee_code": employee_code, "leave_type": leave_type, "start_date": start.isoformat(), "end_date": end.isoformat(), "days": days, "reason": reason, "attachment_url": attachment_url, "status": "pending", "created_at": datetime.now(timezone.utc)}
    if source_event_id:
        document["source_event_id"] = source_event_id
    try:
        await database.leave_requests.insert_one(document)
    except DuplicateKeyError:
        existing = await database.leave_requests.find_one({"source_event_id": source_event_id}) if source_event_id else None
        if not existing: raise
        return existing["_id"], existing["days"]
    return request_id, days
