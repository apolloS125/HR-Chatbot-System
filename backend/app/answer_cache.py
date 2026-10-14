import hashlib
import json
import logging
import re
import time

import httpx
from redis.exceptions import RedisError

from . import vector_store
from .privacy import mask_text


def cache_key(model: str, context: str) -> str:
    # The source content and model are part of the key, so edits cannot reuse old answers.
    digest = hashlib.sha256(f"{model}:{context}".encode()).hexdigest()
    return f"policy-answers:v1:{digest}"


def question_constraints(question: str) -> list[str]:
    return sorted(re.findall(r"\d+(?:\.\d+)?|ไม่|ยกเว้น|ห้าม|not|except|without", question.lower()))


async def lookup_answer(redis, key: str, question: str):
    if redis is None:
        return None, None
    normalized = " ".join(mask_text(question).lower().split())
    vector = None
    try:
        entries = [json.loads(value) for value in await redis.lrange(key, 0, 19)]
        entries = [entry for entry in entries if time.time() - entry.get("created_at", 0) < 300]
        for entry in entries:
            if entry["question"] == normalized:
                return entry["answer"], None
        if vector_store.OPENAI_API_KEY:
            vector = (await vector_store.policy_vectors([normalized]))[0]
            for entry in entries:
                cached_vector = entry.get("vector")
                if not cached_vector or len(cached_vector) != len(vector):
                    continue
                if question_constraints(normalized) != question_constraints(entry["question"]):
                    continue
                similarity = sum(a * b for a, b in zip(vector, cached_vector))
                if similarity >= 0.99:
                    return entry["answer"], vector
    except (RedisError, httpx.HTTPError, ValueError, KeyError, TypeError):
        logging.getLogger(__name__).warning("Policy answer cache unavailable")
    return None, vector


async def store_answer(redis, key: str, question: str, answer: str, vector):
    if redis is None:
        return
    entry = {
        "question": " ".join(mask_text(question).lower().split()),
        "answer": answer,
        "vector": vector,
        "created_at": time.time(),
    }
    try:
        async with redis.pipeline(transaction=True) as pipeline:
            pipeline.lpush(key, json.dumps(entry, ensure_ascii=False))
            pipeline.ltrim(key, 0, 19)
            pipeline.expire(key, 300)
            await pipeline.execute()
    except RedisError:
        logging.getLogger(__name__).warning("Could not cache policy answer")
