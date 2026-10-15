import httpx


def outbound_client(*, timeout: float = 10, **options) -> httpx.AsyncClient:
    # Retry only failed connections; replaying a timed-out POST can duplicate side effects.
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=3, pool=3),
        transport=httpx.AsyncHTTPTransport(retries=2),
        **options,
    )
