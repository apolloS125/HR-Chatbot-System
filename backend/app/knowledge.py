import httpx

from .core import OPENAI_API_KEY, OPENAI_MODEL, WEAVIATE_URL


async def answer_policy(database, question: str) -> str | None:
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.post(f"{WEAVIATE_URL}/v1/graphql", json={"query": "{Get{HrPolicy(limit:1){mongoId answer}}}"})
            rows = response.json().get("data", {}).get("Get", {}).get("HrPolicy", []) if response.is_success else []
            if rows and (faq := await database.faqs.find_one({"_id": rows[0]["mongoId"], "active": True})):
                return await _llm(question, faq["answer"])
        except httpx.HTTPError: pass
    faq = await database.faqs.find_one({"active": True})
    return await _llm(question, faq["answer"]) if faq else None


async def _llm(question: str, answer: str) -> str:
    if not OPENAI_API_KEY: return answer
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json={"model": OPENAI_MODEL, "input": f"ตอบภาษาไทยจากข้อมูลนี้เท่านั้น\nคำถาม:{question}\nข้อมูล:{answer}"})
    return response.json().get("output_text", answer) if response.is_success else answer
