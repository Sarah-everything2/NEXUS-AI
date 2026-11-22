"""Official YouTube OAuth 2.0 authentication for NEXUS AI."""
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from integrations.youtube.secure_storage import load_tokens, save_tokens

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_credentials():
    token = load_tokens()
    if not token:
        raise RuntimeError("YouTube is not connected. Run connect_youtube() first.")

    credentials = Credentials.from_authorized_user_info(token, SCOPES)

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_tokens({
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        })

    if not credentials.valid:
        raise RuntimeError("YouTube credentials are invalid. Reconnect the account.")

    return credentials


def connect_youtube():
    secrets_path = os.getenv("NEXUS_YOUTUBE_CLIENT_SECRETS")

    if not secrets_path:
        raise RuntimeError(
            "Set NEXUS_YOUTUBE_CLIENT_SECRETS to your local Google OAuth "
            "Desktop App JSON file."
        )

    path = Path(secrets_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError("Google OAuth client JSON file was not found.")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(path),
        SCOPES,
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )

    save_tokens({
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    })

    return {
        "connected": True,
        "storage": "Windows Credential Manager",
        "publishing_enabled": False,
    }


def get_youtube_service():
    return build("youtube", "v3", credentials=get_credentials())
