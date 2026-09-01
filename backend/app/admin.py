import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from .core import PUBLIC_BASE_URL, cache, db, require_admin, sha256
from .line_client import announcement_message, multicast_line
from .schemas import ActiveUpdate, AnnouncementCreate, EmployeeCreate, LeaveDecision

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


def employee_view(item):
    return {"id": item["_id"], "employee_code": item["_id"], "name": item["name"], "work_email": item["work_email"], "role": item["role"], "active": item["active"], "line_linked": bool(item.get("line_user_id")), "line_linked_at": item.get("line_linked_at")}


@router.get("/summary")
async def admin_summary(database=Depends(db), redis=Depends(cache)):
    key = "summary"
    if cached := await redis.get(key): return __import__("json").loads(cached)
    result = {"active_employees": await database.employees.count_documents({"active": True}), "linked_employees": await database.employees.count_documents({"active": True, "line_user_id": {"$exists": True}}), "pending_leaves": await database.leave_requests.count_documents({"status": "pending"})}
    await redis.setex(key, 30, __import__("json").dumps(result)); return result


@router.get("/employees")
async def list_employees(database=Depends(db)):
    return [employee_view(item) async for item in database.employees.find({"active": True}).sort("_id", 1)]


@router.post("/employees", status_code=201)
async def create_employee(data: EmployeeCreate, database=Depends(db), redis=Depends(cache)):
    code = data.employee_code.upper()
    try:
        await database.employees.insert_one({"_id": code, "name": data.name, "work_email": data.work_email.lower(), "role": data.role, "active": True, "balances": {"vacation": 10, "sick": 30, "personal": 5}, "created_at": datetime.now(timezone.utc)})
    except DuplicateKeyError: raise HTTPException(status_code=409, detail="employee code or email already exists")
    await redis.delete("summary")
    return employee_view(await database.employees.find_one({"_id": code}))


@router.post("/employees/{employee_id}/link")
async def issue_link_code(employee_id: str, database=Depends(db)):
    code = secrets.token_urlsafe(12)
    employee = await database.employees.find_one_and_update({"_id": employee_id, "active": True}, {"$set": {"link_code_hash": sha256(code), "link_code_expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)}}, return_document=True)
    if not employee: raise HTTPException(status_code=404, detail="active employee not found")
    return {"expires_in_minutes": 30, "link": f"{PUBLIC_BASE_URL}/auth/line/start?employee_code={employee['_id']}&link_code={code}"}


@router.patch("/employees/{employee_id}/active")
async def set_employee_active(employee_id: str, data: ActiveUpdate, database=Depends(db), redis=Depends(cache)):
    if not await database.employees.find_one_and_update({"_id": employee_id}, {"$set": {"active": data.active}}): raise HTTPException(status_code=404, detail="employee not found")
    await redis.delete("summary"); return {"ok": True}


@router.delete("/employees/{employee_id}")
async def delete_employee(employee_id: str, database=Depends(db), redis=Depends(cache)):
    await database.leave_requests.delete_many({"employee_code": employee_id})
    if not await database.employees.find_one_and_delete({"_id": employee_id}): raise HTTPException(status_code=404, detail="employee not found")
    await redis.delete("summary"); return {"ok": True}


@router.get("/announcements")
async def list_announcements(database=Depends(db)):
    return [{**item, "id": item.pop("_id")} async for item in database.announcements.find({}).sort("published_at", -1).limit(20)]


@router.post("/announcements", status_code=201)
async def create_announcement(data: AnnouncementCreate, database=Depends(db)):
    announcement = {"_id": f"AN-{secrets.token_hex(8)}", "title": data.title, "body": data.body, "published_at": datetime.now(timezone.utc)}
    await database.announcements.insert_one(announcement)
    recipients = [item["line_user_id"] async for item in database.employees.find({"active": True, "line_user_id": {"$exists": True}})]
    if recipients: await multicast_line(recipients, announcement_message(data.title, data.body, announcement["published_at"]))
    return {"id": announcement["_id"], "title": data.title, "body": data.body, "published_at": announcement["published_at"], "recipient_count": len(recipients)}


@router.get("/leaves")
async def list_leaves(database=Depends(db)):
    result = []
    async for leave in database.leave_requests.find({}).sort("created_at", -1):
        employee = await database.employees.find_one({"_id": leave["employee_code"]})
        result.append({"id": leave["_id"], "employee_code": leave["employee_code"], "name": employee["name"] if employee else "-", **{key: value for key, value in leave.items() if key not in {"_id", "employee_code"}}})
    return sorted(result, key=lambda value: value["status"] != "pending")


@router.post("/leaves/{leave_id}/decision")
async def decide_leave(leave_id: str, data: LeaveDecision, database=Depends(db), redis=Depends(cache)):
    leave = await database.leave_requests.find_one({"_id": leave_id, "status": "pending"})
    if not leave: raise HTTPException(status_code=409, detail="leave request was already decided or not found")
    if data.decision == "approved":
        employee = await database.employees.find_one({"_id": leave["employee_code"]})
        if not employee or employee["balances"].get(leave["leave_type"], 0) < leave["days"]: raise HTTPException(status_code=409, detail="leave balance is insufficient")
        await database.employees.update_one({"_id": leave["employee_code"]}, {"$inc": {f"balances.{leave['leave_type']}": -leave["days"]}})
    await database.leave_requests.update_one({"_id": leave_id}, {"$set": {"status": data.decision, "decided_by": data.decided_by, "decided_at": datetime.now(timezone.utc)}})
    await redis.delete("summary"); return {"ok": True}
