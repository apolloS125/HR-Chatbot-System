import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from .core import (
    HR_USERNAME,
    PUBLIC_BASE_URL,
    audit,
    cache,
    db,
    document_view,
    file_response,
    hash_password,
    require_admin,
    seaweed_delete,
    sha256,
    transaction,
)
from .leaves import DEFAULT_ENTITLEMENTS, current_balances
from .line_client import announcement_message, multicast_line, push_line
from .schemas import ActiveUpdate, AnnouncementCreate, EmployeeCreate, EmployeeUpdate, HolidayCreate, LeaveDecision

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


def employee_view(item):
    return {"id": item["_id"], "employee_code": item["_id"], "name": item["name"], "work_email": item["work_email"], "role": item["role"], "active": item["active"], "line_linked": bool(item.get("line_user_id")), "line_linked_at": item.get("line_linked_at"), "balances": item["balances"], "entitlements": item.get("entitlements", DEFAULT_ENTITLEMENTS), "balances_year": item.get("balances_year", datetime.now(ZoneInfo("Asia/Bangkok")).year)}


def check_employee_permission(actor, employee, new_role=None, password=None):
    if actor["role"] != "admin" and (employee["role"] != "employee" or new_role not in {None, "employee"} or password):
        raise HTTPException(status_code=403, detail="เฉพาะ Admin จัดการบทบาทและรหัสผ่านได้")


@router.get("/session")
async def admin_session(actor=Depends(require_admin)):
    return actor


@router.get("/summary")
async def admin_summary(database=Depends(db), redis=Depends(cache)):
    if cached := await redis.get("summary"):
        return json.loads(cached)
    result = {"active_employees": await database.employees.count_documents({"active": True}), "linked_employees": await database.employees.count_documents({"active": True, "line_user_id": {"$exists": True}}), "pending_leaves": await database.leave_requests.count_documents({"status": "pending"})}
    await redis.setex("summary", 30, json.dumps(result))
    return result


@router.get("/employees")
async def list_employees(database=Depends(db)):
    return [employee_view(item) async for item in database.employees.find({}).sort("_id", 1)]


@router.post("/employees", status_code=201)
async def create_employee(data: EmployeeCreate, database=Depends(db), redis=Depends(cache), actor=Depends(require_admin)):
    check_employee_permission(actor, {"role": "employee"}, data.role)
    if data.employee_code.lower() == HR_USERNAME.lower():
        raise HTTPException(status_code=409, detail="รหัสนี้สงวนสำหรับบัญชีผู้ดูแลเริ่มต้น")
    employee = {"_id": data.employee_code, "name": data.name.strip(), "work_email": data.work_email, "role": data.role, "active": True, "balances": DEFAULT_ENTITLEMENTS.copy(), "entitlements": DEFAULT_ENTITLEMENTS.copy(), "balances_year": datetime.now(ZoneInfo("Asia/Bangkok")).year, "created_at": datetime.now(timezone.utc)}
    async def create(session):
        await database.employees.insert_one(employee, session=session)
        await audit(database, actor, "employee.create", employee["_id"], session)
    try:
        await transaction(database, create)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="employee code or email already exists")
    await redis.delete("summary")
    return employee_view(employee)


@router.patch("/employees/{employee_id}")
async def update_employee(employee_id: str, data: EmployeeUpdate, database=Depends(db), actor=Depends(require_admin)):
    if data.employee_code != employee_id:
        raise HTTPException(status_code=422, detail="ไม่สามารถเปลี่ยนรหัสพนักงาน")
    async def update(session):
        employee = await database.employees.find_one({"_id": employee_id}, session=session)
        if not employee:
            raise HTTPException(status_code=404, detail="employee not found")
        check_employee_permission(actor, employee, data.role, data.password)
        if employee_id == actor["id"] and data.role != "admin":
            raise HTTPException(status_code=409, detail="ไม่สามารถลดสิทธิ์บัญชีตนเอง")
        values = {"name": data.name.strip(), "work_email": data.work_email, "role": data.role, "balances": {"vacation": data.vacation, "sick": data.sick, "personal": data.personal}, "entitlements": {"vacation": data.vacation_entitlement, "sick": data.sick_entitlement, "personal": data.personal_entitlement}, "balances_year": datetime.now(ZoneInfo("Asia/Bangkok")).year}
        if data.password:
            values["password_hash"] = hash_password(data.password)
        changed = await database.employees.find_one_and_update({"_id": employee_id}, {"$set": values, "$inc": {"leave_revision": 1}}, session=session, return_document=ReturnDocument.AFTER)
        await audit(database, actor, "employee.update", employee_id, session)
        return employee_view(changed)
    try:
        return await transaction(database, update)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="employee code or email already exists")


