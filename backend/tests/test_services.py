import asyncio
import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from app import core, observability, vector_store
from app.admin import document_view
from app.core import issue_liff_token, read_liff_token
from app.schemas import LiffSessionCreate
from app.tools import call_tool, register_tool, tool_definitions
from app.vector_store import VECTOR_SIZE, embed_text, ensure_policy_index, search_policy


def test_liff_token_is_signed_and_rejects_tampering():
    token = issue_liff_token("U123")
    assert read_liff_token(token) == "U123"
    assert read_liff_token(token + "x") is None
    assert read_liff_token("é" * 50) is None
    assert read_liff_token("x" * 2049) is None


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


def test_weaviate_index_and_near_vector_query(monkeypatch):
    monkeypatch.setattr(vector_store, "WEAVIATE_API_KEY", "test-weaviate-key")
    requests = []

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-weaviate-key"
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
    object_request = next(
        request for request in requests if request.url.path == "/v1/batch/objects"
    )
    indexed_object = json.loads(object_request.content)["objects"][0]
    assert len(indexed_object["vector"]) == VECTOR_SIZE
    assert b"nearVector" in requests[-1].content


def test_public_document_does_not_leak_mongo_id():
    assert document_view({"_id": "AN-1", "title": "ข่าว"}) == {"id": "AN-1", "title": "ข่าว"}


def test_startup_rejects_weak_and_shared_secrets(monkeypatch):
    monkeypatch.setattr(core, "WEAVIATE_API_KEY", "a-strong-weaviate-api-key-for-testing")
    monkeypatch.setattr(core, "ADMIN_API_KEY", "a-strong-admin-secret-value-for-testing")
    monkeypatch.setattr(core, "LIFF_SESSION_SECRET", "independent-liff-signing-value-for-testing")
    monkeypatch.setattr(core, "HR_PASSWORD", "a-strong-bootstrap-password")
    core.validate_secrets()
    monkeypatch.setattr(core, "LIFF_SESSION_SECRET", core.ADMIN_API_KEY)
    with pytest.raises(RuntimeError, match="independent"):
        core.validate_secrets()
    monkeypatch.setattr(core, "LIFF_SESSION_SECRET", "weak")
    with pytest.raises(RuntimeError, match="LIFF_SESSION_SECRET"):
        core.validate_secrets()


def test_liff_id_token_has_a_length_limit():
    with pytest.raises(ValidationError):
        LiffSessionCreate(id_token="x" * 8193)


def test_langfuse_masks_input_output_and_tracks_usage(monkeypatch):
    observation = Mock()
    client = Mock()
    client.start_observation.return_value = observation
    monkeypatch.setattr(observability, "trace_client", lambda: client)
    result = observability.start_generation("model", {"question": "employee@example.com"})
    assert result is observation
    assert "employee@example.com" not in str(client.start_observation.call_args)
    observability.finish_generation(
        result,
        "Mr. John Smith",
        {
            "input_tokens": 10,
            "input_token_details": {"cache_read": 5},
        },
    )
    assert "John Smith" not in str(observation.update.call_args)
    assert observation.update.call_args.kwargs["usage_details"] == {"input_tokens": 10}
    observation.end.assert_called_once()


def test_langfuse_failure_does_not_break_answers(monkeypatch):
    def fail():
        raise RuntimeError("telemetry unavailable")

    monkeypatch.setattr(observability, "trace_client", fail)
    assert observability.start_generation("model", {}) is None
