import hashlib
import json
import re
import time
from pathlib import Path

from integrations.video_clipping import engine

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "workspace" / "video_output"
MANIFESTS = OUTPUT / "manifests"

PROFILES = {
    "youtube_shorts": {
        "width": 1080,
        "height": 1920,
        "max_duration": 180,
        "aspect_ratio": "9:16"
    },
    "tiktok": {
        "width": 1080,
        "height": 1920,
        "max_duration": 180,
        "aspect_ratio": "9:16"
    },
    "instagram_reels": {
        "width": 1080,
        "height": 1920,
        "max_duration": 180,
        "aspect_ratio": "9:16"
    }
}


def file_fingerprint(path):
    digest = hashlib.sha256()

    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def find_duplicate(path):
    fingerprint = file_fingerprint(path)
    registry = OUTPUT / "video_fingerprints.json"

    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}

    existing = data.get(fingerprint)

    return {
        "duplicate": bool(existing),
        "fingerprint": fingerprint,
        "existing_source": existing
    }


def register_video(path, metadata=None):
    fingerprint = file_fingerprint(path)
    registry = OUTPUT / "video_fingerprints.json"

    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}

    data[fingerprint] = {
        "path": str(Path(path).resolve()),
        "registered_at": time.time(),
        "metadata": metadata or {}
    }

    temp = registry.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(registry)

    return fingerprint


def clip_segments(segments, start, end):
    """Return transcript segments with timestamps relative to the clip."""
    result = []

    for segment in segments:
        try:
            segment_start = float(segment.get("start", 0))
            segment_end = float(segment.get("end", 0))

            overlap_start = max(segment_start, start)
            overlap_end = min(segment_end, end)

            if overlap_end <= overlap_start:
                continue

            item = dict(segment)
            item["start"] = overlap_start - start
            item["end"] = overlap_end - start
            result.append(item)

        except (TypeError, ValueError, AttributeError):
            continue

    return result


def create_captioned_clip(video_path, segments, start, duration, output_path):
    subtitle_path = Path(output_path).with_suffix(".srt")
    captioned_path = Path(output_path).with_name(
        Path(output_path).stem + "_captioned.mp4"
    )

    relevant = clip_segments(segments, start, start + duration)

    if not relevant:
        return {
            "status": "NO_CAPTIONS",
            "video": str(video_path)
        }

    engine.create_subtitles(relevant, str(subtitle_path))
    if not subtitle_path.is_file():
        raise RuntimeError("Subtitle file was not created")

    engine.burn_subtitles(
        str(video_path),
        str(subtitle_path),
        str(captioned_path)
    )

    if not captioned_path.is_file():
        raise RuntimeError("Captioned video was not created")

    return {
        "status": "CAPTIONED",
        "video": str(captioned_path),
        "subtitle": str(subtitle_path)
    }


def extract_metadata(segments, source_name):
    text = " ".join(
        str(s.get("text", "")).strip()
        for s in segments
        if isinstance(s, dict)
    )
    text = re.sub(r"\s+", " ", text).strip()

    words = re.findall(r"[A-Za-z0-9']+", text)
    title = " ".join(words[:9]).strip()

    if not title:
        title = Path(source_name).stem.replace("_", " ")

    title = title[:90]

    tags = []
    for word in words:
        clean = re.sub(r"[^A-Za-z0-9]", "", word).lower()
        if len(clean) >= 4 and clean not in tags:
            tags.append(clean)
        if len(tags) >= 8:
            break

    hashtags = ["#" + tag for tag in tags]

    return {
        "title_draft": title,
        "description_draft": text[:1500],
        "hashtags": hashtags,
        "metadata_source": "transcript_extraction",
        "requires_editorial_review": True
    }


def build_manifest(job_id, source, segments, clips):
    MANIFESTS.mkdir(parents=True, exist_ok=True)

    manifest = {
        "job_id": job_id,
        "source": str(source),
        "source_fingerprint": file_fingerprint(source),
        "created_at": time.time(),
        "platform_profiles": PROFILES,
        "clips": clips,
        "metadata": extract_metadata(
            segments,
            Path(source).name
        ),
        "publishing": {
            "status": "NOT_PUBLISHED",
            "public_upload_authorized": False,
            "private_upload_authorized": False
        }
    }

    path = MANIFESTS / f"{job_id}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    temp.replace(path)

    return manifest


def validate_platform_duration(duration, platform):
    profile = PROFILES.get(platform)
    if not profile:
        raise ValueError("Unknown platform profile")

    return 0 < float(duration) <= profile["max_duration"]
