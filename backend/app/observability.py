import logging
import os
from functools import lru_cache

from langfuse import Langfuse

from .privacy import mask_text


def mask_trace_data(data, **_):
    if isinstance(data, str):
        return mask_text(data)
    if isinstance(data, dict):
        return {key: mask_trace_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [mask_trace_data(value) for value in data]
    return data


@lru_cache(maxsize=1)
def trace_client():
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not public_key or not secret_key:
        return None
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
        timeout=2,
        mask=mask_trace_data,
    )


def start_generation(model, inputs):
    try:
        client = trace_client()
        if client:
            return client.start_observation(
                name="hr-policy-answer",
                as_type="generation",
                model=model,
                input=mask_trace_data(inputs),
            )
    except Exception:
        logging.getLogger(__name__).warning("Langfuse tracing unavailable")
    return None


def finish_generation(observation, output, usage=None):
    if observation is None:
        return
    try:
        token_counts = {
            name: count for name, count in (usage or {}).items() if isinstance(count, int)
        }
        observation.update(output=mask_text(output), usage_details=token_counts)
        observation.end()
    except Exception:
        logging.getLogger(__name__).warning("Could not finish Langfuse generation")


def shutdown_tracing():
    try:
        client = trace_client()
        if client:
            client.shutdown()
    except Exception:
        logging.getLogger(__name__).warning("Could not flush Langfuse traces")
