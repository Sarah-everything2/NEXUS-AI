"""Instagram Reels publishing through the official Meta Graph API."""
import os
import requests

def validate_remote_video_url(video_url, max_size_mb=512):
    from urllib.parse import urlparse
    import ipaddress
    import socket
    import requests

    parsed = urlparse(str(video_url))
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Video URL must use HTTPS.")

    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("Video URL resolves to a non-public address.")
    except socket.gaierror as exc:
        raise ValueError("Video host could not be resolved.") from exc

    response = requests.head(
        video_url, allow_redirects=False, timeout=15
    )
    try:
        if response.status_code not in (200, 206):
            raise ValueError("Remote video URL is not accessible.")
        content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
        if not content_type.startswith("video/"):
            raise ValueError("Remote resource is not identified as a video.")
        length = response.headers.get("Content-Length")
        if length and int(length) > max_size_mb * 1024 * 1024:
            raise ValueError("Remote video exceeds the configured size limit.")
        return {"valid": True, "content_type": content_type}
    finally:
        response.close()


def _settings():
    token = os.getenv("NEXUS_INSTAGRAM_ACCESS_TOKEN")
    account = os.getenv("NEXUS_INSTAGRAM_ACCOUNT_ID")
    version = os.getenv("NEXUS_META_GRAPH_VERSION", "v22.0")
    if not token or not account:
        raise RuntimeError("Configure NEXUS_INSTAGRAM_ACCESS_TOKEN and NEXUS_INSTAGRAM_ACCOUNT_ID.")
    return token, account, version

def _request(method, url, **kwargs):
    response = requests.request(method, url, timeout=60, **kwargs)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data["error"].get("message", "Meta API error"))
    return data

def verify_account():
    token, account, version = _settings()
    return _request("GET", f"https://graph.facebook.com/{version}/{account}",
                    params={"fields": "id,username", "access_token": token})

def create_reel(video_url, caption="", consent=False):
    validate_remote_video_url(video_url)
    if consent is not True:
        raise PermissionError("Explicit consent=True is required for each Instagram publication.")
    if not isinstance(video_url, str) or not video_url.startswith("https://"):
        raise ValueError("Instagram requires a publicly reachable HTTPS video URL.")
    token, account, version = _settings()
    return _request("POST", f"https://graph.facebook.com/{version}/{account}/media",
                    data={"media_type": "REELS", "video_url": video_url,
                          "caption": caption, "access_token": token})

def reel_status(container_id):
    if not container_id:
        raise ValueError("container_id is required")
    token, account, version = _settings()
    return _request("GET", f"https://graph.facebook.com/{version}/{container_id}",
                    params={"fields": "status_code,status", "access_token": token})

def publish_reel(container_id, consent=False):
    if consent is not True:
        raise PermissionError("Explicit consent=True is required to publish the Reel.")
    status = reel_status(container_id)
    if status.get("status_code") != "FINISHED":
        raise RuntimeError(f"Reel is not ready to publish: {status}")
    token, account, version = _settings()
    return _request("POST", f"https://graph.facebook.com/{version}/{account}/media_publish",
                    data={"creation_id": container_id, "access_token": token})
