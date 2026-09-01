import httpx

from .core import OPENAI_API_KEY, OPENAI_MODEL, WEAVIATE_URL
from .vector_store import search_policy


async def answer_policy(database, question: str) -> str | None:
    async with httpx.AsyncClient(base_url=WEAVIATE_URL, timeout=5) as client:
        try:
            mongo_id = await search_policy(client, question)
            if mongo_id and (faq := await database.faqs.find_one({"_id": mongo_id, "active": True})):
                return await _llm(question, faq["answer"])
        except httpx.HTTPError: pass
    candidates = [faq async for faq in database.faqs.find({"active": True})]
    faq = max((faq for faq in candidates if faq.get("keyword") and faq["keyword"].lower() in question.lower()), key=lambda value: len(value["keyword"]), default=None)
    return await _llm(question, faq["answer"]) if faq else None


async def _llm(question: str, answer: str) -> str:
    if not OPENAI_API_KEY: return answer
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json={"model": OPENAI_MODEL, "input": f"ตอบภาษาไทยจากข้อมูลนี้เท่านั้น\nคำถาม:{question}\nข้อมูล:{answer}"})
    return response.json().get("output_text", answer) if response.is_success else answer
