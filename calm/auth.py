from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import (CAL_SCOPES, GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH,
                     ensure_600)


def import_oauth_client_from_json_string(raw: str) -> None:
    data = json.loads(raw)
    if not any(k in data for k in ("installed", "web")):
        raise ValueError("Invalid OAuth client JSON (need 'installed' or 'web').")
    GOOGLE_CREDENTIALS_PATH.write_text(json.dumps(data), encoding="utf-8")
    ensure_600(GOOGLE_CREDENTIALS_PATH)

def import_oauth_client_from_path(path: str) -> None:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"credentials.json not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not any(k in data for k in ("installed", "web")):
        raise ValueError("Invalid OAuth client JSON (need 'installed' or 'web').")
    GOOGLE_CREDENTIALS_PATH.write_text(json.dumps(data), encoding="utf-8")
    ensure_600(GOOGLE_CREDENTIALS_PATH)

def get_calendar_credentials() -> Credentials:
    creds: Optional[Credentials] = None
    if GOOGLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), CAL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            GOOGLE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            ensure_600(GOOGLE_TOKEN_PATH)
        else:
            if not GOOGLE_CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing OAuth client at {GOOGLE_CREDENTIALS_PATH}.\n"
                    "Run: calm configure oauth"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_PATH), CAL_SCOPES)
            creds = flow.run_local_server(port=0)  # 開瀏覽器授權
            GOOGLE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            ensure_600(GOOGLE_TOKEN_PATH)
    return creds

def reset_tokens() -> None:
    if GOOGLE_TOKEN_PATH.exists():
        GOOGLE_TOKEN_PATH.unlink()