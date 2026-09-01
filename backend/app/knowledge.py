import asyncpg
import httpx

from .core import OPENAI_API_KEY, OPENAI_MODEL


async def answer_policy(pool: asyncpg.Pool, question: str) -> str | None:
    source = await pool.fetchrow(
        "SELECT question, answer FROM faqs WHERE active AND $1 ILIKE '%' || keyword || '%' ORDER BY length(keyword) DESC LIMIT 1",
        question,
    )
    if not source:
        return None
    if not OPENAI_API_KEY:
        return source["answer"]
    prompt = f"ตอบคำถาม HR เป็นภาษาไทย โดยใช้เฉพาะข้อมูลนี้ หากข้อมูลไม่พอให้ตอบว่าไม่พบข้อมูล\n\nคำถาม: {question}\nข้อมูลนโยบาย: {source['question']}\n{source['answer']}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": OPENAI_MODEL, "input": prompt},
        )
    if response.is_error:
        return source["answer"]
    return response.json().get("output_text") or source["answer"]
