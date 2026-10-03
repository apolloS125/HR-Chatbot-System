"""Run with TEST_MONGODB_URL pointing to a disposable replica set."""
import asyncio
import base64
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app import admin, auth, core
from app.admin import create_announcement, decide_leave, delete_employee, deliver_announcement
from app.chatbot import handle_message
from app.core import db, hash_password, issue_liff_token
from app.leaves import cancel_leave, current_balances, submit_leave
from app.main import app
from app.schemas import AnnouncementCreate, LeaveDecision

ACTOR = {"id": "HR001", "role": "admin"}


def monday():
    day = date(datetime.now(timezone.utc).year, 1, 1)
    return day + timedelta(days=(7 - day.weekday()) % 7)


@pytest.fixture
def mongo():
    url = os.getenv("TEST_MONGODB_URL")
    if not url:
        pytest.skip("TEST_MONGODB_URL is required for replica-set integration tests")

    def run(scenario):
        async def exercise():
            client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
            database = client[f"hr_test_{secrets.token_hex(8)}"]
            employee = {
                "_id": "E001",
                "name": "Employee",
                "work_email": "e001@example.com",
                "role": "employee",
                "active": True,
                "balances": {"vacation": 10, "sick": 30, "personal": 5},
                "balances_year": monday().year,
                "line_user_id": "U123",
            }
            await database.employees.insert_one(employee)
            await database.leave_requests.create_index("source_event_id", unique=True, sparse=True)
            try:
                return await scenario(database)
            finally:
                app.dependency_overrides.clear()
                await client.drop_database(database.name)
                client.close()

        return asyncio.run(exercise())

    return run


def test_liff_leave_omits_null_source_event_id(mongo):
    async def scenario(database):
        key, days = await submit_leave(database, "E001", "vacation", monday(), monday(), "พักผ่อน")
        leave = await database.leave_requests.find_one({"_id": key})
        assert days == 1
        assert "source_event_id" not in leave

    mongo(scenario)


def test_concurrent_duplicate_requests_create_one_leave(mongo):
    async def scenario(database):
        requests = [
            submit_leave(
                database,
                "E001",
                "vacation",
                monday(),
                monday(),
                "พักผ่อน",
                source_event_id="event-1",
            )
            for _ in range(2)
        ]
        results = await asyncio.gather(*requests)
        assert results[0] == results[1]
        assert await database.leave_requests.count_documents({}) == 1

    mongo(scenario)


def test_half_days_holidays_overlap_and_reserved_balance(mongo):
    async def scenario(database):
        day = monday()
        await database.holidays.insert_one({"_id": day.isoformat(), "name": "holiday"})
        with pytest.raises(HTTPException) as error:
            await submit_leave(database, "E001", "vacation", day, day, "holiday")
        assert error.value.status_code == 422
        day += timedelta(days=1)
        await database.employees.update_one({"_id": "E001"}, {"$set": {"balances.vacation": 1}})
        first, days = await submit_leave(database, "E001", "vacation", day, day, "เช้า", half_day="morning")
        assert days == 0.5
        await submit_leave(database, "E001", "vacation", day, day, "บ่าย", half_day="afternoon")
        with pytest.raises(HTTPException):
            await submit_leave(database, "E001", "vacation", day, day, "ทับซ้อน")
        with pytest.raises(HTTPException):
            await submit_leave(
                database,
                "E001",
                "vacation",
                day + timedelta(days=1),
                day + timedelta(days=1),
                "ยอดไม่พอ",
            )
        await cancel_leave(database, first, "E001")
        _, days = await submit_leave(database, "E001", "vacation", day, day, "ใหม่", half_day="morning")
        assert days == 0.5

    mongo(scenario)


def test_approval_is_atomic_and_cannot_double_debit(mongo, monkeypatch):
    monkeypatch.setattr(admin, "push_line", AsyncMock())

    async def scenario(database):
        key, _ = await submit_leave(database, "E001", "vacation", monday(), monday(), "พักผ่อน")
        decisions = [
            decide_leave(key, LeaveDecision(decision="approved"), database, None, ACTOR)
            for _ in range(2)
        ]
        results = await asyncio.gather(*decisions, return_exceptions=True)
        assert sum(isinstance(result, HTTPException) for result in results) == 1
        assert (await database.employees.find_one({"_id": "E001"}))["balances"]["vacation"] == 9
        leave = await database.leave_requests.find_one({"_id": key})
        assert leave["status"] == "approved" and leave["decided_by"] == "HR001"

    mongo(scenario)


