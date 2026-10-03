from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from .core import transaction

LEAVE_TYPES = {"vacation", "sick", "personal"}
DEFAULT_ENTITLEMENTS = {"vacation": 10, "sick": 30, "personal": 5}


def business_days(start: date, end: date, holidays=()) -> int:
    if end < start or (end - start).days > 366:
        raise ValueError("invalid leave date range")

    days = (
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
    )
    return sum(day.weekday() < 5 and day.isoformat() not in holidays for day in days)


async def current_balances(database, employee, session=None):
    year = datetime.now(ZoneInfo("Asia/Bangkok")).year
    previous = employee.get("balances_year", year)
    if previous > year:
        raise HTTPException(status_code=409, detail="leave entitlement year is invalid")

    if previous < year:
        employee["balances"] = employee.get("entitlements", DEFAULT_ENTITLEMENTS).copy()

    await database.employees.update_one(
        {"_id": employee["_id"]},
        {"$set": {"balances": employee["balances"], "balances_year": year}},
        session=session,
    )
    return employee["balances"]


async def read_balances(database, employee_code):
    async def read(session):
        employee = await database.employees.find_one_and_update(
            {"_id": employee_code, "active": True},
            {"$inc": {"leave_revision": 1}},
            session=session,
        )
        if not employee:
            raise HTTPException(status_code=401, detail="employee is inactive")
        return await current_balances(database, employee, session)

    return await transaction(database, read)


async def submit_leave(
    database,
    employee_code: str,
    leave_type: str,
    start: date,
    end: date,
    reason: str,
    source_event_id: str | None = None,
    attachment_id: str | None = None,
    half_day: str | None = None,
):
    year = datetime.now(ZoneInfo("Asia/Bangkok")).year
    if leave_type not in LEAVE_TYPES or start.year != year or end.year != year:
        raise HTTPException(status_code=422, detail="เลือกประเภทการลาและวันที่ภายในปีปัจจุบัน")
    if half_day not in {None, "morning", "afternoon"} or (half_day and start != end):
        raise HTTPException(
            status_code=422,
            detail="ลาครึ่งวันต้องเลือกวันเริ่มและวันสิ้นสุดเป็นวันเดียวกัน",
        )
    business_days(start, end)

    async def create(session):
        if source_event_id:
            existing = await database.leave_requests.find_one(
                {"source_event_id": source_event_id},
                session=session,
            )
            if existing:
                if existing["employee_code"] != employee_code:
                    raise HTTPException(status_code=409, detail="request key is already used")
                expected = (
                    leave_type,
                    start.isoformat(),
                    end.isoformat(),
                    reason,
                    attachment_id,
                    half_day,
                )
                actual = (
                    existing["leave_type"],
                    existing["start_date"],
                    existing["end_date"],
                    existing["reason"],
                    existing.get("attachment_id"),
                    existing.get("half_day"),
                )
                if expected != actual:
                    raise HTTPException(
                        status_code=409,
                        detail="request key is already used for a different leave",
                    )
                return existing["_id"], existing["days"]

        # Writing the employee serializes concurrent requests and approvals in MongoDB.
        employee = await database.employees.find_one_and_update(
            {"_id": employee_code, "active": True},
            {"$inc": {"leave_revision": 1}},
            session=session,
        )
        if not employee:
            raise HTTPException(status_code=404, detail="employee not found")

        balances = await current_balances(database, employee, session)
        holiday_query = {
            "_id": {"$gte": start.isoformat(), "$lte": end.isoformat()}
        }
        holidays = {
            item["_id"]
            async for item in database.holidays.find(holiday_query, session=session)
        }
        days = business_days(start, end, holidays) * (0.5 if half_day else 1)
        if not days:
            raise HTTPException(status_code=422, detail="ช่วงวันที่เลือกไม่มีวันทำงาน")

        overlap = {
            "employee_code": employee_code,
            "status": {"$in": ["pending", "approved"]},
            "start_date": {"$lte": end.isoformat()},
            "end_date": {"$gte": start.isoformat()},
        }
        if half_day:
            overlap["half_day"] = {"$in": [None, half_day]}
        if await database.leave_requests.find_one(overlap, session=session):
            raise HTTPException(status_code=409, detail="มีคำขอลาในช่วงวันที่นี้แล้ว")

        pending_query = {
            "employee_code": employee_code,
            "status": "pending",
            "leave_type": leave_type,
            "start_date": {"$gte": f"{year}-01-01"},
        }
        pending_days = [
            item["days"]
            async for item in database.leave_requests.find(
                pending_query,
                session=session,
            )
        ]
        pending = sum(pending_days)
        if balances.get(leave_type, 0) - pending < days:
            raise HTTPException(
                status_code=409,
                detail="วันลาคงเหลือไม่เพียงพอ รวมคำขอที่รออนุมัติ",
            )

        attachment_query = {"_id": attachment_id, "employee_code": employee_code}
        if attachment_id and not await database.files.find_one(
            attachment_query,
            session=session,
        ):
            raise HTTPException(status_code=422, detail="ไม่พบเอกสารแนบของพนักงาน")

        request_id = f"LR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        document = {
            "_id": request_id,
            "employee_code": employee_code,
            "leave_type": leave_type,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "days": days,
            "half_day": half_day,
            "reason": reason,
            "attachment_id": attachment_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }
        if source_event_id:
            document["source_event_id"] = source_event_id
        await database.leave_requests.insert_one(document, session=session)
        return request_id, days

    return await transaction(database, create)


async def cancel_leave(database, leave_id, employee_code):
    async def cancel(session):
        employee = await database.employees.find_one_and_update(
            {"_id": employee_code, "active": True},
            {"$inc": {"leave_revision": 1}},
            session=session,
        )
        if not employee:
            raise HTTPException(status_code=403, detail="employee is inactive")

        leave_query = {
            "_id": leave_id,
            "employee_code": employee_code,
            "status": "pending",
        }
        result = await database.leave_requests.update_one(
            leave_query,
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc)}},
            session=session,
        )
        if result.modified_count != 1:
            raise HTTPException(status_code=409, detail="ยกเลิกได้เฉพาะคำขอของตนเองที่ยังรออนุมัติ")
        return {"ok": True}

    return await transaction(database, cancel)
