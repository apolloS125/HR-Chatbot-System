import hashlib
import json
import math
import os
import uuid

import httpx

from .privacy import mask_text

VECTOR_SIZE = 128
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
POLICY_CLASS = "HrPolicySemantic" if OPENAI_API_KEY else "HrPolicy"


def embed_text(text: str) -> list[float]:
    normalized = " ".join(text.lower().split())
    features = [normalized[index:index + 3] for index in range(max(1, len(normalized) - 2))]
    vector = [0.0] * VECTOR_SIZE
    for feature in features:
        digest = hashlib.blake2b(feature.encode(), digest_size=4).digest()
        vector[int.from_bytes(digest[:2]) % VECTOR_SIZE] += 1 if digest[2] & 1 else -1
    length = math.sqrt(sum(value * value for value in vector)) or 1
    return [value / length for value in vector]


async def ensure_policy_index(client: httpx.AsyncClient, policies: list[dict]) -> None:
    schema = await client.get(f"/v1/schema/{POLICY_CLASS}")
    if schema.status_code == 404:
        created = await client.post("/v1/schema", json={"class": POLICY_CLASS, "vectorizer": "none", "properties": [{"name": "mongoId", "dataType": ["text"]}]})
        created.raise_for_status()
    elif schema.is_error:
        schema.raise_for_status()
    for offset in range(0, len(policies), 32):
        batch = policies[offset:offset + 32]
        texts = [f"{policy.get('keyword', '')} {policy.get('question', '')} {policy['answer']}" for policy in batch]
        vectors = await policy_vectors(texts)
        objects = [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"hr-policy:{POLICY_CLASS}:{policy['_id']}")), "class": POLICY_CLASS, "properties": {"mongoId": policy["_id"]}, "vector": vector} for policy, vector in zip(batch, vectors)]
        response = await client.post("/v1/batch/objects", json={"objects": objects})
        response.raise_for_status()
        if any(item.get("result", {}).get("errors") for item in response.json()):
            raise ValueError("policy batch indexing failed")


async def policy_vectors(texts: list[str]) -> list[list[float]]:
    if not OPENAI_API_KEY:
        return [embed_text(text) for text in texts]
    # ponytail: index the first 1500 characters per FAQ; split longer policies into document chunks.
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post("https://api.openai.com/v1/embeddings", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json={"model": "text-embedding-3-small", "input": [mask_text(text)[:1500] for text in texts], "dimensions": VECTOR_SIZE})
        response.raise_for_status()
        vectors = [item["embedding"] for item in sorted(response.json()["data"], key=lambda item: item["index"])]
        if len(vectors) != len(texts) or any(len(vector) != VECTOR_SIZE for vector in vectors):
            raise ValueError("invalid embedding response")
        return vectors


async def search_policy(client: httpx.AsyncClient, question: str) -> list[str]:
    vector = json.dumps((await policy_vectors([question]))[0], separators=(",", ":"))
    query = "{Get{" + POLICY_CLASS + "(nearVector:{vector:" + vector + ",distance:0.75},limit:3){mongoId _additional{distance}}}}"
    response = await client.post("/v1/graphql", json={"query": query})
    response.raise_for_status()
    rows = response.json().get("data", {}).get("Get", {}).get(POLICY_CLASS, [])
    return list(dict.fromkeys(row["mongoId"] for row in rows))
