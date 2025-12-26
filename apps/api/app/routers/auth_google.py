from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException

from packages.agent_core.tools.google_oauth import (
    OAuthConfigError,
    build_oauth_flow,
    credentials_to_dict,
    save_token,
)

router = APIRouter()


def _redirect_uri() -> str:
    return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")


def _exchange_code(code: str) -> dict[str, Any]:
    flow = build_oauth_flow(_redirect_uri())
    flow.fetch_token(code=code)
    credentials = flow.credentials
    token_data = credentials_to_dict(credentials)
    save_token(token_data)
    return token_data


@router.get("/auth/google/start")
def google_auth_start() -> dict[str, str]:
    try:
        flow = build_oauth_flow(_redirect_uri())
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
    except OAuthConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"auth_url": auth_url}


@router.get("/auth/google/callback")
def google_auth_callback(code: str | None = None) -> dict[str, str]:
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    try:
        _exchange_code(code)
    except OAuthConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "ok", "message": "OK autorizado"}


@router.post("/auth/google/finish")
def google_auth_finish(payload: dict[str, Any]) -> dict[str, str]:
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    try:
        _exchange_code(code)
    except OAuthConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "ok", "message": "OK autorizado"}