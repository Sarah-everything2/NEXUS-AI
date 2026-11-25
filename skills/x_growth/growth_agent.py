from skills.x_growth.research_adapter import discover_x_opportunities
from skills.x_growth.content_generator import XContentGenerator
from skills.x_growth.draft_manager import save_draft


class XGrowthAgent:
    def __init__(self):
        self.generator = XContentGenerator()

    async def run_growth_cycle(
        self,
        content_type="post",
        max_drafts=3,
        tone="engaging",
        queries_per_category=2,
    ):
        if content_type not in ("post", "thread"):
            raise ValueError("Content type must be post or thread.")

        if not isinstance(max_drafts, int) or not 1 <= max_drafts <= 10:
            raise ValueError("max_drafts must be between 1 and 10.")

        research = await discover_x_opportunities(
            queries_per_category=queries_per_category,
            stories_per_query=5,
        )

        if not research.get("top_opportunities"):
            return {
                "status": "NO_OPPORTUNITIES",
                "research": research,
                "drafts": [],
            }

        drafts = []
        errors = []
        skipped = []

        for story in research["top_opportunities"]:
            if story.get("freshness_status") != "VERIFIED_FRESH":
                skipped.append({"title": story.get("title", "Unknown"), "reason": "UNVERIFIED_DATE"})
                continue
            if len(drafts) >= max_drafts:
                break
            try:
                if content_type == "post":
                    content = await self.generator.generate_post(
                        story,
                        tone=tone,
                    )
                else:
                    content = await self.generator.generate_thread(
                        story,
                        tone=tone,
                    )

                draft = save_draft(
                    content,
                    content_type=content_type,
                    research={
                        "title": story.get("title", ""),
                        "url": story.get("url", ""),
                        "description": story.get("description", ""),
                        "score": story.get("score"),
                        "published": story.get("published"),
                        "freshness_status": story.get("freshness_status"),
                        "matched_categories": story.get(
                            "matched_categories", []
                        ),
                        "research_report_id": research.get("report_id"),
                    },
                )

                drafts.append({
                    "draft_id": draft["draft_id"],
                    "content_type": draft["content_type"],
                    "content": draft["content"],
                    "status": draft["status"],
                    "published": False,
                })

            except Exception as exc:
                errors.append({
                    "story": story.get("title", "Unknown"),
                    "error": str(exc)[:200],
                })

        return {
            "status": (
                "SUCCESS" if drafts and not errors
                else "PARTIAL" if drafts
                else "NO_VERIFIED_FRESH_STORIES" if skipped and not errors
                else "ERROR"
            ),
            "research_report_id": research.get("report_id"),
            "categories_searched": research.get("categories_searched", 0),
            "queries_attempted": research.get("queries_attempted", 0),
            "stories_found": research.get("stories_found", 0),
            "drafts_created": len(drafts),
            "stories_skipped": len(skipped),
            "skipped_stories": skipped,
            "drafts": drafts,
            "errors": errors,
            "publishing_performed": False,
        }
