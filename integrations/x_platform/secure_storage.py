"""Secure X OAuth token storage using Windows Credential Manager."""
import json
import keyring

SERVICE = "NEXUS-AI-X-OAUTH"
ACCOUNT = "primary"

def save_tokens(token):
    if not isinstance(token, dict) or not token.get("access_token"):
        raise ValueError("Valid OAuth token required")
    keyring.set_password(SERVICE, ACCOUNT, json.dumps(token))
    return True

def load_tokens():
    value = keyring.get_password(SERVICE, ACCOUNT)
    return json.loads(value) if value else None

def delete_tokens():
    try:
        keyring.delete_password(SERVICE, ACCOUNT)
        return True
    except keyring.errors.PasswordDeleteError:
        return False

def token_status():
    token = load_tokens()
    return {
        "connected": bool(token),
        "refresh_available": bool(token and token.get("refresh_token")),
        "storage": "Windows Credential Manager"
    }
import keyring

SERVICE = "NEXUS-AI-X-OAUTH"

def save_client_secret(secret):
    if not secret:
        raise ValueError("Client secret required")
    keyring.set_password(SERVICE, "client_secret", secret)
    return True

def load_client_secret():
    return keyring.get_password(SERVICE, "client_secret")
