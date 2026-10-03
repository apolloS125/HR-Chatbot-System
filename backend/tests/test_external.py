import asyncio
import io
import json
from types import SimpleNamespace

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import intent, knowledge, line_client
from app.knowledge import document_chunks
from app.privacy import mask_text


def mock_http(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **options: original(transport=httpx.MockTransport(handler), **options))


def test_llm_reads_response_message_content_and_masks_identifiers(monkeypatch):
    monkeypatch.setattr(knowledge, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(knowledge, "OPENAI_BASE_URL", "https://ai.psu.blue/v1")
    monkeypatch.setattr(knowledge, "OPENAI_MODEL", "openai/gpt-6-luna")
    def handler(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://ai.psu.blue/v1/chat/completions"
        assert body["model"] == "openai/gpt-6-luna"
        assert body["stream"] is False
        assert body["max_completion_tokens"] == 800
        assert "employee@example.com" not in body["messages"][1]["content"]
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0, "model": "openai/gpt-6-luna", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "คำตอบจากนโยบาย [1]"}}]})
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await knowledge._llm("employee@example.com ถามวันลา", "[1] วันลา 10 วัน", client)
    assert asyncio.run(call()) == "คำตอบจากนโยบาย [1]"


def test_llm_outage_falls_back_to_source_text(monkeypatch):
    monkeypatch.setattr(knowledge, "OPENAI_API_KEY", "test-key")
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
            return await knowledge._llm("วันลา", "วันลา 10 วัน", client)
    assert asyncio.run(call()) == "วันลา 10 วัน"


def test_policy_retrieval_excludes_archived_and_cites_three_sources(monkeypatch):
    policies = [
        {"_id": "archived", "question": "old", "answer": "old", "source": "old.pdf", "active": False},
        *({"_id": str(i), "question": f"q{i}", "answer": f"a{i}", "source": f"p{i}.pdf", "active": True} for i in range(1, 5)),
    ]
    class Faqs:
        def find(self, query):
            assert query == {"active": True}
            async def results():
                for item in policies:
                    if item["active"]:
                        yield item
            return results()
    async def search(*_): return ["archived", "1", "2", "3", "4"]
    async def answer(_, context):
        assert context == "[1] a1\n\n[2] a2\n\n[3] a3"
        return "สรุป [1] [2] [3]"
    monkeypatch.setattr(knowledge, "search_policy", search)
    monkeypatch.setattr(knowledge, "_llm", answer)
    result = asyncio.run(knowledge.answer_policy(SimpleNamespace(faqs=Faqs()), "unknown"))
    assert result == "สรุป [1] [2] [3]\n\nแหล่งข้อมูล:\n[1] p1.pdf\n[2] p2.pdf\n[3] p3.pdf"


def test_policy_without_evidence_does_not_call_llm(monkeypatch):
    class Faqs:
        def find(self, query):
            async def results():
                if False:
                    yield query
            return results()
    async def search(*_): return []
    async def fail(*_): raise AssertionError("LLM must not be called")
    monkeypatch.setattr(knowledge, "search_policy", search)
    monkeypatch.setattr(knowledge, "_llm", fail)
    assert asyncio.run(knowledge.answer_policy(SimpleNamespace(faqs=Faqs()), "unknown")) is None


@pytest.mark.parametrize("choice,confidence,expected", [("balance", 0.95, "balance"), ("balance", 0.2, None), ("approve", 1, None), ("balance", 2, None)])
def test_jev_uses_only_allowed_confident_intents(monkeypatch, choice, confidence, expected):
    monkeypatch.setattr(intent, "TYPESAFE_API_KEY", "test-key")
    def handler(request):
        body = json.loads(request.content)
        assert body["questions"]["intent"]["type"] == "choice"
        assert "employee@example.com" not in body["state"]
        assert "approve" not in body["questions"]["intent"]["criteria"]
        return httpx.Response(200, json={"answers": {"intent": {"type": "choice", "choice": choice, "confidence": confidence}}})
    mock_http(monkeypatch, handler)
    assert asyncio.run(intent.classify_intent("employee@example.com เหลือวันลากี่วัน")) == expected


def test_jev_timeout_falls_back(monkeypatch):
    monkeypatch.setattr(intent, "TYPESAFE_API_KEY", "test-key")
    def handler(request): raise httpx.ReadTimeout("timeout", request=request)
    mock_http(monkeypatch, handler)
    assert asyncio.run(intent.classify_intent("วันลา")) is None


def test_line_accepts_already_accepted_retry_key(monkeypatch):
    monkeypatch.setattr(line_client, "LINE_CHANNEL_ACCESS_TOKEN", "test-token")
    def handler(request):
        assert request.headers["X-Line-Retry-Key"] == "persistent-key"
        return httpx.Response(409, headers={"x-line-accepted-request-id": "accepted-1"})
    mock_http(monkeypatch, handler)
    asyncio.run(line_client.multicast_line(["U123"], {"type": "text", "text": "ประกาศ"}, "persistent-key"))


def test_document_chunks_keep_overlapping_text_and_page_sources():
    text = "ข้อความนโยบายบริษัท " * 100
    chunks = document_chunks("policy.txt", text.encode())
    assert len(chunks) > 1 and all(page == 1 for page, _ in chunks)
    assert chunks[0][1] in text and chunks[-1][1] in text
    writer = PdfWriter()
    page = writer.add_blank_page(400, 400)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 350 Td (Annual leave is ten days.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    assert "Annual leave" in document_chunks("policy.pdf", output.getvalue())[0][1]


@pytest.mark.parametrize("filename,content", [("fake.pdf", b"not a pdf"), ("policy.exe", b"text"), ("empty.txt", b" ")])
def test_invalid_documents_are_rejected(filename, content):
    with pytest.raises(ValueError): document_chunks(filename, content)


def test_common_identifiers_are_masked():
    text = mask_text("E001 employee@example.com 081-234-5678 1234567890123")
    assert not any(value in text for value in ["E001", "employee@example.com", "081-234-5678", "1234567890123"])
