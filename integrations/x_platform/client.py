"""NEXUS X client using Native App OAuth2 PKCE credentials."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
import time
import tweepy
from dotenv import load_dotenv

from integrations.x_platform.secure_storage import load_tokens, save_tokens

load_dotenv()

SCOPES = ["users.read", "tweet.read", "tweet.write", "offline.access"]
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
REDIRECT_URI = os.getenv(
    "NEXUS_X_REDIRECT_URI",
    "http://127.0.0.1:8766/callback"
)

TESTING_MODE = False
PUBLISHING_ENABLED = True


class NexusXClient:
    def __init__(self):
        self.client = None
        self._connect()

    def _connect(self):
        token = load_tokens()

        if not token or not token.get("access_token"):
            raise RuntimeError("X account is not connected. Run connect.py first.")

        expires_at = token.get("expires_at")

        if expires_at and float(expires_at) <= time.time() + 60:
            refresh = token.get("refresh_token")

            if not refresh:
                raise RuntimeError("X access token expired and no refresh token exists. Reconnect X.")

            client_id = os.getenv("NEXUS_X_CLIENT_ID")
            if not client_id:
                raise RuntimeError("NEXUS_X_CLIENT_ID is not configured.")

            handler = tweepy.OAuth2UserHandler(
                client_id=client_id,
                redirect_uri=REDIRECT_URI,
                scope=SCOPES,
            )

            refreshed = handler.refresh_token(
                TOKEN_URL,
                refresh_token=refresh,
                client_id=client_id,
            )

            if not refreshed.get("access_token"):
                raise RuntimeError("X token refresh failed.")

            if not refreshed.get("refresh_token"):
                refreshed["refresh_token"] = refresh

            save_tokens(refreshed)
            token = refreshed

        self.client = tweepy.Client(
            bearer_token=token["access_token"],
            wait_on_rate_limit=False,
        )

    def verify_account(self):
        try:
            result = self.client.get_me(user_auth=False)
            return {
                "ok": bool(result.data),
                "account": result.data.username if result.data else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def post_text(self, text, approved=False):
        if TESTING_MODE or not PUBLISHING_ENABLED:
            return {"ok": False, "error": "Publishing is disabled.", "published": False}
        if not approved:
            return {"ok": False, "error": "Approval required", "published": False}
        if not text or len(text) > 280:
            return {"ok": False, "error": "Post must contain 1-280 characters"}

        try:
            result = self.client.create_tweet(text=text, user_auth=False)
            return {
                "ok": bool(result.data),
                "post_id": result.data.get("id") if result.data else None,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def post_thread(self, posts, approved=False):
        if TESTING_MODE or not PUBLISHING_ENABLED:
            return {"ok": False, "error": "Publishing is disabled.", "published": False}
        if not approved:
            return {"ok": False, "error": "Approval required", "published": False}
        if not posts or len(posts) > 10 or any(not p or len(p) > 280 for p in posts):
            return {"ok": False, "error": "Invalid thread: 1-10 posts, max 280 characters each"}

        ids = []
        reply_to = None

        try:
            for post in posts:
                result = self.client.create_tweet(
                    text=post,
                    in_reply_to_tweet_id=reply_to,
                    user_auth=False,
                )
                if not result.data:
                    return {"ok": False, "published_ids": ids, "error": "Thread interrupted"}

                reply_to = result.data["id"]
                ids.append(reply_to)

            return {"ok": True, "post_ids": ids}
        except Exception as e:
            return {"ok": False, "published_ids": ids, "error": str(e)}

    def search_recent(self, query, max_results=20):
        if not query or not isinstance(query, str):
            return {"ok": False, "error": "A search query is required."}

        max_results = max(10, min(int(max_results), 100))

        try:
            result = self.client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics", "author_id"],
                user_auth=False,
            )
            return {
                "ok": True,
                "query": query,
                "tweets": [
                    {
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": str(tweet.created_at),
                        "author_id": tweet.author_id,
                        "metrics": tweet.public_metrics or {},
                    }
                    for tweet in (result.data or [])
                ],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def account_timeline(self, max_results=20):
        max_results = max(5, min(int(max_results), 100))

        try:
            account = self.client.get_me(user_auth=False)
            if not account.data:
                return {"ok": False, "error": "Unable to identify connected account."}

            result = self.client.get_users_tweets(
                id=account.data.id,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics"],
                user_auth=False,
            )
            return {
                "ok": True,
                "username": account.data.username,
                "tweets": [
                    {
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": str(tweet.created_at),
                        "metrics": tweet.public_metrics or {},
                    }
                    for tweet in (result.data or [])
                ],
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def close(self):
        self.client = None
