import secrets
from datetime import date
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response

from .core import LINE_LOGIN_CHANNEL_ID, PUBLIC_BASE_URL, db, issue_liff_token, read_liff_token, seaweed_read, seaweed_upload
from .leaves import submit_leave
from .schemas import LiffLeaveCreate, LiffSessionCreate

router = APIRouter(prefix="/api/liff")
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}


async def current_employee(authorization: Annotated[str | None, Header()] = None, database=Depends(db)):
    user_id = read_liff_token(authorization.removeprefix("Bearer ") if authorization else "")
    employee = await database.employees.find_one({"line_user_id": user_id, "active": True}) if user_id else None
    if not employee: raise HTTPException(status_code=401, detail="LIFF session is invalid or expired")
    return employee


@router.post("/session")
async def create_session(data: LiffSessionCreate, database=Depends(db)):
    if not LINE_LOGIN_CHANNEL_ID: raise HTTPException(status_code=503, detail="LINE Login is not configured")
    async with httpx.AsyncClient(timeout=10) as client: response = await client.post("https://api.line.me/oauth2/v2.1/verify", data={"id_token": data.id_token, "client_id": LINE_LOGIN_CHANNEL_ID})
    user_id = response.json().get("sub") if response.is_success else None
    employee = await database.employees.find_one({"line_user_id": user_id, "active": True}) if user_id else None
    if not employee: raise HTTPException(status_code=403, detail="ยังไม่ได้ยืนยันตัวพนักงาน กรุณาติดต่อ HR")
    return {"token": issue_liff_token(user_id), "name": employee["name"]}


@router.get("/balances")
async def balances(employee=Depends(current_employee)):
    return [{"leave_type": key, "remaining_days": value} for key, value in employee["balances"].items()]


@router.get("/leaves")
async def leaves(employee=Depends(current_employee), database=Depends(db)):
    return [{**item, "id": item.pop("_id")} async for item in database.leave_requests.find({"employee_code": employee["_id"]}).sort("created_at", -1)]


@router.get("/announcements")
async def announcements(database=Depends(db)):
    return [{**item, "id": item.pop("_id")} async for item in database.announcements.find({}).sort("published_at", -1).limit(20)]


@router.post("/attachments", status_code=201)
async def upload_attachment(file: Annotated[UploadFile, File()], employee=Depends(current_employee), authorization: Annotated[str | None, Header()] = None, database=Depends(db)):
    if file.content_type not in ALLOWED_TYPES: raise HTTPException(status_code=415, detail="รองรับเฉพาะ PDF, JPG และ PNG")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024: raise HTTPException(status_code=413, detail="ไฟล์ต้องไม่เกิน 10 MB")
    fid = await seaweed_upload(file.filename or "file", content, file.content_type)
    file_id = f"F-{secrets.token_hex(8)}"
    await database.files.insert_one({"_id": file_id, "employee_code": employee["_id"], "fid": fid, "name": file.filename, "content_type": file.content_type})
    token = authorization.removeprefix("Bearer ") if authorization else ""
    return {"url": f"{PUBLIC_BASE_URL}/api/liff/attachments/{file_id}?token={token}", "name": file.filename}


@router.get("/attachments/{file_id}")
async def attachment(file_id: str, token: str, database=Depends(db)):
    user_id = read_liff_token(token)
    employee = await database.employees.find_one({"line_user_id": user_id, "active": True}) if user_id else None
    file = await database.files.find_one({"_id": file_id, "employee_code": employee["_id"]}) if employee else None
    if not file: raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return Response(await seaweed_read(file["fid"]), media_type=file["content_type"], headers={"Content-Disposition": f'attachment; filename="{file["name"]}"'})


@router.post("/leaves", status_code=201)
async def create_leave(data: LiffLeaveCreate, employee=Depends(current_employee), database=Depends(db)):
    try: request_id, days = await submit_leave(database, employee["_id"], data.leave_type, date.fromisoformat(data.start_date), date.fromisoformat(data.end_date), data.reason, attachment_url=data.attachment_url)
    except ValueError: raise HTTPException(status_code=422, detail="รูปแบบวันที่ไม่ถูกต้อง")
    return {"id": request_id, "days": days, "status": "pending"}
