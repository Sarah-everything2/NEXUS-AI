import json
import subprocess
import sys
from datetime import datetime, timezone


def enrich_top_metadata(signals, limit=3):
    ranked = sorted(
        signals,
        key=lambda x: x.get("radar", {}).get("score", 0),
        reverse=True
    )

    selected = ranked[:max(0, min(int(limit), 3))]

    for item in selected:
        url = item.get("url")
        if not url:
            item["metadata_status"] = "NO_URL"
            continue

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "yt_dlp",
                    "--skip-download", "--dump-single-json",
                    "--no-warnings", "--socket-timeout", "8", "--retries", "0", "--extractor-retries", "0",
                    "--no-playlist", url
                ],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
                encoding="utf-8",
                errors="replace"
            )

            if result.returncode != 0 or not result.stdout.strip():
                item["metadata_status"] = "UNAVAILABLE"
                continue

            meta = json.loads(result.stdout)

            for source, target in (
                ("view_count", "views"),
                ("like_count", "likes"),
                ("upload_date", "upload_date"),
                ("duration", "duration"),
            ):
                value = meta.get(source)
                if value is not None:
                    item[target] = value

            upload_date = item.get("upload_date")
            age_hours = None

            if upload_date:
                try:
                    published = datetime.strptime(
                        upload_date, "%Y%m%d"
                    ).replace(tzinfo=timezone.utc)
                    age_hours = max(
                        0,
                        (datetime.now(timezone.utc) - published)
                        .total_seconds() / 3600
                    )
                except (ValueError, TypeError):
                    pass

            item["age_hours"] = age_hours
            item["age_data_status"] = (
                "MEASURED" if age_hours is not None else "UNKNOWN"
            )
            item["metadata_status"] = "ENRICHED"

            quality = item.setdefault("data_quality", {})
            quality["views"] = (
                "MEASURED" if meta.get("view_count") is not None
                else "UNAVAILABLE"
            )
            quality["likes"] = (
                "MEASURED" if meta.get("like_count") is not None
                else "UNAVAILABLE"
            )
            quality["upload_date"] = (
                "MEASURED" if upload_date else "UNAVAILABLE"
            )

        except subprocess.TimeoutExpired:
            item["metadata_status"] = "TIMEOUT"
        except (json.JSONDecodeError, OSError, TypeError):
            item["metadata_status"] = "ERROR"

    return signals
