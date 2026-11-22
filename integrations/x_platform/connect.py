import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from integrations.x_platform.oauth import NexusXOAuth
from integrations.x_platform.secure_storage import save_tokens, token_status

callback_data = {}

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path != "/callback":
            self.send_error(404)
            return
        callback_data["url"] = "http://127.0.0.1:8766" + self.path
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>NEXUS authorization received. Return to PowerShell.</h2>")

    def log_message(self, *args):
        pass

try:
    oauth = NexusXOAuth()
    url = oauth.authorization_url()

    print("\nNEXUS X AUTHORIZATION")
    print("Opening browser. Authorize NEXUS when prompted.")
    print("Waiting for the local callback...\n")
    print(url)

    server = HTTPServer(("127.0.0.1", 8766), CallbackHandler)
    server.timeout = 300
    webbrowser.open(url)
    server.handle_request()
    server.server_close()

    if not callback_data.get("url"):
        raise TimeoutError("No callback received within 5 minutes")

    token = oauth.exchange_callback(callback_data["url"])
    save_tokens(token)

    print("\nOAUTH RESULT: SUCCESS")
    print("SECURE STORAGE:", token_status())
    print("Token values were not displayed.")

except Exception as exc:
    print("\nOAUTH RESULT: FAILED")
    print(type(exc).__name__, str(exc))
