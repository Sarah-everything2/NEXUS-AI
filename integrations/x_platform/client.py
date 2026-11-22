"""NEXUS X API client. TESTING by default; posting requires explicit approval."""
import os
import tweepy

TESTING_MODE = True
PUBLISHING_ENABLED = False


class NexusXClient:
    def __init__(self):
        self.client = tweepy.Client(
            bearer_token=os.getenv("NEXUS_X_BEARER_TOKEN"),
            consumer_key=os.getenv("NEXUS_X_API_KEY"),
            consumer_secret=os.getenv("NEXUS_X_API_SECRET"),
            access_token=os.getenv("NEXUS_X_ACCESS_TOKEN"),
            access_token_secret=os.getenv("NEXUS_X_ACCESS_SECRET"),
            wait_on_rate_limit=False
        )

    def verify_account(self):
        try:
            result = self.client.get_me(user_auth=True)
            return {"ok": bool(result.data), "account": result.data.username if result.data else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def post_text(self, text, approved=False):
        if TESTING_MODE:
            return {"ok": False, "mode": "TESTING", "preview": text, "published": False}
        if not approved:
            return {"ok": False, "error": "Approval required", "published": False}
        if not text or len(text) > 280:
            return {"ok": False, "error": "Post must contain 1-280 characters"}
        try:
            result = self.client.create_tweet(text=text)
            return {"ok": bool(result.data), "post_id": result.data.get("id") if result.data else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def post_thread(self, posts, approved=False):
        if TESTING_MODE:
            return {"ok": False, "mode": "TESTING", "preview": posts, "published": False}
        if not approved:
            return {"ok": False, "error": "Approval required", "published": False}
        if not posts or len(posts) > 10 or any(not p or len(p) > 280 for p in posts):
            return {"ok": False, "error": "Invalid thread: 1-10 posts, max 280 characters each"}
        ids = []
        reply_to = None
        try:
            for post in posts:
                result = self.client.create_tweet(text=post, in_reply_to_tweet_id=reply_to)
                if not result.data:
                    return {"ok": False, "published_ids": ids, "error": "Thread interrupted"}
                reply_to = result.data["id"]
                ids.append(reply_to)
            return {"ok": True, "post_ids": ids}
        except Exception as e:
            return {"ok": False, "published_ids": ids, "error": str(e)}

    def close(self):
        self.client = None
