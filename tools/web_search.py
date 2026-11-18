from ddgs import DDGS
from urllib.parse import urlparse


BLOCKED_DOMAINS = {
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com"
}


def search_web(query, max_results=5):

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A search query is required.")

    if not 1 <= max_results <= 10:
        raise ValueError("Results must be between 1 and 10.")

    try:
        results = DDGS().text(
            query.strip(),
            max_results=max_results * 2,
            safesearch="moderate"
        )

        output = []
        seen = set()

        for item in results:

            url = item.get("href", "")
            title = item.get("title", "")
            snippet = item.get("body", "")

            domain = urlparse(url).netloc.lower().replace("www.", "")

            if not url.startswith("https://"):
                continue

            if any(domain == blocked or domain.endswith("." + blocked)
                   for blocked in BLOCKED_DOMAINS):
                continue

            if url in seen:
                continue

            seen.add(url)

            output.append({
                "title": title,
                "url": url,
                "snippet": snippet
            })

            if len(output) >= max_results:
                break

        return {
            "query": query,
            "count": len(output),
            "results": output,
            "status": "SUCCESS"
        }

    except Exception as error:
        raise RuntimeError(f"Web search failed: {error}") from error


if __name__ == "__main__":

    result = search_web("Best open source AI agent frameworks", 5)

    for item in result["results"]:
        print("\nTITLE:", item["title"])
        print("URL:", item["url"])
        print("SNIPPET:", item["snippet"])

    print("\nSTATUS:", result["status"])