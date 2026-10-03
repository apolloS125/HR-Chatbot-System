import asyncio
import json
from datetime import date

import httpx
import pytest
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
    async def handler(arguments):
        return {"employee": arguments["employee"]}

    register_tool("directory_lookup", handler)
    assert any(item["name"] == "directory_lookup" for item in tool_definitions())
    result = asyncio.run(call_tool("directory_lookup", {"employee": "E001"}))
    assert result == {"employee": "E001"}

    with pytest.raises(ValueError):
        asyncio.run(call_tool("unknown", {}))


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
        if request.method == "GET":
            return httpx.Response(404)
        if request.url.path == "/v1/graphql":
            return httpx.Response(
                200,
                json={"data": {"Get": {"HrPolicy": [{"mongoId": "work-hours"}]}}},
            )
        if request.url.path == "/v1/batch/objects":
            return httpx.Response(200, json=[{"result": {"status": "SUCCESS"}}])
        return httpx.Response(200)

    async def exercise():
        async with httpx.AsyncClient(
            base_url="http://weaviate",
            transport=httpx.MockTransport(handler),
        ) as client:
            policy = {
                "_id": "work-hours",
                "keyword": "เวลาทำงาน",
                "question": "ทำงานกี่โมง",
                "answer": "09:00",
            }
            await ensure_policy_index(client, [policy])
            return await search_policy(client, "เวลาทำงาน")

    assert asyncio.run(exercise()) == ["work-hours"]
    object_request = next(request for request in requests if request.url.path == "/v1/batch/objects")
    indexed_object = json.loads(object_request.content)["objects"][0]
    assert len(indexed_object["vector"]) == VECTOR_SIZE
    assert b"nearVector" in requests[-1].content


def test_public_document_does_not_leak_mongo_id():
    assert document_view({"_id": "AN-1", "title": "ข่าว"}) == {"id": "AN-1", "title": "ข่าว"}
