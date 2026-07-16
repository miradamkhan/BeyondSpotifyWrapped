"""FastAPI authentication helpers."""

from __future__ import annotations

import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException, status

from src.db import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Reject requests that do not present the configured API key."""
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY is not configured on the server",
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


ApiKeyDep = Annotated[None, Depends(require_api_key)]
