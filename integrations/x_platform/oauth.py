import os
import getpass
import tweepy
from requests_oauthlib import OAuth2Session

SCOPES = ["users.read", "tweet.read", "tweet.write", "offline.access"]

class NexusXOAuth:
    def __init__(self):
        client_id = os.getenv("NEXUS_X_CLIENT_ID")
        if not client_id:
            raise RuntimeError("NEXUS_X_CLIENT_ID is not configured")

        client_secret = getpass.getpass("X OAuth Client Secret: ")
        if not client_secret:
            raise RuntimeError("Client Secret is required")

        self.handler = tweepy.OAuth2UserHandler(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=os.getenv(
                "NEXUS_X_REDIRECT_URI",
                "http://127.0.0.1:8766/callback"
            ),
            scope=SCOPES,
        )

    def authorization_url(self):
        return self.handler.get_authorization_url()

    def exchange_callback(self, callback_url):
        if not callback_url.startswith(
            "http://127.0.0.1:8766/callback?"
        ):
            raise ValueError("Unexpected OAuth callback address")

        return OAuth2Session.fetch_token(
            self.handler,
            "https://api.twitter.com/2/oauth2/token",
            authorization_response=callback_url,
            auth=self.handler.auth,
            include_client_id=False,
            code_verifier=self.handler._client.code_verifier
        )

    @staticmethod
    def create_client(token):
        access_token = token.get("access_token")
        if not access_token:
            raise ValueError("OAuth access token missing")
        return tweepy.Client(
            access_token=access_token,
            wait_on_rate_limit=False
        )
