from fastapi import Depends, HTTPException, Request
from redis.exceptions import RedisError

from .core import cache, sha256

_LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
if count > tonumber(ARGV[1]) then return math.max(1, redis.call('TTL', KEYS[1])) end
return 0
"""

async def enforce_limit(redis, scope: str, identity: str, limit: int, seconds: int = 60):
    try:
        wait = await redis.eval(_LIMIT, 1, f"rate:{scope}:{sha256(identity)}", limit, seconds)
    except RedisError as error:
        raise HTTPException(status_code=503, detail="Rate limiter is unavailable") from error
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
            headers={"Retry-After": str(max(1, wait))},
        )

async def limit_liff_session(request: Request, redis=Depends(cache)):
    # Use the connection address; arbitrary forwarded headers are not trusted here.
    address = request.client.host if request.client else "unknown"
    await enforce_limit(redis, "liff-session", address, 10)
