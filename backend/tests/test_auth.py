import asyncio
import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import core


def basic(username):
    token = base64.b64encode(f"{username}:incorrect".encode()).decode()
    return f"Basic {token}"


def test_failed_accounts_do_not_block_other_accounts(monkeypatch):
    authenticate = AsyncMock(side_effect=HTTPException(401, "invalid credentials"))
    monkeypatch.setattr(core, "authenticate_admin", authenticate)
    redis = SimpleNamespace(eval=AsyncMock(return_value=0), delete=AsyncMock())

    async def scenario():
        for index in range(60):
            with pytest.raises(HTTPException) as error:
                await core.require_admin(authorization=basic(f"bad-{index}"), redis=redis)
            assert error.value.status_code == 401
        authenticate.side_effect = None
        authenticate.return_value = {"id": "HR001", "role": "hr"}
        result = await core.require_admin(authorization=basic("HR001"), redis=redis)
        assert result["id"] == "HR001"
        reserve_keys = [
            call.args[2]
            for call in redis.eval.await_args_list
            if call.args[0] == core._RESERVE_LOGIN
        ]
        assert len(set(reserve_keys)) == 61
        assert all(call.args[1] == 1 for call in redis.eval.await_args_list)

    asyncio.run(scenario())


@pytest.mark.parametrize("retry_after", [1, 2, 4, 8, 16, 30])
def test_backoff_returns_actual_delay_without_checking_password(monkeypatch, retry_after):
    authenticate = AsyncMock()
    monkeypatch.setattr(core, "authenticate_admin", authenticate)
    redis = SimpleNamespace(eval=AsyncMock(return_value=retry_after))
    with pytest.raises(HTTPException) as error:
        asyncio.run(core.require_admin(authorization=basic("HR001"), redis=redis))
    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": str(retry_after)}
    authenticate.assert_not_awaited()


def test_existing_sessions_bypass_password_backoff(monkeypatch):
    actor = {"id": "HR001", "role": "hr"}
    authenticate = AsyncMock(return_value=actor)
    monkeypatch.setattr(core, "authenticate_admin", authenticate)
    redis = SimpleNamespace(eval=AsyncMock(return_value=30))
    result = asyncio.run(core.require_admin(authorization="Bearer existing-token", redis=redis))
    assert result == actor
    authenticate.assert_awaited_once()
    redis.eval.assert_not_awaited()


def test_successful_login_clears_only_its_own_backoff(monkeypatch):
    actor = {"id": "HR001", "role": "hr"}
    monkeypatch.setattr(core, "authenticate_admin", AsyncMock(return_value=actor))
    redis = SimpleNamespace(eval=AsyncMock(return_value=0), delete=AsyncMock())
    assert asyncio.run(core.require_admin(authorization=basic("hr001"), redis=redis)) == actor
    redis.delete.assert_awaited_once_with(f"login-backoff:{core.sha256('HR001')}")


def test_dashboard_stores_keyed_version_and_rejects_rotated_credentials(monkeypatch):
    password = "bootstrap-password-for-testing"
    monkeypatch.setattr(core, "HR_USERNAME", "bootstrap")
    monkeypatch.setattr(core, "HR_PASSWORD", password)
    monkeypatch.setattr(core, "LIFF_SESSION_SECRET", "independent-signing-secret-for-tests")
    redis = SimpleNamespace(set=AsyncMock(), get=AsyncMock())

    async def scenario():
        actor = {"id": "bootstrap", "role": "admin", "bootstrap": True}
        token = await core.create_dashboard_session(actor, None, redis)
        stored = redis.set.await_args.args[1]
        version = json.loads(stored)["version"]
        assert password not in stored
        assert version != hashlib.sha256(password.encode()).hexdigest()
        redis.get.return_value = stored
        assert await core.authenticate_admin(f"Bearer {token}", None, None, redis) == actor
        monkeypatch.setattr(core, "LIFF_SESSION_SECRET", "rotated-signing-secret-for-tests")
        assert version != core.credential_version(password)
        with pytest.raises(HTTPException) as error:
            await core.authenticate_admin(f"Bearer {token}", None, None, redis)
        assert error.value.status_code == 401

    asyncio.run(scenario())
