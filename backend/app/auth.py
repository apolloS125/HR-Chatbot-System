import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from .core import LINE_LOGIN_CHANNEL_ID, LINE_LOGIN_CHANNEL_SECRET, PUBLIC_BASE_URL, base64url, db, sha256

router = APIRouter(prefix="/auth/line")


@router.get("/start")
async def line_login_prompt(employee_code: str, link_code: str, database=Depends(db)):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")

    employee = await database.employees.find_one(
        {
            "_id": employee_code.upper(),
            "active": True,
            "link_code_hash": sha256(link_code),
            "link_code_expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    if not employee:
        raise HTTPException(status_code=400, detail="link is invalid or expired")

    safe_name = escape(employee["name"])
    safe_employee_code = escape(employee_code, quote=True)
    safe_link_code = escape(link_code, quote=True)
    page = f"""<!doctype html>
<html lang="th">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ยืนยันบัญชี LINE</title>
    <style>
      body {
        color: #173b2b;
        font-family: system-ui, sans-serif;
        margin: 12vh auto;
        max-width: 28rem;
        padding: 1.5rem;
      }
      .primary-button {
        background: #087747;
        border: 0;
        border-radius: .75rem;
        color: white;
        font-size: 1rem;
        font-weight: 700;
        padding: .9rem 1.2rem;
      }
    </style>
  </head>
  <body>
    <h1>ยืนยันบัญชี LINE</h1>
    <p>
      กดปุ่มด้านล่างเพื่อเชื่อมบัญชี LINE กับพนักงาน {safe_name}
    </p>
    <form method="post" action="/auth/line/start">
      <input type="hidden" name="employee_code" value="{safe_employee_code}">
      <input type="hidden" name="link_code" value="{safe_link_code}">
      <button class="primary-button">
        เชื่อมบัญชี LINE
      </button>
    </form>
  </body>
</html>"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@router.post("/start")
async def line_login_start(employee_code: str = Form(), link_code: str = Form(), database=Depends(db)):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")

    employee = await database.employees.find_one_and_update(
        {
            "_id": employee_code.upper(),
            "active": True,
            "link_code_hash": sha256(link_code),
            "link_code_expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {"$unset": {"link_code_hash": "", "link_code_expires_at": ""}},
    )
    if not employee:
        raise HTTPException(status_code=400, detail="link is invalid or expired")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    await database.line_oauth_sessions.insert_one(
        {
            "_id": state,
            "employee_code": employee["_id"],
            "nonce": nonce,
            "code_verifier": verifier,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        }
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": LINE_LOGIN_CHANNEL_ID,
            "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback",
            "state": state,
            "scope": "openid profile",
            "nonce": nonce,
            "code_challenge": base64url(hashlib.sha256(verifier.encode()).digest()),
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"https://access.line.me/oauth2/v2.1/authorize?{query}", status_code=303)


@router.get("/callback", response_class=HTMLResponse)
async def line_login_callback(code: str, state: str, database=Depends(db)):
    session = await database.line_oauth_sessions.find_one_and_delete(
        {"_id": state, "expires_at": {"$gt": datetime.now(timezone.utc)}}
    )
    if not session:
        raise HTTPException(status_code=400, detail="login session is invalid or expired")

    async with httpx.AsyncClient(timeout=10) as client:
        token = await client.post(
            "https://api.line.me/oauth2/v2.1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback",
                "client_id": LINE_LOGIN_CHANNEL_ID,
                "client_secret": LINE_LOGIN_CHANNEL_SECRET,
                "code_verifier": session["code_verifier"],
            },
        )
        if token.is_error or not token.json().get("id_token"):
            raise HTTPException(status_code=400, detail="LINE identity verification failed")
        verify = await client.post(
            "https://api.line.me/oauth2/v2.1/verify",
            data={
                "id_token": token.json().get("id_token"),
                "client_id": LINE_LOGIN_CHANNEL_ID,
                "nonce": session["nonce"],
            },
        )

    user_id = verify.json().get("sub") if verify.is_success else None
    if not user_id:
        raise HTTPException(status_code=400, detail="LINE identity verification failed")

    linked = await database.employees.find_one(
        {"line_user_id": user_id, "_id": {"$ne": session["employee_code"]}}
    )
    if linked:
        raise HTTPException(status_code=409, detail="LINE account is linked to another employee")

    employee = await database.employees.find_one_and_update(
        {"_id": session["employee_code"], "active": True},
        {
            "$set": {
                "line_user_id": user_id,
                "line_linked_at": datetime.now(timezone.utc),
            }
        },
    )
    if not employee:
        raise HTTPException(status_code=409, detail="employee account is inactive")

    page = """<!doctype html>
<html lang="th">
  <head>
    <meta charset="utf-8">
    <title>เชื่อมบัญชีสำเร็จ</title>
  </head>
  <body>
    <h1>เชื่อมบัญชีสำเร็จ</h1>
    <p>กลับไปใช้งาน HR Chatbot ใน LINE ได้เลย</p>
  </body>
</html>"""
    return HTMLResponse(page)
