"""NEXUS AI-to-Earn Original Content Generator. Production mode."""
TESTING_MODE = False
PUBLISHING_ENABLED = True

def generate_content(story, content_type="youtube"):
    title = story.get("title", "Trending topic")
    transcript = story.get("transcript_excerpt", "")
    source = story.get("source_url", "")
    formats = {
        "youtube": {
            "hook": f"What if everything you know about {title} is missing one important detail?",
            "outline": ["Hook", "The problem", "Three key insights", "Practical demonstration", "Conclusion"],
            "length": "5-8 minutes"
        },
        "short": {
            "hook": f"Here's something most people overlook about {title}.",
            "outline": ["Hook", "One surprising insight", "Practical takeaway", "Call to action"],
            "length": "30-60 seconds"
        },
        "tiktok": {
            "hook": f"Stop scrolling. Here's what you need to know about {title}.",
            "outline": ["Hook", "Problem", "Solution or insight", "Closing"],
            "length": "30-60 seconds"
        },
        "x": {
            "hook": f"What I learned researching {title}:",
            "outline": ["Hook tweet", "Insight 1", "Insight 2", "Insight 3", "Conclusion"],
            "length": "5-7 posts"
        }
    }
    template = formats.get(content_type, formats["youtube"])
    return {
        "status": "DRAFT",
        "testing_mode": False,
        "publishing_enabled": True,
        "content_type": content_type,
        "topic": title,
        "hook": template["hook"],
        "outline": template["outline"],
        "target_length": template["length"],
        "research_notes": transcript[:2500],
        "source": source,
        "original_content_required": True,
        "copyright_notice": "Use research for inspiration. Do not copy source wording.",
        "approval_required": True
    }
