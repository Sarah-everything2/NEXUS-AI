from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, HttpUrl, Field

from memory.store import save_research, search_research
from tools.web_search import search_web
from tools.web_research import fetch_page
from tools.research_analyzer import analyze_research

router = APIRouter(prefix="/api/research", tags=["Research"])


def _identity(http_request: Request):
    user = getattr(http_request.state, "current_user", None)

    if not isinstance(user, dict):
        raise HTTPException(401, "Authentication required.")

    user_id = user.get("id")
    role = user.get("role")

    if not isinstance(user_id, int) or user_id < 1:
        raise HTTPException(403, "Invalid account identity.")

    if role not in ("admin", "user"):
        raise HTTPException(403, "Account role is not permitted.")

    return user_id, role


class ResearchRequest(BaseModel):
    url: HttpUrl


class SearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=5, ge=1, le=10)


class AnalysisRequest(BaseModel):
    query: str
    max_sources: int = Field(default=5, ge=1, le=10)


@router.post("/fetch")
async def research_webpage(request: ResearchRequest, http_request: Request):
    user_id, _role = _identity(http_request)

    try:
        result = await fetch_page(url=str(request.url))

        save_research(
            result["url"],
            result["title"],
            result["content"],
            user_id=user_id,
        )

        result["memory"] = "SAVED"
        return result

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/history")
def research_history(
    http_request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    user_id, role = _identity(http_request)

    return {
        "results": search_research(
            q, limit, user_id=user_id, is_admin=(role == "admin")
        )
    }


@router.post("/search")
def live_web_search(request: SearchRequest, http_request: Request):
    user_id, _role = _identity(http_request)

    try:
        result = search_web(request.query, request.max_results)
        saved = 0

        for item in result["results"]:
            if item["url"]:
                save_research(
                    item["url"],
                    item["title"] or "Untitled",
                    item["snippet"],
                    user_id=user_id,
                )
                saved += 1

        result["memory"] = "SAVED"
        result["saved_results"] = saved
        return result

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/search/history")
def search_history(
    http_request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    user_id, role = _identity(http_request)

    return {
        "results": search_research(
            q, limit, user_id=user_id, is_admin=(role == "admin")
        )
    }


@router.post("/analyze")
async def research_analysis(request: AnalysisRequest, http_request: Request):
    user_id, _role = _identity(http_request)

    try:
        result = await analyze_research(
            request.query,
            request.max_sources,
        )

        saved = 0

        for source in result["sources"]:
            save_research(
                source["url"],
                source["title"],
                source["content"],
                user_id=user_id,
            )
            saved += 1

        result["memory"] = "SAVED"
        result["saved_sources"] = saved
        return result

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))
