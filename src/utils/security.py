from fastapi import Header, HTTPException, Depends
from typing import Optional
from src.config import settings

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """
    FastAPI Dependency: Verifies the 'X-API-Key' header.
    This creates a "Gatekeeper" that rejects requests without the valid token.
    """
    # Allow completely open access ONLY if no key is set in env (Dev mode)
    # In Production, SOCIALAGENT_API_KEY must be set.
    if not settings.SOCIALAGENT_API_KEY:
        return True

    if x_api_key != settings.SOCIALAGENT_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header"
        )
    return True