"""NEXUS AI-to-Earn Story Intelligence. Production mode."""
from .youtube import fetch_transcript

TESTING_MODE = False

def analyze_story(video):
    transcript_data = fetch_transcript(video["url"])
    transcript = transcript_data.get("transcript", "")

    if not transcript:
        return {
            "ok": False,
            "title": video.get("title"),
            "reason": "Transcript unavailable",
            "content_opportunities": []
        }

    text = transcript[:18000]
    title = video.get("title", "")

    opportunities = [
        {
            "format": "YouTube Short",
            "angle": f"3 surprising lessons from {title}"
        },
        {
            "format": "TikTok",
            "angle": f"The biggest mistake people make with {title}"
        },
        {
            "format": "X Thread",
            "angle": f"Key insights and practical takeaways: {title}"
        },
        {
            "format": "YouTube Video",
            "angle": f"An original deep dive inspired by the topic: {title}"
        }
    ]

    return {
        "ok": True,
        "title": title,
        "channel": video.get("channel"),
        "source_url": video.get("url"),
        "transcript_characters": len(transcript),
        "transcript_excerpt": text[:3000],
        "content_opportunities": opportunities,
        "requires_original_content": True,
        "publishing_enabled": True
    }
