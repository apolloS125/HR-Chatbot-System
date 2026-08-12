import hashlib
import secrets
from typing import Annotated
from urllib.parse import urlencode

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from .core import (
    LINE_LOGIN_CHANNEL_ID,
    LINE_LOGIN_CHANNEL_SECRET,
    PUBLIC_BASE_URL,
    base64url,
    db,
    sha256,
)


router = APIRouter(prefix="/auth/line")


@router.get("/start")
async def line_login_start(
    employee_code: str,
    link_code: str,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    if not LINE_LOGIN_CHANNEL_ID or not LINE_LOGIN_CHANNEL_SECRET:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")

    employee = await pool.fetchrow(
        """
        UPDATE employees
        SET link_code_hash = NULL, link_code_expires_at = NULL
        WHERE employee_code = $1 AND active
          AND link_code_hash = $2 AND link_code_expires_at > now()
        RETURNING id
        """,
        employee_code.upper(), sha256(link_code),
    )
    if not employee:
        raise HTTPException(status_code=400, detail="link is invalid or expired")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64url(hashlib.sha256(verifier.encode()).digest())
    await pool.execute(
        """
        INSERT INTO line_oauth_sessions (state, employee_id, nonce, code_verifier, expires_at)
        VALUES ($1, $2, $3, $4, now() + interval '10 minutes')
        """,
        state, employee["id"], nonce, verifier,
    )
    query = urlencode({
        "response_type": "code",
        "client_id": LINE_LOGIN_CHANNEL_ID,
        "redirect_uri": f"{PUBLIC_BASE_URL}/auth/line/callback",
        "state": state,
        "scope": "openid profile",
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return RedirectResponse(f"https://access.line.me/oauth2/v2.1/authorize?{query}")


@router.get("/callback", response_class=HTMLResponse)
async def line_login_callback(
    code: str,
    state: str,
    pool: Annotated[asyncpg.Pool, Depends(db)],
):
    async with pool.acquire() as conn, conn.transaction():
        session = await conn.fetchrow(
            """
            DELETE FROM line_oauth_sessions
            WHERE state = $1 AND expires_at > now()
            RETURNING employee_id, nonce, code_verifier
            """,
            state,
        )
        if not session:
            raise HTTPException(status_code=400, detail="login session is invalid or expired")

        async with httpx.AsyncClient(timeout=10) as client:
            token_response = await client.post(
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
            if token_response.is_error:
                raise HTTPException(status_code=400, detail="LINE token exchange failed")
            id_token = token_response.json().get("id_token")
            verify_response = await client.post(
                "https://api.line.me/oauth2/v2.1/verify",
                data={
                    "id_token": id_token,
                    "client_id": LINE_LOGIN_CHANNEL_ID,
                    "nonce": session["nonce"],
                },
            )
            if verify_response.is_error:
                raise HTTPException(status_code=400, detail="LINE identity verification failed")
            line_user_id = verify_response.json().get("sub")
            if not line_user_id:
                raise HTTPException(status_code=400, detail="LINE user ID is missing")

        linked_employee = await conn.fetchval(
            "SELECT employee_code FROM employees WHERE line_user_id = $1 AND id <> $2",
            line_user_id, session["employee_id"],
        )
        if linked_employee:
            raise HTTPException(status_code=409, detail="LINE account is linked to another employee")
        updated = await conn.fetchval(
            """
            UPDATE employees
            SET line_user_id = $1, line_linked_at = now(),
                link_code_hash = NULL, link_code_expires_at = NULL
            WHERE id = $2 AND active
            RETURNING id
            """,
            line_user_id, session["employee_id"],
        )
        if not updated:
            raise HTTPException(status_code=409, detail="employee account is inactive")

    return HTMLResponse("""
    <!doctype html><html lang="th"><meta charset="utf-8">
    <title>เชื่อมบัญชีสำเร็จ</title>
    <body style="font-family:system-ui;text-align:center;padding:4rem">
      <h1>เชื่อมบัญชีสำเร็จ</h1><p>กลับไปใช้งาน HR Chatbot ใน LINE ได้เลย</p>
    </body></html>
    """)
