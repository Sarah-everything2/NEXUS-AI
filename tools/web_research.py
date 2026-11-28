import socket
import ipaddress

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse


MAX_CONTENT_SIZE = 500_000
MAX_TEXT_LENGTH = 10_000
ALLOWED_PORT = 443


def validate_url(url):
    if not isinstance(url, str):
        raise ValueError("A valid website URL is required.")

    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":
        raise ValueError("Only HTTPS websites are currently permitted.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid website address.")

    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Invalid website port.") from error

    if port not in (None, ALLOWED_PORT):
        raise ValueError("Only HTTPS port 443 is permitted.")

    hostname = parsed.hostname.rstrip(".").lower()

    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Local addresses are prohibited.")

    try:
        # Handle IP-literal URLs without relying on DNS.
        try:
            literal_ip = ipaddress.ip_address(hostname)
            addresses = [literal_ip]
        except ValueError:
            resolved = socket.getaddrinfo(
                hostname, ALLOWED_PORT, type=socket.SOCK_STREAM
            )
            addresses = [
                ipaddress.ip_address(item[4][0])
                for item in resolved
            ]

        if not addresses:
            raise ValueError("Website address could not be resolved.")

        # Reject the hostname if ANY returned address is non-public.
        for address in addresses:
            if not address.is_global:
                raise ValueError(
                    "Private or restricted network addresses are prohibited."
                )

    except socket.gaierror as error:
        raise ValueError("Website address could not be resolved.") from error

    return parsed


async def fetch_page(url):
    parsed = validate_url(url)

    timeout = httpx.Timeout(20.0)

    # Do not inherit proxy settings from the host environment.
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:

        # Stream the response so oversized pages are rejected before
        # the complete response body is buffered in memory.
        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": "NEXUS-AI/0.2"},
        ) as response:

            if response.is_redirect:
                raise ValueError("Redirects are not permitted.")

            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type.lower():
                raise ValueError("Only HTML webpages are supported.")

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > MAX_CONTENT_SIZE:
                        raise ValueError(
                            "Webpage exceeds the 500 KB limit."
                        )
                except ValueError as error:
                    if "exceeds" in str(error):
                        raise
                    raise ValueError("Invalid webpage content length.") from error

            body = bytearray()

            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_CONTENT_SIZE:
                    raise ValueError("Webpage exceeds the 500 KB limit.")

            encoding = response.encoding or "utf-8"
            html = bytes(body).decode(encoding, errors="replace")

        soup = BeautifulSoup(html, "html.parser")

        for element in soup([
            "script", "style", "nav", "footer",
            "header", "iframe", "form",
        ]):
            element.decompose()

        title = (
            soup.title.get_text(strip=True)
            if soup.title else "No title"
        )

        text = soup.get_text(separator=" ", strip=True)

        return {
            "url": str(parsed.geturl()),
            "title": title,
            "content": text[:MAX_TEXT_LENGTH],
            "status": "SUCCESS",
        }


if __name__ == "__main__":
    print("NEXUS AI WEB RESEARCH ENGINE")
    print("----------------------------")
    print("HTTPS only: ENABLED")
    print("Private address checks: ENABLED")
    print("Redirects: BLOCKED")
    print("Streaming content limit:", MAX_CONTENT_SIZE)
    print("Status: READY")
