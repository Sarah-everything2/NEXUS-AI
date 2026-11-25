import os
import tweepy

SCOPES = [
    "users.read",
    "tweet.read",
    "tweet.write",
    "offline.access",
]

REDIRECT_URI = os.getenv(
    "NEXUS_X_REDIRECT_URI",
    "http://127.0.0.1:8766/callback"
)


class NexusXOAuth:
    def __init__(self):
        client_id = os.getenv("NEXUS_X_CLIENT_ID")
        if not client_id:
            raise RuntimeError("NEXUS_X_CLIENT_ID is not configured")

        self.handler = tweepy.OAuth2UserHandler(
            client_id=client_id,
            redirect_uri=REDIRECT_URI,
            scope=SCOPES,
        )

    def authorization_url(self):
        return self.handler.get_authorization_url()

    def exchange_callback(self, callback_url):
        if not callback_url.startswith(REDIRECT_URI + "?"):
            raise ValueError("Unexpected OAuth callback address")

        return self.handler.fetch_token(callback_url)

    @staticmethod
    def create_client(token):
        if not token or not token.get("access_token"):
            raise ValueError("OAuth access token missing")

        return tweepy.Client(
            access_token=token["access_token"],
            wait_on_rate_limit=False,
        )
