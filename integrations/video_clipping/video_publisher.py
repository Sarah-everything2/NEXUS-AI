import json
import time
from pathlib import Path

from integrations.video_clipping.publication_manager import (
    get_ready_jobs,
    update_publication,
    recover_interrupted
)

ROOT = Path(__file__).resolve().parents[2]
YOUTUBE_CONFIG = ROOT / "integrations" / "youtube" / "config.json"
VIDEO_POLICY = ROOT / "config" / "video_autopilot.policy.json"


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _settings_autonomous():
    from core.settings import load_settings
    settings = load_settings()

    if isinstance(settings, dict):
        return settings.get("autonomous_mode") is True

    return getattr(settings, "autonomous_mode", False) is True



def publish_youtube(job):
    from integrations.video_clipping.platform_adapters import publish

    return publish(
        "youtube",
        job["video_path"],
        job.get("metadata", {}),
        job.get("privacy", "private")
    )


def process_publication_queue(max_jobs=1):
    from integrations.video_clipping.video_authorization import load_policy
    try:
        policy = load_policy()
        if policy.get("enabled") is not True or policy.get("auto_publish_enabled") is not True:
            return [{"status": "DISABLED", "reason": "Autonomous video publishing is disabled"}]
    except Exception as exc:
        return [{"status": "DISABLED", "reason": str(exc)}]

    recover_interrupted()

    results = []

    cap = min(3, max(1, int(policy.get("maximum_publications_per_cycle", 1))))
    requested = max(1, min(int(max_jobs), 3, cap))
    for job in get_ready_jobs()[:requested]:
        platform = job.get("platform")

        update_publication(job["id"], "PUBLISHING")

        try:
            if platform in {"youtube", "youtube_shorts"}:
                result = publish_youtube(job)
            elif platform in {"tiktok", "instagram_reels"}:
                from integrations.video_clipping.platform_adapters import publish
                result = publish(
                    platform,
                    job["video_path"],
                    job.get("metadata", {}),
                    job.get("privacy", "private")
                )

            else:
                result = {
                    "status": "REVIEW_REQUIRED",
                    "reason": (
                        "Platform-specific API adapter and account "
                        "authorization are not yet configured"
                    )
                }

            status = result.get("status", "REVIEW_REQUIRED")

            if status == "PUBLISHED":
                update_publication(
                    job["id"],
                    "PUBLISHED",
                    result=result.get("result", {})
                )
            elif status == "FAILED":
                update_publication(
                    job["id"], "FAILED",
                    error=result.get("reason")
                )
            else:
                update_publication(
                    job["id"], "REVIEW_REQUIRED",
                    error=result.get("reason"),
                    result=result.get("result", {})
                )

            results.append({
                "job_id": job["id"],
                **result
            })

        except Exception as exc:
            # Do not blindly retry uncertain uploads.
            update_publication(
                job["id"],
                "REVIEW_REQUIRED",
                error=type(exc).__name__
            )
            results.append({
                "job_id": job["id"],
                "status": "REVIEW_REQUIRED",
                "error": type(exc).__name__
            })

    return results


