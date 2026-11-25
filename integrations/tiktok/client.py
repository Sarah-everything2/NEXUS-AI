"""NEXUS TikTok API client: authenticated read-only operations."""
import time
import requests
from integrations.tiktok.secure_storage import load_tokens
from integrations.tiktok.oauth import TikTokOAuth

BASE_URL = "https://open.tiktokapis.com"

class NexusTikTokClient:
    def __init__(self):
        self.tokens = load_tokens()
        if not self.tokens:
            raise RuntimeError("TikTok is not connected.")
        if float(self.tokens.get("expires_at", 0)) <= time.time() + 60:
            TikTokOAuth().refresh()
            self.tokens = load_tokens()
        if not self.tokens or not self.tokens.get("access_token"):
            raise RuntimeError("TikTok access token unavailable.")

    def _get(self, endpoint, params=None):
        response = requests.get(
            BASE_URL + endpoint,
            headers={"Authorization": "Bearer " + self.tokens["access_token"]},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        error = result.get("error", {})
        if error and error.get("code") not in ("ok", 0, None):
            raise RuntimeError("TikTok API error: " + str(error.get("code")))
        return result

    def verify_account(self):
        result = self._get(
            "/v2/user/info/",
            {"fields": "open_id,display_name,avatar_url"},
        )
        user = result.get("data", {}).get("user", {})
        if not user.get("open_id"):
            raise RuntimeError("TikTok account verification failed.")
        return {
            "ok": True,
            "open_id": user["open_id"],
            "display_name": user.get("display_name"),
        }


    def creator_info(self):
        """Retrieve TikTok creator settings before a publishing operation."""
        return self._get("/v2/post/publish/creator_info/query/")

    def publication_status(self, publish_id):
        """Retrieve the processing status of a TikTok publication."""
        if not publish_id:
            raise ValueError("publish_id is required")
        import requests
        from .secure_storage import load_tokens
        token = load_tokens() or {}
        access = token.get("access_token")
        if not access:
            raise RuntimeError("TikTok account is not connected")
        response = requests.post(
            BASE_URL.rstrip("/") + "/v2/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
            json={"publish_id": publish_id}, timeout=30
        )
        response.raise_for_status()
        return response.json()

    def publish_video(self, video_path, title="", privacy_level="SELF_ONLY",
                      consent=False, disable_comment=False, disable_duet=False,
                      disable_stitch=False):
        """Direct-post a video only after explicit per-publication consent."""
        from integrations.video_clipping.media_preflight import validate_for_platform
        _media_check = validate_for_platform(video_path, 'tiktok')
        if not _media_check.get('valid'):
            raise ValueError('Media preflight rejected upload: ' + '; '.join(_media_check.get('errors', [])))
        import requests, math, mimetypes
        from pathlib import Path
        from .secure_storage import load_tokens

        if consent is not True:
            raise PermissionError("Explicit consent=True is required for each TikTok publication.")

        path = Path(video_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))
        if path.suffix.lower() not in {".mp4", ".mov", ".webm"}:
            raise ValueError("Unsupported video format")

        token = load_tokens() or {}
        access = token.get("access_token")
        scopes = token.get("scope", "")
        if not access:
            raise RuntimeError("TikTok account is not connected")
        if "video.publish" not in scopes.split():
            raise PermissionError("TikTok video.publish scope is missing")

        creator = self.creator_info()
        data = creator.get("data", {})
        allowed = data.get("privacy_level_options", [])
        if privacy_level not in allowed:
            raise ValueError(f"Privacy level not allowed by creator account: {allowed}")

        size = path.stat().st_size
        chunk_size = 10 * 1024 * 1024
        chunks = math.ceil(size / chunk_size)
        if chunks < 1:
            raise ValueError("Video file is empty")
        if size > 4 * 1024 * 1024 * 1024:
            raise ValueError("Video exceeds the 4GB upload limit")

        headers = {
            "Authorization": f"Bearer {access}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        init = requests.post(
            BASE_URL.rstrip("/") + "/v2/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {
                    "title": title[:150],
                    "privacy_level": privacy_level,
                    "disable_comment": bool(disable_comment),
                    "disable_duet": bool(disable_duet),
                    "disable_stitch": bool(disable_stitch)
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": chunks
                }
            }, timeout=45
        )
        init.raise_for_status()
        payload = init.json()
        if payload.get("error", {}).get("code") not in (None, "ok"):
            raise RuntimeError(f"TikTok initialization failed: {payload['error']}")
        result = payload.get("data", {})
        upload_url = result.get("upload_url")
        publish_id = result.get("publish_id")
        if not upload_url or not publish_id:
            raise RuntimeError("TikTok did not return upload_url and publish_id")

        with path.open("rb") as stream:
            for index in range(chunks):
                start = index * chunk_size
                block = stream.read(chunk_size)
                end = start + len(block) - 1
                upload = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": _media_check["mime_type"],
                        "Content-Length": str(len(block)),
                        "Content-Range": f"bytes {start}-{end}/{size}"
                    },
                    data=block, timeout=180
                )
                upload.raise_for_status()

        return {
            "submitted": True,
            "publish_id": publish_id,
            "status": "PROCESSING",
            "message": "Upload submitted; poll publication_status before marking published."
        }
