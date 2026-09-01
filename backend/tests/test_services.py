import asyncio
import json
from datetime import date

import pytest
import httpx
from fastapi import HTTPException

from app.admin import decide_leave, document_view
from app.core import issue_liff_token, read_liff_token
from app.leaves import submit_leave
from app.schemas import LeaveDecision
from app.tools import call_tool, register_tool, tool_definitions
from app.vector_store import VECTOR_SIZE, embed_text, ensure_policy_index, search_policy


def test_liff_token_is_signed_and_rejects_tampering():
    token = issue_liff_token("U123")
    assert read_liff_token(token) == "U123"
    assert read_liff_token(token + "x") is None


def test_tool_registry_only_calls_registered_tools():
    async def handler(arguments): return {"employee": arguments["employee"]}
    register_tool("directory_lookup", handler)
    assert any(item["name"] == "directory_lookup" for item in tool_definitions())
    assert asyncio.run(call_tool("directory_lookup", {"employee": "E001"})) == {"employee": "E001"}
    with pytest.raises(ValueError): asyncio.run(call_tool("unknown", {}))


def test_embedding_is_stable_and_normalized():
    first = embed_text("นโยบายวันลา")
    assert len(first) == VECTOR_SIZE
    assert first == embed_text("นโยบายวันลา")
    assert first != embed_text("เวลาทำงาน")
    assert sum(value * value for value in first) == pytest.approx(1)


def test_weaviate_index_and_near_vector_query():
    requests = []
    def handler(request):
        requests.append(request)
        if request.method == "GET": return httpx.Response(404)
        if request.url.path == "/v1/graphql": return httpx.Response(200, json={"data": {"Get": {"HrPolicy": [{"mongoId": "work-hours"}]}}})
        return httpx.Response(200)
    async def exercise():
        async with httpx.AsyncClient(base_url="http://weaviate", transport=httpx.MockTransport(handler)) as client:
            await ensure_policy_index(client, [{"_id": "work-hours", "keyword": "เวลาทำงาน", "question": "ทำงานกี่โมง", "answer": "09:00"}])
            return await search_policy(client, "เวลาทำงาน")
    assert asyncio.run(exercise()) == "work-hours"
    object_request = next(request for request in requests if request.url.path == "/v1/objects")
    assert len(json.loads(object_request.content)["vector"]) == VECTOR_SIZE
    assert b"nearVector" in requests[-1].content


def test_public_document_does_not_leak_mongo_id():
    assert document_view({"_id": "AN-1", "title": "ข่าว"}) == {"id": "AN-1", "title": "ข่าว"}


def test_liff_leave_omits_null_source_event_id():
    class Employees:
        async def find_one(self, _): return {"balances": {"vacation": 10}}
    class Requests:
        document = None
        async def insert_one(self, document): self.document = document
    class Database:
        employees = Employees()
        leave_requests = Requests()
    database = Database()
    request_id, days = asyncio.run(submit_leave(database, "E001", "vacation", date(2026, 9, 1), date(2026, 9, 1), "พักผ่อน"))
    assert request_id.startswith("LR-") and days == 1
    assert "source_event_id" not in database.leave_requests.document


def test_leave_decision_claim_prevents_second_approval():
    class Result:
        modified_count = 1
    class Requests:
        status = "pending"
        async def find_one_and_update(self, query, update, **_):
            if query.get("status") != self.status: return None
            self.status = update["$set"]["status"]
            return {"_id": "LR-1", "employee_code": "E001", "leave_type": "vacation", "days": 1, "status": self.status}
        async def update_one(self, query, update):
            if query.get("status") == self.status: self.status = update["$set"]["status"]
            return Result()
    class Employees:
        calls = 0
        async def update_one(self, *_): self.calls += 1; return Result()
    class Redis:
        async def delete(self, *_): pass
    class Database:
        leave_requests = Requests()
        employees = Employees()
    database = Database()
    decision = LeaveDecision(decision="approved", decided_by="HR")
    assert asyncio.run(decide_leave("LR-1", decision, database, Redis())) == {"ok": True}
    with pytest.raises(HTTPException): asyncio.run(decide_leave("LR-1", decision, database, Redis()))
    assert database.employees.calls == 1
