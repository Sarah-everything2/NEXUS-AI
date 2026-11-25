import asyncio
from tools.manager import TOOLS
from skills.x_growth.growth_agent import XGrowthAgent
from skills.x_growth.draft_manager import list_drafts, get_draft
from skills.x_growth.publication_manager import record_publish_result
from skills.x_growth.analytics import save_analytics_report
from integrations.x_platform.tools import x_post, x_thread


async def x_growth_run(
    content_type="post",
    max_drafts=3,
    tone="engaging",
    queries_per_category=2,
):
    agent = XGrowthAgent()
    return await agent.run_growth_cycle(
        content_type=content_type,
        max_drafts=max_drafts,
        tone=tone,
        queries_per_category=queries_per_category,
    )


def x_growth_list_drafts():
    return list_drafts()


def x_growth_preview_draft(draft_id):
    draft = get_draft(draft_id)

    if not draft:
        return {"ok": False, "error": "Draft not found."}

    return {
        "ok": True,
        "draft": draft,
        "publishing_performed": False,
    }


def x_growth_publish_draft(draft_id):
    draft = get_draft(draft_id)

    if not draft:
        return {"ok": False, "error": "Draft not found."}

    if draft.get("status") not in ("DRAFT", "FAILED") or draft.get("published"):
        return {
            "ok": False,
            "error": "Only unpublished drafts can be published.",
        }

    if draft["content_type"] == "post":
        result = x_post(draft["content"])
    elif draft["content_type"] == "thread":
        result = x_thread(draft["content"])
    else:
        return {"ok": False, "error": "Unsupported draft type."}

    if not isinstance(result, dict):
        return {"ok": False, "error": "Invalid X publication response."}

    if result.get("error") == "Approval denied.":
        return {
            "ok": False,
            "published": False,
            "error": "Human approval denied. No publication recorded.",
        }

    receipt = record_publish_result(draft_id, result)

    return {
        "ok": receipt["status"] == "PUBLISHED",
        "publication_status": receipt["status"],
        "receipt": receipt,
    }


def x_growth_analytics():
    return save_analytics_report()


TOOLS.update({
    "x_growth_run": x_growth_run,
    "x_growth_list_drafts": x_growth_list_drafts,
    "x_growth_preview_draft": x_growth_preview_draft,
    "x_growth_publish_draft": x_growth_publish_draft,
    "x_growth_analytics": x_growth_analytics,
})


print("X Growth tools registered:", [
    name for name in TOOLS if name.startswith("x_growth_")
])
