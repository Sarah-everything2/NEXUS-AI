from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl, Field

from skills.executor import execute_skill_async
from memory.store import save_research, search_research
from tools.web_search import search_web
from tools.research_analyzer import analyze_research

router = APIRouter(prefix="/api/research", tags=["Research"])


class ResearchRequest(BaseModel):
    url: HttpUrl


class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=5, ge=1, le=10)


class AnalysisRequest(BaseModel):
    query: str
    max_sources: int = Field(default=5, ge=1, le=10)


@router.post("/fetch")
async def research_webpage(request: ResearchRequest):

    try:
        result = await execute_skill_async(
            "web_research",
            "fetch",
            url=str(request.url)
        )

        save_research(
            result["url"],
            result["title"],
            result["content"]
        )

        result["memory"] = "SAVED"
        return result

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/history")
def research_history(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50)
):

    return {
        "results": search_research(q, limit)
    }


@router.post("/search")
def live_web_search(request: SearchRequest):

    try:
        result = search_web(
            request.query,
            request.max_results
        )

        saved = 0

        for item in result["results"]:
            if item["url"]:
                save_research(
                    item["url"],
                    item["title"] or "Untitled",
                    item["snippet"]
                )
                saved += 1

        result["memory"] = "SAVED"
        result["saved_results"] = saved

        return result

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/search/history")
def search_history(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50)
):

    return {
        "results": search_research(q, limit)
    }


@router.post("/analyze")
async def research_analysis(request: AnalysisRequest):

    try:
        result = await analyze_research(
            request.query,
            request.max_sources
        )

        saved = 0

        for source in result["sources"]:

            save_research(
                source["url"],
                source["title"],
                source["content"]
            )

            saved += 1

        result["memory"] = "SAVED"
        result["saved_sources"] = saved

        return result

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))