"""TikTok OAuth 2.0 with PKCE and state validation."""
import os, secrets, hashlib, urllib.parse, time, requests, base64
from pathlib import Path
from dotenv import load_dotenv
from integrations.tiktok.secure_storage import save_tokens, load_tokens

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

class TikTokOAuth:
    def __init__(self):
        self.client_key = os.getenv("NEXUS_TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("NEXUS_TIKTOK_CLIENT_SECRET")
        self.redirect_uri = os.getenv("NEXUS_TIKTOK_REDIRECT_URI")
        if not all((self.client_key, self.client_secret, self.redirect_uri)):
            raise RuntimeError("Configure NEXUS_TIKTOK_CLIENT_KEY, NEXUS_TIKTOK_CLIENT_SECRET and NEXUS_TIKTOK_REDIRECT_URI in .env.")
        self.state = None
        self.verifier = None

    def authorization_url(self, scopes=None):
        self.state = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode("ascii").rstrip("=")
        params = {
            "client_key": self.client_key,
            "response_type": "code",
            "scope": ",".join(scopes or ["user.info.basic", "video.list", "video.publish"]),
            "redirect_uri": self.redirect_uri,
            "state": self.state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return AUTH_URL + "?" + urllib.parse.urlencode(params)

    def exchange_code(self, code, state):
        if not self.state or not secrets.compare_digest(str(state), self.state):
            raise PermissionError("TikTok OAuth state validation failed.")
        if not isinstance(code, str) or not code.strip():
            raise ValueError("TikTok authorization code is required.")
        response = requests.post(TOKEN_URL, data={
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code_verifier": self.verifier,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        response.raise_for_status()
        result = response.json()
        data = result
        if result.get("error") not in (None, "ok") or not data.get("access_token"):
            raise RuntimeError("TikTok OAuth token exchange failed: " + str(result.get("error_description") or result.get("error") or "Invalid token response"))
        if not data.get("open_id"):
            raise RuntimeError("TikTok token response did not include an account ID.")
        data["expires_at"] = time.time() + int(data.get("expires_in", 7200))
        data["refresh_expires_at"] = time.time() + int(data.get("refresh_expires_in", 0))
        save_tokens(data)
        self.state = self.verifier = None
        return {"connected": True, "open_id": data.get("open_id"), "storage": "Windows Credential Manager"}

    def refresh(self):
        token = load_tokens()
        if not token or not token.get("refresh_token"):
            raise RuntimeError("TikTok is not connected or refresh token is missing.")
        response = requests.post(TOKEN_URL, data={
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
        response.raise_for_status()
        result = response.json()
        data = {**token, **result}
        if result.get("error") not in (None, "ok") or not data.get("access_token"):
            raise RuntimeError("TikTok token refresh failed: " + str(result.get("error_description") or result.get("error") or "Invalid token response"))
        data["expires_at"] = time.time() + int(result.get("expires_in", 7200))
        data["refresh_expires_at"] = time.time() + int(data.get("refresh_expires_in", 0))
        save_tokens(data)
        return True
