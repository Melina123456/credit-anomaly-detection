import os

from fastapi import Header, HTTPException


def require_api_key(x_api_key: str = Header(default=None)) -> None:
    """FastAPI dependency gating internal endpoints (the /debug/* routes and
    POST /train) behind a shared API key, passed as the X-API-Key header.

    Fails closed: if ADMIN_API_KEY isn't configured at all, every protected
    route becomes unreachable (503) rather than silently open to anyone —
    a misconfiguration should never be indistinguishable from "no auth
    required."
    """
    expected = os.getenv("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY is not configured on the server")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key header")
