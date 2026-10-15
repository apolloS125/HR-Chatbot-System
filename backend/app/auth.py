import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pymongo.errors import DuplicateKeyError

from .core import (
    LINE_LOGIN_CHANNEL_ID,
    LINE_LOGIN_CHANNEL_SECRET,
    PUBLIC_BASE_URL,
    audit,
    base64url,
    db,
    sha256,
    transaction,
)
from .http_client import outbound_client
from .line_identity import verify_line_identity

router = APIRouter(prefix="/auth/line")


@router.get("/start")
async def line_login_prompt(employee_code: str, link_code: str, database=Depends(db)):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")

    employee = await database.employees.find_one(
        {
            "_id": employee_code.upper(),
            "active": True,
            "line_user_id": {"$exists": False},
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
      body {{
        color: #173b2b;
        font-family: system-ui, sans-serif;
        margin: 12vh auto;
        max-width: 28rem;
        padding: 1.5rem;
      }}
      .primary-button {{
        background: #087747;
        border: 0;
        border-radius: .75rem;
        color: white;
        font-size: 1rem;
        font-weight: 700;
        padding: .9rem 1.2rem;
      }}
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
async def line_login_start(
    employee_code: str = Form(),
    link_code: str = Form(),
    database=Depends(db),
):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")

    state = secrets.token_urlsafe(32)
    employee = await database.employees.find_one_and_update(
        {
            "_id": employee_code.upper(),
            "active": True,
            "line_user_id": {"$exists": False},
            "link_code_hash": sha256(link_code),
            "link_code_expires_at": {"$gt": datetime.now(timezone.utc)},
        },
        {
            "$unset": {"link_code_hash": "", "link_code_expires_at": ""},
            "$set": {"line_link_version": state},
        },
    )
    if not employee:
        raise HTTPException(status_code=400, detail="link is invalid or expired")

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
    authorize_url = f"https://access.line.me/oauth2/v2.1/authorize?{query}"
    return RedirectResponse(authorize_url, status_code=303)


@router.get("/callback", response_class=HTMLResponse)
async def line_login_callback(code: str, state: str, database=Depends(db)):
    session = await database.line_oauth_sessions.find_one_and_delete(
        {"_id": state, "expires_at": {"$gt": datetime.now(timezone.utc)}}
    )
    if not session:
        raise HTTPException(status_code=400, detail="login session is invalid or expired")

    try:
        async with outbound_client() as client:
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
            token.raise_for_status()
            id_token = token.json()["id_token"]
            if not isinstance(id_token, str) or not id_token:
                raise ValueError("missing ID token")
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="LINE Login is unavailable") from error
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=400, detail="LINE identity verification failed") from error
    user_id = await verify_line_identity(id_token, LINE_LOGIN_CHANNEL_ID, session["nonce"])
    await bind_line_account(database, session["employee_code"], user_id, state)

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
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


async def bind_line_account(database, employee_code: str, user_id: str, version: str):
    async def bind(session):
        employee = await database.employees.find_one_and_update(
            {
                "_id": employee_code,
                "active": True,
                "line_user_id": {"$exists": False},
                "line_link_version": version,
            },
            {"$set": {"line_user_id": user_id, "line_linked_at": datetime.now(timezone.utc)}},
            session=session,
        )
        if not employee:
            raise HTTPException(status_code=409, detail="employee is inactive or already linked")
        await audit(
            database, {"id": f"line:{user_id}"}, "employee.line_bind", employee_code, session
        )

    try:
        await transaction(database, bind)
    except DuplicateKeyError as error:
        raise HTTPException(
            status_code=409, detail="LINE account is linked to another employee"
        ) from error