def test_failure_after_balance_debit_rolls_back_everything(mongo):
    async def scenario(database):
        key, _ = await submit_leave(database, "E001", "vacation", monday(), monday(), "พักผ่อน")
        collection = database.leave_requests
        async def fail(*args, **kwargs):
            raise RuntimeError("database fails after debit")

        wrapped = SimpleNamespace(
            client=database.client,
            employees=database.employees,
            audit_logs=database.audit_logs,
            leave_requests=SimpleNamespace(
                find_one=collection.find_one,
                update_one=fail,
            ),
        )
        with pytest.raises(RuntimeError):
            await decide_leave(
                key,
                LeaveDecision(decision="approved"),
                wrapped,
                None,
                ACTOR,
            )
        assert (await database.employees.find_one({"_id": "E001"}))["balances"]["vacation"] == 10
        assert (await collection.find_one({"_id": key}))["status"] == "pending"
        assert await database.audit_logs.count_documents({}) == 0

    mongo(scenario)


def test_delete_employee_removes_data_and_allows_reuse(mongo, monkeypatch):
    monkeypatch.setattr(admin, "seaweed_delete", AsyncMock())

    async def scenario(database):
        await database.employees.create_index("work_email", unique=True)
        key, _ = await submit_leave(database, "E001", "vacation", monday(), monday(), "พักผ่อน")
        await database.files.insert_one({"_id": "F-1", "employee_code": "E001", "fid": "fake"})
        await database.line_oauth_sessions.insert_one({"_id": "S-1", "employee_code": "E001"})
        await database.announcements.insert_one({"_id": "AN-1", "deliveries": [{"to": ["U123", "UOTHER"]}]})
        audit_entries = [
            {"actor": "E001", "action": "old", "subject": "other"},
            {"actor": "HR001", "action": "old", "subject": "E001"},
        ]
        await database.audit_logs.insert_many(audit_entries)
        await delete_employee("E001", database, SimpleNamespace(delete=AsyncMock()), ACTOR)
        assert await database.employees.find_one({"_id": "E001"}) is None
        assert await database.leave_requests.find_one({"_id": key}) is None
        assert await database.files.find_one({"_id": "F-1"}) is None
        assert await database.line_oauth_sessions.find_one({"_id": "S-1"}) is None
        announcement = await database.announcements.find_one({"_id": "AN-1"})
        assert announcement["deliveries"][0]["to"] == ["UOTHER"]
        audit_query = {"$or": [{"actor": "E001"}, {"subject": "E001"}]}
        assert await database.audit_logs.count_documents(audit_query) == 1
        admin.seaweed_delete.assert_awaited_once_with("fake")
        await database.employees.insert_one({"_id": "E001", "name": "Employee again", "work_email": "e001@example.com"})

    mongo(scenario)


def test_private_apis_check_session_and_attachment_owner(mongo, monkeypatch):
    monkeypatch.setattr(core, "seaweed_read", AsyncMock(return_value=b"%PDF-content"))

    async def scenario(database):
        own_file = {
            "_id": "F-1",
            "employee_code": "E001",
            "fid": "fake",
            "name": "medical.pdf",
            "content_type": "application/pdf",
        }
        other_file = {
            "_id": "F-other",
            "employee_code": "E002",
            "fid": "fake",
            "name": "other.pdf",
            "content_type": "application/pdf",
        }
        await database.files.insert_one(own_file)
        await database.files.insert_one(other_file)
        app.dependency_overrides[db] = lambda: database
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/liff/announcements")).status_code == 401
            headers = {"Authorization": f"Bearer {issue_liff_token('U123')}"}
            assert (await client.get("/api/liff/announcements", headers=headers)).status_code == 200
            response = await client.get("/api/liff/attachments/F-1", headers=headers)
            assert response.status_code == 200 and response.content == b"%PDF-content"
            assert (await client.get("/api/liff/attachments/F-other", headers=headers)).status_code == 404
            assert (await client.get("/api/liff/attachments/F-1?token=old-token")).status_code == 401
            admin_headers = {"X-Admin-Key": core.ADMIN_API_KEY}
            response = await client.get(
                "/api/admin/attachments/F-1",
                headers=admin_headers,
            )
            assert response.status_code == 200

    mongo(scenario)


def test_announcement_retry_keeps_batch_keys_and_skips_sent_batches(mongo, monkeypatch):
    calls = []

    async def send(recipients, message, key):
        calls.append((recipients, key))
        if len(calls) == 2:
            raise httpx.ReadTimeout("temporary failure")

    monkeypatch.setattr(admin, "multicast_line", send)

    async def scenario(database):
        employees = [
            {"_id": f"P{i}", "active": True, "line_user_id": f"U{i}"}
            for i in range(500)
        ]
        await database.employees.insert_many(employees)
        data = AnnouncementCreate(title="ประกาศ", body="ข้อความ", request_key="same-request-key-1234")
        result = await create_announcement(data, database, ACTOR)
        assert result["delivery_status"] == "failed" and result["sent_count"] == 500
        result = await deliver_announcement(database, result["id"])
        assert result["delivery_status"] == "sent" and result["sent_count"] == 501
        assert calls[1] == calls[2] and len(calls[0][0]) == 500
        await create_announcement(data, database, ACTOR)
        assert len(calls) == 3 and await database.announcements.count_documents({}) == 1

    mongo(scenario)


