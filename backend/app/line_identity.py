import time

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from .http_client import outbound_client
from .schemas import LineIdentity


async def verify_line_identity(id_token: str, channel_id: str, nonce: str | None = None) -> str:
    if not channel_id:
        raise HTTPException(status_code=503, detail="LINE Login is not configured")
    data = {"id_token": id_token, "client_id": channel_id}
    if nonce is not None:
        data["nonce"] = nonce
    try:
        async with outbound_client() as client:
            response = await client.post("https://api.line.me/oauth2/v2.1/verify", data=data)
            if response.status_code >= 500 or response.status_code == 429:
                raise HTTPException(status_code=503, detail="LINE verification is unavailable")
            if not response.is_success:
                raise HTTPException(status_code=401, detail="invalid LINE ID token")
            identity = LineIdentity.model_validate(response.json())
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="LINE verification is unavailable") from error
    except (ValidationError, ValueError, TypeError) as error:
        raise HTTPException(status_code=401, detail="invalid LINE ID token") from error
    if (
        identity.iss != "https://access.line.me"
        or identity.aud != channel_id
        or identity.exp <= time.time()
        or (nonce is not None and identity.nonce != nonce)
    ):
        raise HTTPException(status_code=401, detail="invalid LINE ID token")
    return identity.sub
