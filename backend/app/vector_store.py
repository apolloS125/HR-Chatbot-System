import hashlib
import json
import math
import uuid

import httpx

VECTOR_SIZE = 128


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
    schema = await client.get("/v1/schema/HrPolicy")
    if schema.status_code == 404:
        created = await client.post("/v1/schema", json={"class": "HrPolicy", "vectorizer": "none", "properties": [{"name": "mongoId", "dataType": ["text"]}, {"name": "answer", "dataType": ["text"]}]})
        created.raise_for_status()
    elif schema.is_error:
        schema.raise_for_status()
    for policy in policies:
        object_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"hr-policy:{policy['_id']}"))
        body = {"class": "HrPolicy", "properties": {"mongoId": policy["_id"], "answer": policy["answer"]}, "vector": embed_text(f"{policy.get('keyword', '')} {policy.get('question', '')} {policy['answer']}")}
        exists = await client.get(f"/v1/objects/{object_id}")
        if exists.status_code not in {200, 404}: exists.raise_for_status()
        response = await client.post("/v1/objects", json={"id": object_id, **body}) if exists.status_code == 404 else await client.put(f"/v1/objects/{object_id}", json=body)
        response.raise_for_status()


async def search_policy(client: httpx.AsyncClient, question: str) -> str | None:
    vector = json.dumps(embed_text(question), separators=(",", ":"))
    query = "{Get{HrPolicy(nearVector:{vector:" + vector + ",distance:0.75},limit:1){mongoId _additional{distance}}}}"
    response = await client.post("/v1/graphql", json={"query": query})
    response.raise_for_status()
    rows = response.json().get("data", {}).get("Get", {}).get("HrPolicy", [])
    return rows[0]["mongoId"] if rows else None