def test_personal_hr_credentials_and_role_enforcement(mongo):
    async def scenario(database):
        password_hash = hash_password("strong-password")
        await database.employees.update_one(
            {"_id": "E001"},
            {"$set": {"password_hash": password_hash}},
        )
        hr_employee = {
            "_id": "HR001",
            "name": "HR",
            "active": True,
            "role": "hr",
            "password_hash": password_hash,
        }
        await database.employees.insert_one(hr_employee)
        app.dependency_overrides[db] = lambda: database

        def basic(username):
            credentials = f"{username}:strong-password".encode()
            token = base64.b64encode(credentials).decode()
            return {"Authorization": "Basic " + token}

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/admin/session", headers=basic("E001"))).status_code == 403
            response = await client.get(
                "/api/admin/session",
                headers=basic("HR001"),
            )
            assert response.json() == {"id": "HR001", "role": "hr"}
            body = {
                "employee_code": "E001",
                "name": "Employee",
                "work_email": "e001@example.com",
                "role": "admin",
                "vacation": 10,
                "sick": 30,
                "personal": 5,
            }
            response = await client.patch(
                "/api/admin/employees/E001",
                json=body,
                headers=basic("HR001"),
            )
            assert response.status_code == 403
            assert (await client.get("/api/admin/audit", headers=basic("HR001"))).status_code == 403

    mongo(scenario)


def test_line_link_preview_does_not_consume_code(mongo, monkeypatch):
    monkeypatch.setattr(auth, "LINE_LOGIN_CHANNEL_ID", "test-channel")
    monkeypatch.setattr(auth, "LINE_LOGIN_CHANNEL_SECRET", "test-secret")
    monkeypatch.setattr(auth, "PUBLIC_BASE_URL", "https://example.test")

    async def scenario(database):
        code = secrets.token_urlsafe(18)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await database.employees.update_one(
            {"_id": "E001"},
            {
                "$set": {
                    "link_code_hash": core.sha256(code),
                    "link_code_expires_at": expires_at,
                }
            },
        )
        page = await auth.line_login_prompt("E001", code, database)
        assert "เชื่อมบัญชี LINE" in page.body.decode()
        link_filter = {"_id": "E001", "link_code_hash": core.sha256(code)}
        assert await database.employees.find_one(link_filter)

        redirect = await auth.line_login_start("E001", code, database)
        assert redirect.status_code == 303
        assert redirect.headers["location"].startswith("https://access.line.me/")
        assert await database.employees.find_one(link_filter) is None

        with pytest.raises(HTTPException) as error:
            await auth.line_login_start("E001", code, database)
        assert error.value.status_code == 400

    mongo(scenario)


def test_line_employee_cannot_approve_and_hr_can(mongo, monkeypatch):
    monkeypatch.setattr(admin, "push_line", AsyncMock())

    async def scenario(database):
        key, _ = await submit_leave(database, "E001", "vacation", monday(), monday(), "พักผ่อน")
        result = await handle_message(database, "U123", f"อนุมัติ {key}")
        assert "เฉพาะ HR" in result and (await database.leave_requests.find_one({"_id": key}))["status"] == "pending"
        hr_employee = {
            "_id": "HR001",
            "name": "HR",
            "active": True,
            "role": "hr",
            "line_user_id": "UHR",
        }
        await database.employees.insert_one(hr_employee)
        result = await handle_message(database, "UHR", f"อนุมัติ {key}")
        assert "บันทึกผล" in result and (await database.leave_requests.find_one({"_id": key}))["status"] == "approved"

    mongo(scenario)


def test_year_rollover_uses_entitlements_and_preserves_history(mongo):
    async def scenario(database):
        employee = await database.employees.find_one({"_id": "E001"})
        employee["balances_year"] -= 1
        employee["balances"]["vacation"] = 2
        employee["entitlements"] = {"vacation": 12, "sick": 30, "personal": 5}
        async def read(session):
            return await current_balances(database, employee, session)

        result = await core.transaction(database, read)
        assert result["vacation"] == 12
        assert (await database.employees.find_one({"_id": "E001"}))["balances_year"] == monday().year

    mongo(scenario)