@router.post("/employees/{employee_id}/link")
async def issue_link_code(employee_id: str, database=Depends(db), actor=Depends(require_admin)):
    code = secrets.token_urlsafe(12)
    employee = await database.employees.find_one({"_id": employee_id, "active": True})
    if not employee:
        raise HTTPException(status_code=404, detail="active employee not found")
    check_employee_permission(actor, employee)
    await database.employees.update_one({"_id": employee_id, "active": True}, {"$set": {"link_code_hash": sha256(code), "link_code_expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)}})
    await audit(database, actor, "employee.line_link", employee_id)
    return {"expires_in_minutes": 30, "link": f"{PUBLIC_BASE_URL}/auth/line/start?employee_code={employee_id}&link_code={code}"}


@router.patch("/employees/{employee_id}/active")
async def set_employee_active(employee_id: str, data: ActiveUpdate, database=Depends(db), redis=Depends(cache), actor=Depends(require_admin)):
    async def update(session):
        employee = await database.employees.find_one({"_id": employee_id}, session=session)
        if not employee:
            raise HTTPException(status_code=404, detail="employee not found")
        check_employee_permission(actor, employee)
        if employee_id == actor["id"] and not data.active:
            raise HTTPException(status_code=409, detail="ไม่สามารถปิดบัญชีตนเอง")
        await database.employees.update_one({"_id": employee_id}, {"$set": {"active": data.active}}, session=session)
        await audit(database, actor, "employee.activate" if data.active else "employee.deactivate", employee_id, session)
    await transaction(database, update)
    await redis.delete("summary")
    return {"ok": True}


@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: str, database=Depends(db), redis=Depends(cache), actor=Depends(require_admin)):
    employee = await database.employees.find_one({"_id": employee_id})
    if not employee:
        raise HTTPException(status_code=404, detail="employee not found")
    check_employee_permission(actor, employee)
    if employee_id == actor["id"]:
        raise HTTPException(status_code=409, detail="ไม่สามารถลบบัญชีตนเอง")

    files = [item async for item in database.files.find({"employee_code": employee_id}, {"fid": 1})]
    try:
        for item in files:
            if item.get("fid"):
                await seaweed_delete(item["fid"])
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="ลบเอกสารจากระบบจัดเก็บไม่สำเร็จ กรุณาลองใหม่") from error

    async def remove(session):
        current = await database.employees.find_one({"_id": employee_id}, session=session)
        if not current:
            raise HTTPException(status_code=404, detail="employee not found")
        check_employee_permission(actor, current)
        if employee_id == actor["id"]:
            raise HTTPException(status_code=409, detail="ไม่สามารถลบบัญชีตนเอง")
        await database.leave_requests.delete_many({"employee_code": employee_id}, session=session)
        await database.files.delete_many({"employee_code": employee_id}, session=session)
        await database.line_oauth_sessions.delete_many({"employee_code": employee_id}, session=session)
        if current.get("line_user_id"):
            await database.announcements.update_many(
                {"deliveries.to": current["line_user_id"]},
                {"$pull": {"deliveries.$[].to": current["line_user_id"]}},
                session=session,
            )
        await database.audit_logs.delete_many(
            {"$or": [{"subject": employee_id}, {"actor": employee_id}]},
            session=session,
        )
        await database.employees.delete_one({"_id": employee_id}, session=session)
        await audit(database, actor, "employee.delete", employee_id, session)

    await transaction(database, remove)
    await redis.delete("summary")
    return {"ok": True}


@router.get("/attachments/{file_id}")
async def attachment(file_id: str, database=Depends(db)):
    return await file_response(database, file_id)


@router.get("/announcements")
async def list_announcements(database=Depends(db)):
    return [document_view(item) async for item in database.announcements.find({}).sort("published_at", -1).limit(50)]


async def deliver_announcement(database, announcement_id):
    now = datetime.now(timezone.utc)
    item = await database.announcements.find_one_and_update({"_id": announcement_id, "delivery_status": {"$nin": ["sent", "no_recipients", "expired"]}, "$or": [{"delivery_lease": {"$exists": False}}, {"delivery_lease": {"$lte": now}}]}, {"$set": {"delivery_lease": now + timedelta(minutes=2), "delivery_status": "sending"}}, return_document=ReturnDocument.AFTER)
    if not item:
        existing = await database.announcements.find_one({"_id": announcement_id})
        if not existing:
            raise HTTPException(status_code=404, detail="announcement not found")
        return document_view(existing)
    status = "sent"
    lease = item["delivery_lease"]
    try:
        for offset, delivery in enumerate(item["deliveries"]):
            if delivery["sent"]:
                continue
            expires = delivery.get("expires_at")
            if expires and expires.replace(tzinfo=timezone.utc) <= now:
                status = "expired"
                break
            renewal = datetime.now(timezone.utc) + timedelta(minutes=2)
            values = {"delivery_lease": renewal}
            if not expires:
                values[f"deliveries.{offset}.expires_at"] = now + timedelta(hours=23)
            claimed = await database.announcements.update_one({"_id": announcement_id, "delivery_lease": lease}, {"$set": values})
            if claimed.modified_count != 1:
                return document_view(await database.announcements.find_one({"_id": announcement_id}))
            lease = renewal
            await multicast_line(delivery["to"], announcement_message(item["title"], item["body"], item["published_at"]), delivery["retry_key"])
            await database.announcements.update_one({"_id": announcement_id, f"deliveries.{offset}.sent": False}, {"$set": {f"deliveries.{offset}.sent": True}, "$inc": {"sent_count": len(delivery["to"])}})
    except (httpx.HTTPError, HTTPException):
        status = "failed"
    await database.announcements.update_one({"_id": announcement_id, "delivery_lease": lease}, {"$set": {"delivery_status": status}, "$unset": {"delivery_lease": ""}})
    return document_view(await database.announcements.find_one({"_id": announcement_id}))


@router.post("/announcements", status_code=201)
async def create_announcement(data: AnnouncementCreate, database=Depends(db), actor=Depends(require_admin)):
    key = data.request_key or secrets.token_urlsafe(24)
    announcement_id = f"AN-{sha256(actor['id'] + ':' + key)[:24]}"
    recipients = [item["line_user_id"] async for item in database.employees.find({"active": True, "line_user_id": {"$exists": True}})]
    announcement = {"_id": announcement_id, "title": data.title, "body": data.body, "published_at": datetime.now(timezone.utc), "recipient_count": len(recipients), "sent_count": 0, "delivery_status": "pending" if recipients else "no_recipients", "deliveries": [{"to": recipients[offset:offset + 500], "retry_key": str(uuid.uuid4()), "sent": False} for offset in range(0, len(recipients), 500)]}
    try:
        async def create(session):
            await database.announcements.insert_one(announcement, session=session)
            await audit(database, actor, "announcement.create", announcement_id, session)
        await transaction(database, create)
    except DuplicateKeyError:
        existing = await database.announcements.find_one({"_id": announcement_id})
        if not existing or existing["title"] != data.title or existing["body"] != data.body:
            raise HTTPException(status_code=409, detail="request key is already used")
    return await deliver_announcement(database, announcement_id)


@router.post("/announcements/{announcement_id}/retry")
async def retry_announcement(announcement_id: str, database=Depends(db), actor=Depends(require_admin)):
    await audit(database, actor, "announcement.retry", announcement_id)
    return await deliver_announcement(database, announcement_id)


@router.get("/leaves")
async def list_leaves(database=Depends(db)):
    employees = {item["_id"]: item["name"] async for item in database.employees.find({})}
    result = [{**document_view(item), "name": employees.get(item["employee_code"], "-")} async for item in database.leave_requests.find({}).sort("created_at", -1).limit(500)]
    return sorted(result, key=lambda value: value["status"] != "pending")


async def notify_leave(database, leave_id):
    leave = await database.leave_requests.find_one({"_id": leave_id})
    if not leave or leave.get("status") not in {"approved", "rejected"}:
        raise HTTPException(status_code=409, detail="leave request is not decided")
    if leave.get("notification_status") == "sent":
        return "sent"
    until = leave.get("notification_expires_at")
    if until and until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        await database.leave_requests.update_one({"_id": leave_id}, {"$set": {"notification_status": "expired"}})
        return "expired"
    if not leave.get("notification_to"):
        await database.leave_requests.update_one({"_id": leave_id}, {"$set": {"notification_status": "not_linked"}})
        return "not_linked"
    if not until:
        await database.leave_requests.update_one({"_id": leave_id}, {"$set": {"notification_expires_at": datetime.now(timezone.utc) + timedelta(hours=23)}})
    label = "อนุมัติแล้ว" if leave["status"] == "approved" else "ไม่อนุมัติ"
    try:
        await push_line(leave["notification_to"], f"คำขอลา #{leave_id}: {label}\n{leave['start_date']} – {leave['end_date']} ({leave['days']} วัน)", leave["notification_key"])
        status = "sent"
    except (httpx.HTTPError, HTTPException):
        status = "failed"
    await database.leave_requests.update_one({"_id": leave_id}, {"$set": {"notification_status": status}})
    return status


@router.post("/leaves/{leave_id}/decision")
async def decide_leave(leave_id: str, data: LeaveDecision, database=Depends(db), redis=Depends(cache), actor=Depends(require_admin)):
    if actor["role"] not in {"hr", "admin"}:
        raise HTTPException(status_code=403, detail="HR access required")
    async def decide(session):
        leave = await database.leave_requests.find_one({"_id": leave_id, "status": "pending"}, session=session)
        if not leave:
            raise HTTPException(status_code=409, detail="leave request was already decided or not found")
        employee = await database.employees.find_one_and_update({"_id": leave["employee_code"]}, {"$inc": {"leave_revision": 1}}, session=session)
        if not employee:
            raise HTTPException(status_code=404, detail="employee not found")
        if data.decision == "approved":
            if not employee["active"] or int(leave["start_date"][:4]) != datetime.now(ZoneInfo("Asia/Bangkok")).year:
                raise HTTPException(status_code=409, detail="ไม่สามารถอนุมัติบัญชีที่ปิดใช้งานหรือคำขอจากปีก่อน")
            await current_balances(database, employee, session)
            balance = await database.employees.update_one({"_id": employee["_id"], f"balances.{leave['leave_type']}": {"$gte": leave["days"]}}, {"$inc": {f"balances.{leave['leave_type']}": -leave["days"]}}, session=session)
            if balance.modified_count != 1:
                raise HTTPException(status_code=409, detail="leave balance is insufficient")
        final = {"status": data.decision, "decided_by": actor["id"], "decided_at": datetime.now(timezone.utc), "notification_to": employee.get("line_user_id"), "notification_key": str(uuid.uuid4()), "notification_status": "pending"}
        await database.leave_requests.update_one({"_id": leave_id, "status": "pending"}, {"$set": final}, session=session)
        await audit(database, actor, f"leave.{data.decision}", leave_id, session)
    await transaction(database, decide)
    if redis is not None:
        await redis.delete("summary")
    return {"ok": True, "notification_status": await notify_leave(database, leave_id)}


@router.post("/leaves/{leave_id}/notify")
async def retry_leave_notification(leave_id: str, database=Depends(db), actor=Depends(require_admin)):
    await audit(database, actor, "leave.notify", leave_id)
    return {"notification_status": await notify_leave(database, leave_id)}


@router.get("/holidays")
async def list_holidays(database=Depends(db)):
    return [document_view(item) async for item in database.holidays.find({}).sort("_id", 1)]


@router.post("/holidays", status_code=201)
async def create_holiday(data: HolidayCreate, database=Depends(db), actor=Depends(require_admin)):
    async def create(session):
        await database.holidays.update_one({"_id": data.date.isoformat()}, {"$set": {"name": data.name}}, upsert=True, session=session)
        await audit(database, actor, "holiday.save", data.date.isoformat(), session)
    await transaction(database, create)
    return {"ok": True}


@router.delete("/holidays/{holiday_date}")
async def delete_holiday(holiday_date: str, database=Depends(db), actor=Depends(require_admin)):
    async def remove(session):
        await database.holidays.delete_one({"_id": holiday_date}, session=session)
        await audit(database, actor, "holiday.delete", holiday_date, session)
    await transaction(database, remove)
    return {"ok": True}


@router.get("/audit")
async def list_audit(database=Depends(db), actor=Depends(require_admin)):
    if actor["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return [document_view(item) async for item in database.audit_logs.find({}).sort("created_at", -1).limit(100)]
