import json
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "x_growth"
PUBLISHED_DIR = BASE_DIR / "published"
ANALYTICS_DIR = BASE_DIR / "analytics"


METRIC_FIELDS = (
    "impressions",
    "likes",
    "reposts",
    "replies",
    "quotes",
    "bookmarks",
)


def save_metrics_snapshot(post_id, metrics, source="X API"):
    """Save an actual metrics observation for an X post."""

    if not isinstance(post_id, str) or not post_id.strip():
        raise ValueError("A valid post ID is required.")

    if not isinstance(metrics, dict):
        raise ValueError("Metrics must be a dictionary.")

    clean_metrics = {}

    for field in METRIC_FIELDS:
        value = metrics.get(field)

        if value is None:
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Invalid metric: {field}")

        if value < 0:
            raise ValueError(f"Metric cannot be negative: {field}")

        clean_metrics[field] = value

    if not clean_metrics:
        raise ValueError("No valid metrics were provided.")

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "post_id": post_id,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "metrics": clean_metrics,
    }

    path = ANALYTICS_DIR / f"{post_id}.json"

    history = []

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                history = existing
        except (OSError, json.JSONDecodeError):
            raise ValueError("Existing metrics history is unreadable.")

    history.append(snapshot)

    temporary = ANALYTICS_DIR / f".{post_id}.tmp"

    try:
        temporary.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()

    return snapshot


def _load_receipts():
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    receipts = []

    for path in PUBLISHED_DIR.glob("*.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(item, dict):
                receipts.append(item)
        except (OSError, json.JSONDecodeError):
            continue

    return receipts


def _load_latest_metrics(post_id):
    path = ANALYTICS_DIR / f"{post_id}.json"

    if not path.exists():
        return None

    try:
        history = json.loads(path.read_text(encoding="utf-8"))

        if not isinstance(history, list) or not history:
            return None

        return history[-1].get("metrics")

    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def build_analytics_report():
    """Build an analytics report from receipts and actual metric snapshots."""

    receipts = _load_receipts()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_receipts": len(receipts),
        "successful_publications": 0,
        "partial_publications": 0,
        "failed_publications": 0,
        "total_posts_published": 0,
        "posts_with_metrics": 0,
        "posts_without_metrics": 0,
        "engagement_totals": {},
        "engagement_rate": None,
        "metrics_source": "Actual saved observations only",
        "posts": [],
    }

    totals = {
        field: 0
        for field in METRIC_FIELDS
    }

    impressions_available = True
    engagement_fields = ("likes", "reposts", "replies", "quotes")

    for receipt in receipts:
        status = receipt.get("status")

        if status == "PUBLISHED":
            report["successful_publications"] += 1
        elif status == "PARTIAL":
            report["partial_publications"] += 1
        elif status == "FAILED":
            report["failed_publications"] += 1

        post_ids = receipt.get("post_ids") or []
        report["total_posts_published"] += len(post_ids)

        for post_id in post_ids:
            metrics = _load_latest_metrics(str(post_id))

            post = {
                "post_id": str(post_id),
                "receipt_id": receipt.get("receipt_id"),
                "status": status,
                "metrics": metrics,
            }

            if metrics is None:
                report["posts_without_metrics"] += 1
                impressions_available = False
            else:
                report["posts_with_metrics"] += 1

                for field, value in metrics.items():
                    if field in totals:
                        totals[field] += value

                if "impressions" not in metrics:
                    impressions_available = False

            report["posts"].append(post)

    report["engagement_totals"] = totals

    impressions = 0
    engagement_total = sum(
        totals[field] for field in engagement_fields
    )

    for post in report["posts"]:
        metrics = post.get("metrics") or {}
        if "impressions" in metrics:
            impressions += metrics["impressions"]

    if (
        report["total_posts_published"] > 0
        and report["posts_with_metrics"] == report["total_posts_published"]
        and impressions_available
        and impressions > 0
    ):
        report["engagement_rate"] = round(
            engagement_total / impressions * 100,
            2,
        )

    return report


def save_analytics_report():
    report = build_analytics_report()

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    path = ANALYTICS_DIR / "latest_report.json"
    temporary = ANALYTICS_DIR / ".latest_report.tmp"

    try:
        temporary.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()

    return report
