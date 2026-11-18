import asyncio
import socket
import ipaddress

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse


MAX_CONTENT_SIZE = 500_000
MAX_TEXT_LENGTH = 10_000


def validate_url(url):

    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("Only HTTPS websites are currently permitted.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid website address.")

    hostname = parsed.hostname

    if hostname.lower() in ("localhost",):
        raise ValueError("Local addresses are prohibited.")

    try:
        addresses = socket.getaddrinfo(
            hostname, 443, type=socket.SOCK_STREAM
        )

        if not addresses:
            raise ValueError("Website address could not be resolved.")

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])

            if not ip.is_global:
                raise ValueError("Private or restricted network addresses are prohibited.")

    except socket.gaierror:
        raise ValueError("Website address could not be resolved.")

    return parsed


async def fetch_page(url):

    parsed = validate_url(url)

    timeout = httpx.Timeout(20.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False
    ) as client:

        response = await client.get(
            url,
            headers={"User-Agent": "NEXUS-AI/0.2"}
        )

        if response.is_redirect:
            raise ValueError("Redirects are not permitted.")

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "text/html" not in content_type.lower():
            raise ValueError("Only HTML webpages are supported.")

        if len(response.content) > MAX_CONTENT_SIZE:
            raise ValueError("Webpage exceeds the 500 KB limit.")

        soup = BeautifulSoup(response.text, "html.parser")

        for element in soup([
            "script", "style", "nav", "footer",
            "header", "iframe", "form"
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
            "status": "SUCCESS"
        }


if __name__ == "__main__":

    print("NEXUS AI WEB RESEARCH ENGINE")
    print("----------------------------")
    print("HTTPS only: ENABLED")
    print("Private address checks: ENABLED")
    print("Redirects: BLOCKED")
    print("Content limit:", MAX_CONTENT_SIZE)
    print("Status: READY")