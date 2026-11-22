"""NEXUS original X thread builder. TESTING ONLY."""
TESTING_MODE = True
PUBLISHING_ENABLED = False

def build_thread(story):
    title = story.get("title", "AI topic")
    notes = story.get("research_notes", story.get("transcript_excerpt", ""))
    notes = notes[:7000]
    posts = [
        f"🧵 {title}: 7 things worth understanding.",
        f"1/ The big idea: {title}. Start by understanding the problem this technology is trying to solve.",
        "2/ The real value isn't hype. It's finding a practical use case that saves time, money, or effort.",
        "3/ Start small. Test one workflow before attempting to automate everything.",
        "4/ Always verify AI output. Automation can scale mistakes just as quickly as it scales productivity.",
        "5/ Measure results. Track time saved, reliability, cost, and whether the workflow actually helps.",
        "6/ Build gradually: experiment → validate → improve → scale.",
        "7/ The takeaway: understand the problem first, then choose the tool. Bookmark this thread for later."
    ]
    return {
        "status": "DRAFT",
        "testing_mode": True,
        "publishing_enabled": False,
        "platform": "X",
        "topic": title,
        "posts": posts,
        "research_reference": notes[:1000],
        "source_url": story.get("source", ""),
        "original_content_required": True,
        "approval_required": True
    }
