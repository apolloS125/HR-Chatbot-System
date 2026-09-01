import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from .core import LINE_LOGIN_CHANNEL_ID, LINE_LOGIN_CHANNEL_SECRET, PUBLIC_BASE_URL, base64url, db, sha256

router = APIRouter(prefix="/auth/line")


@router.get("/start")
async def line_login_start(employee_code: str, link_code: str, database=Depends(db)):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET: raise HTTPException(status_code=503, detail="LINE Login is not configured")
    employee = await database.employees.find_one({"_id": employee_code.upper(), "active": True, "link_code_hash": sha256(link_code), "link_code_expires_at": {"$gt": datetime.now(timezone.utc)}})
    if not employee: raise HTTPException(status_code=400, detail="link is invalid or expired")
    await database.employees.update_one({"_id": employee["_id"]}, {"$unset": {"link_code_hash": "", "link_code_expires_at": ""}})
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    await database.line_oauth_sessions.insert_one({"_id": state, "employee_code": employee["_id"], "nonce": nonce, "code_verifier": verifier, "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10)})
    query = urlencode({"response_type": "code", "client_id": LINE_LOGIN_CHANNEL_ID, "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback", "state": state, "scope": "openid profile", "nonce": nonce, "code_challenge": base64url(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"})
    return RedirectResponse(f"https://access.line.me/oauth2/v2.1/authorize?{query}")


@router.get("/callback", response_class=HTMLResponse)
async def line_login_callback(code: str, state: str, database=Depends(db)):
    session = await database.line_oauth_sessions.find_one_and_delete({"_id": state, "expires_at": {"$gt": datetime.now(timezone.utc)}})
    if not session: raise HTTPException(status_code=400, detail="login session is invalid or expired")
    async with httpx.AsyncClient(timeout=10) as client:
        token = await client.post("https://api.line.me/oauth2/v2.1/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback", "client_id": LINE_LOGIN_CHANNEL_ID, "client_secret": LINE_LOGIN_CHANNEL_SECRET, "code_verifier": session["code_verifier"]})
        verify = await client.post("https://api.line.me/oauth2/v2.1/verify", data={"id_token": token.json().get("id_token"), "client_id": LINE_LOGIN_CHANNEL_ID, "nonce": session["nonce"]})
    if token.is_error or verify.is_error or not (user_id := verify.json().get("sub")): raise HTTPException(status_code=400, detail="LINE identity verification failed")
    linked = await database.employees.find_one({"line_user_id": user_id, "_id": {"$ne": session["employee_code"]}})
    if linked: raise HTTPException(status_code=409, detail="LINE account is linked to another employee")
    if not await database.employees.find_one_and_update({"_id": session["employee_code"], "active": True}, {"$set": {"line_user_id": user_id, "line_linked_at": datetime.now(timezone.utc)}}): raise HTTPException(status_code=409, detail="employee account is inactive")
    return HTMLResponse("<!doctype html><html lang='th'><meta charset='utf-8'><title>เชื่อมบัญชีสำเร็จ</title><body><h1>เชื่อมบัญชีสำเร็จ</h1><p>กลับไปใช้งาน HR Chatbot ใน LINE ได้เลย</p></body></html>")