def monitor_publication_job(job):
    """Read publication status without resubmitting or duplicating uploads."""
    from integrations.video_clipping.platform_adapters import publish
    platform = job.get("platform")
    job_id = job.get("id")
    metadata = job.get("metadata") or {}
    previous = job.get("result") or {}

    publish_id = previous.get("publish_id")
    container_id = previous.get("container_id")

    try:
        if platform == "tiktok":
            if not publish_id:
                return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                        "reason": "TikTok publish ID missing; manual investigation required"}
            from integrations.tiktok.client import NexusTikTokClient
            response = NexusTikTokClient().publication_status(publish_id)
            data = response.get("data", {}) if isinstance(response, dict) else {}
            state = str(data.get("status", "UNKNOWN")).upper()

            if state in {"PUBLISH_COMPLETE", "PUBLISHED", "SUCCESS"}:
                return {"job_id": job_id, "status": "PUBLISHED",
                        "result": {"publish_id": publish_id, "platform_status": state}}
            if state in {"FAILED", "PUBLISH_FAILED"}:
                return {"job_id": job_id, "status": "FAILED",
                        "reason": str(data.get("fail_reason", state))[:300],
                        "result": {"publish_id": publish_id, "platform_status": state}}

            return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                    "reason": "TikTok publication is not confirmed complete",
                    "result": {"publish_id": publish_id, "platform_status": state}}

        if platform == "instagram_reels":
            if not container_id:
                return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                        "reason": "Instagram container ID missing; manual investigation required"}
            from integrations.instagram.reels_publisher import reel_status
            response = reel_status(container_id)
            state = str(response.get("status_code", "UNKNOWN")).upper()

            if state == "FINISHED":
                from integrations.video_clipping.video_authorization import authorize_publication
                authorize_publication("instagram_reels", "public")
                from integrations.instagram.reels_publisher import publish_reel
                published = publish_reel(container_id, consent=True)
                media_id = published.get("id") if isinstance(published, dict) else None
                if not media_id:
                    return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                            "reason": "Instagram publish response has no verifiable media ID; do not retry",
                            "result": {"container_id": container_id}}
                return {"job_id": job_id, "status": "PUBLISHED",
                        "result": {"media_id": media_id, "container_id": container_id}}

            if state in {"ERROR", "EXPIRED"}:
                return {"job_id": job_id, "status": "FAILED",
                        "reason": "Instagram container cannot be published: " + state,
                        "result": {"container_id": container_id, "container_status": state}}

            return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                    "reason": "Instagram container is still processing or its status is uncertain",
                    "result": {"container_id": container_id, "container_status": state}}

        return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                "reason": "Unsupported monitoring platform"}

    except Exception as exc:
        return {"job_id": job_id, "status": "REVIEW_REQUIRED",
                "reason": "Status check failed: " + type(exc).__name__,
                "result": previous}


def monitor_pending_publications(jobs=None):
    """Poll pending jobs from the queue file or an explicitly supplied job list."""
    import json

    queue_path = Path(__file__).resolve().parents[2] / "config" / "video_publication_queue.json"

    if jobs is None:
        if not queue_path.is_file():
            return [{"status": "REVIEW_REQUIRED", "reason": "Publication queue file not found"}]
        try:
            stored = json.loads(queue_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            return [{"status": "REVIEW_REQUIRED", "reason": "Queue read failed: " + type(exc).__name__}]

        found = []
        def collect(value):
            if isinstance(value, dict):
                if value.get("platform") in {"tiktok", "instagram_reels"} and value.get("status") in {
                    "REVIEW_REQUIRED", "PUBLISHING", "PROCESSING"
                }:
                    found.append(value)
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(stored)
        jobs = found

    # Never contact a platform unless both configuration switches are enabled.
    platform_config_path = Path(__file__).resolve().parents[2] / "config" / "video_platforms.json"
    try:
        platform_config = json.loads(platform_config_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return [{"status": "DISABLED", "reason": "Platform configuration unavailable; monitoring blocked"}]

    enabled_jobs = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        platform = job.get("platform")
        section = platform_config.get("platforms", {}).get(platform, {})
        legacy_key = "instagram" if platform == "instagram_reels" else platform
        legacy = platform_config.get(legacy_key, {})
        if section.get("enabled") is True and legacy.get("enabled") is True and legacy.get("publishing_enabled") is True:
            enabled_jobs.append(job)

    jobs = enabled_jobs
    results = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        result = monitor_publication_job(job)
        results.append(result)
        job_id = job.get("id")
        if job_id:
            try:
                if result["status"] == "PUBLISHED":
                    update_publication(job_id, "PUBLISHED", result=result.get("result", {}))
                elif result["status"] == "FAILED":
                    update_publication(job_id, "FAILED",
                                       error=result.get("reason"),
                                       result=result.get("result", {}))
                else:
                    update_publication(job_id, "REVIEW_REQUIRED",
                                       error=result.get("reason"),
                                       result=result.get("result", {}))
            except Exception as exc:
                result["queue_update_error"] = type(exc).__name__
    return results
