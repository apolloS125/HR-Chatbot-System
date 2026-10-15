import asyncio
import base64
import hashlib
import hmac
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.datastructures import Headers
from starlette.requests import Request

from app import chatbot, core, http_client, liff, line_identity, rate_limit
from app.schemas import LiffLeaveCreate, LiffSessionCreate


def identity(**changes):
    return {
        "iss": "https://access.line.me",
        "sub": "U123",
        "aud": "channel",
        "exp": 4102444800,
        "nonce": "expected-nonce",
        **changes,
    }


@pytest.mark.parametrize(
    "claims",
    [
        identity(aud="other-channel"),
        identity(exp=0),
        identity(exp="4102444800"),
        identity(exp=True),
        identity(iss="https://attacker.test"),
        identity(sub=""),
        identity(nonce="wrong"),
        {"sub": "U123"},
        [],
    ],
)
def test_line_verify_rejects_invalid_claims(monkeypatch, claims):
    monkeypatch.setattr(
        line_identity,
        "outbound_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=claims))
        ),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(line_identity.verify_line_identity("token", "channel", "expected-nonce"))
    assert error.value.status_code == 401


@pytest.mark.parametrize("status,expected", [(400, 401), (429, 503), (500, 503)])
def test_line_verify_handles_http_failure(monkeypatch, status, expected):
    monkeypatch.setattr(
        line_identity,
        "outbound_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status))),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(line_identity.verify_line_identity("token", "channel"))
    assert error.value.status_code == expected


def test_line_verify_uses_server_claims_and_closes_client(monkeypatch):
    def handler(request):
        assert request.content == b"id_token=token&client_id=channel&nonce=expected-nonce"
        return httpx.Response(200, json=identity())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(line_identity, "outbound_client", lambda: client)
    result = asyncio.run(line_identity.verify_line_identity("token", "channel", "expected-nonce"))
    assert result == "U123"
    assert client.is_closed


def test_line_verify_network_failure_is_unavailable_and_closes_client(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("offline", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(line_identity, "outbound_client", lambda: client)
    with pytest.raises(HTTPException) as error:
        asyncio.run(line_identity.verify_line_identity("token", "channel"))
    assert error.value.status_code == 503
    assert client.is_closed


def test_liff_rejects_browser_identity_and_oversized_token():
    with pytest.raises(ValidationError):
        LiffSessionCreate(id_token="token", userId="victim")
    with pytest.raises(ValidationError):
        LiffSessionCreate(id_token="x" * 8193)


@pytest.mark.parametrize("signature", [None, "wrong", "valid", "tampered"])
def test_webhook_checks_real_signature_before_rate_limit_or_tasks(monkeypatch, signature):
    monkeypatch.setattr(core, "LINE_CHANNEL_SECRET", "test-secret")
    body = b'{"events":[]}'
    digest = hmac.new(b"test-secret", body, hashlib.sha256).digest()
    signed = base64.b64encode(digest).decode()
    provided = signed if signature in {"valid", "tampered"} else signature
    if signature == "tampered":
        body = b'{"events": [{}]}'

    async def receive():
        return {"type": "http.request", "body": body}

    redis = SimpleNamespace(eval=AsyncMock(return_value=0))
    app = SimpleNamespace(state=SimpleNamespace(redis=redis, mongo=object()))
    request = Request({"type": "http", "app": app}, receive)
    tasks = BackgroundTasks()
    if signature == "valid":
        assert asyncio.run(chatbot.line_webhook(request, tasks, provided)) == {"ok": True}
        assert len(tasks.tasks) == 1
        redis.eval.assert_awaited_once()
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(chatbot.line_webhook(request, tasks, provided))
        assert error.value.status_code == 401
        assert tasks.tasks == []
        redis.eval.assert_not_awaited()


def test_inactive_employee_with_existing_liff_session_is_denied():
    database = SimpleNamespace(employees=SimpleNamespace(find_one=AsyncMock(return_value=None)))
    redis = SimpleNamespace(eval=AsyncMock(return_value=0))
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            liff.current_employee(f"Bearer {core.issue_liff_token('U123')}", database, redis)
        )
    assert error.value.status_code == 401
    database.employees.find_one.assert_awaited_once_with({"line_user_id": "U123", "active": True})
    redis.eval.assert_not_awaited()


@pytest.mark.parametrize(
    "content,content_type,status",
    [
        (b"<script>evil()</script>", "application/pdf", 415),
        (b"%PDF-fake-jpeg", "image/jpeg", 415),
        (b"\xff\xd8\xff", "image/png", 415),
        (b"%PDF-file", "text/html", 415),
        (b"%PDF-" + b"x" * liff.MAX_ATTACHMENT_SIZE, "application/pdf", 413),
    ],
)
def test_attachment_rejects_spoofed_mime_and_large_files(
    monkeypatch, content, content_type, status
):
    upload = AsyncMock()
    monkeypatch.setattr(liff, "seaweed_upload", upload)
    file = UploadFile(
        io.BytesIO(content), filename="medical.pdf", headers=Headers({"content-type": content_type})
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(liff.upload_attachment(file, {"_id": "E001"}, object()))
    assert error.value.status_code == status
    upload.assert_not_awaited()


@pytest.mark.parametrize("value", [0, 7])
def test_rate_limit_returns_retry_after(value):
    redis = SimpleNamespace(eval=AsyncMock(return_value=value))
    if value:
        with pytest.raises(HTTPException) as error:
            asyncio.run(rate_limit.enforce_limit(redis, "test", "user", 10))
        assert error.value.status_code == 429
        assert error.value.headers == {"Retry-After": "7"}
    else:
        asyncio.run(rate_limit.enforce_limit(redis, "test", "user", 10))
    args = redis.eval.call_args.args
    assert args[2] == f"rate:test:{core.sha256('user')}"
    assert args[3:] == (10, 60)


def test_rate_limit_fails_closed_when_redis_is_unavailable():
    redis = SimpleNamespace(eval=AsyncMock(side_effect=RedisConnectionError()))
    with pytest.raises(HTTPException) as error:
        asyncio.run(rate_limit.enforce_limit(redis, "test", "user", 10))
    assert error.value.status_code == 503


def test_session_rate_limit_ignores_spoofed_forwarded_ip():
    request = Request(
        {
            "type": "http",
            "client": ("192.0.2.1", 1234),
            "headers": [(b"x-forwarded-for", b"attacker-supplied")],
        }
    )
    redis = SimpleNamespace(eval=AsyncMock(return_value=0))
    asyncio.run(rate_limit.limit_liff_session(request, redis))
    assert redis.eval.call_args.args[2] == f"rate:liff-session:{core.sha256('192.0.2.1')}"


def test_outbound_http_has_bounded_connect_retry_and_timeouts(monkeypatch):
    transport = httpx.MockTransport(lambda _: httpx.Response(200))
    # A synchronous constructor records the retry policy without making network calls.
    options = []
    monkeypatch.setattr(
        http_client.httpx, "AsyncHTTPTransport", lambda **kw: options.append(kw) or transport
    )

    async def exercise():
        async with http_client.outbound_client(timeout=15) as client:
            assert client.timeout.connect == 3
            assert client.timeout.pool == 3
            assert client.timeout.read == 15
            assert client.timeout.write == 15
        assert client.is_closed

    asyncio.run(exercise())
    assert options == [{"retries": 2}]


@pytest.mark.parametrize(
    "changes",
    [
        {"leave_type": "admin_override"},
        {"start_date": "not-a-date"},
        {"end_date": "2026-02-30"},
        {"half_day": "all"},
    ],
)
def test_untrusted_leave_fields_are_validated(changes):
    with pytest.raises(ValidationError):
        LiffLeaveCreate.model_validate(
            {
                "leave_type": "vacation",
                "start_date": "2026-08-20",
                "end_date": "2026-08-21",
                "request_key": "request-key-123456",
                **changes,
            }
        )
