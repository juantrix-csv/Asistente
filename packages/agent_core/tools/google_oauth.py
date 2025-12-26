from __future__ import annotations

from datetime import timezone
import json
import os
from typing import Any

from cryptography.fernet import Fernet
from google_auth_oauthlib.flow import Flow

from packages.db.database import SessionLocal
from packages.db.models import Secret

GOOGLE_TOKEN_NAME = "google_oauth_token"
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class OAuthConfigError(RuntimeError):
    pass


def _get_secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if not key:
        raise OAuthConfigError("SECRET_KEY missing")
    return key


def _get_fernet() -> Fernet:
    return Fernet(_get_secret_key().encode())


def _build_client_config(redirect_uri: str) -> dict[str, Any]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise OAuthConfigError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET missing")

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }


def build_oauth_flow(redirect_uri: str) -> Flow:
    config = _build_client_config(redirect_uri)
    return Flow.from_client_config(config, scopes=GOOGLE_SCOPES, redirect_uri=redirect_uri)


def credentials_to_dict(credentials) -> dict[str, Any]:
    data: dict[str, Any] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    if credentials.expiry:
        expiry = credentials.expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        data["expiry"] = expiry.isoformat()
    return data


def save_token(token_data: dict[str, Any], name: str = GOOGLE_TOKEN_NAME) -> None:
    payload = json.dumps(token_data, separators=(",", ":")).encode()
    ciphertext = _get_fernet().encrypt(payload).decode()

    with SessionLocal() as session:
        secret = session.query(Secret).filter_by(name=name).one_or_none()
        if secret is None:
            secret = Secret(name=name, ciphertext=ciphertext)
            session.add(secret)
        else:
            secret.ciphertext = ciphertext
        session.commit()


def load_token(name: str = GOOGLE_TOKEN_NAME) -> dict[str, Any] | None:
    with SessionLocal() as session:
        secret = session.query(Secret).filter_by(name=name).one_or_none()
        if secret is None:
            return None
        ciphertext = secret.ciphertext.encode()

    payload = _get_fernet().decrypt(ciphertext).decode()
    return json.loads(payload)


def has_token(name: str = GOOGLE_TOKEN_NAME) -> bool:
    with SessionLocal() as session:
        return session.query(Secret).filter_by(name=name).count() > 0


def token_metadata(name: str = GOOGLE_TOKEN_NAME) -> dict[str, Any] | None:
    with SessionLocal() as session:
        secret = session.query(Secret).filter_by(name=name).one_or_none()
        if secret is None:
            return None
        return {"name": secret.name}
