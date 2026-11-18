import asyncio
from urllib.parse import urlparse

from tools.web_search import search_web
from tools.web_research import fetch_page


async def analyze_research(query, max_sources=5):

    if not isinstance(query, str) or not query.strip():
        raise ValueError("A research topic is required.")

    if not 1 <= max_sources <= 10:
        raise ValueError("Sources must be between 1 and 10.")

    search_results = search_web(query, max_sources)

    sources = []

    async def collect_source(item):

        url = item.get("url", "")

        if not url:
            return None

        try:
            page = await asyncio.wait_for(
                fetch_page(url),
                timeout=25
            )

            return {
                "title": page["title"],
                "url": page["url"],
                "domain": urlparse(page["url"]).hostname,
                "content": page["content"][:5000],
                "status": "SUCCESS"
            }

        except Exception as error:

            return {
                "title": item.get("title", "Unknown"),
                "url": url,
                "status": "FAILED",
                "error": str(error)
            }

    results = await asyncio.gather(
        *(collect_source(item) for item in search_results["results"])
    )

    for result in results:

        if result and result["status"] == "SUCCESS":
            sources.append(result)

    return {
        "query": query,
        "sources_found": search_results["count"],
        "sources_analyzed": len(sources),
        "sources_failed": search_results["count"] - len(sources),
        "sources": sources,
        "status": "SUCCESS" if sources else "NO_SOURCES_ANALYZED"
    }


if __name__ == "__main__":

    print("NEXUS AI RESEARCH ANALYZER")
    print("--------------------------")

    result = asyncio.run(
        analyze_research(
            "Open source artificial intelligence",
            3
        )
    )

    print("Research topic:", result["query"])
    print("Sources found:", result["sources_found"])
    print("Sources analyzed:", result["sources_analyzed"])

    for source in result["sources"]:
        print("\nTITLE:", source["title"])
        print("DOMAIN:", source["domain"])
        print("STATUS:", source["status"])

    print("\nFINAL STATUS:", result["status"])
