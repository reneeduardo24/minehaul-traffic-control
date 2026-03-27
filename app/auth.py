from __future__ import annotations

from fastapi import Header, HTTPException

from .service_config import API_TOKEN


async def require_token(x_api_token: str = Header(default="")) -> None:
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")
