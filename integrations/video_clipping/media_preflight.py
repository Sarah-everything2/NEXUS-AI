import mimetypes
import shutil
import subprocess
from pathlib import Path

MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/x-m4v",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}

def inspect_media(video_path, max_size_mb=512, max_duration_seconds=None):
    path = Path(video_path).expanduser()
    result = {
        "valid": False,
        "path": str(path),
        "errors": [],
        "warnings": [],
        "mime_type": None,
        "size_mb": None,
        "duration_seconds": None,
    }

    if not path.is_file():
        result["errors"].append("Media file does not exist.")
        return result

    extension = path.suffix.lower()
    mime = MIME_TYPES.get(extension) or mimetypes.guess_type(path.name)[0]
    if not mime or not mime.startswith("video/"):
        result["errors"].append("Unsupported or unrecognized video format.")
        return result

    size_mb = path.stat().st_size / (1024 * 1024)
    result["mime_type"] = mime
    result["size_mb"] = round(size_mb, 2)

    if size_mb > max_size_mb:
        result["errors"].append(
            f"File exceeds the configured {max_size_mb} MB limit."
        )

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            completed = subprocess.run(
                [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(path)
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=True
            )
            duration = float(completed.stdout.strip())
            if duration <= 0:
                raise ValueError("Invalid duration")
            result["duration_seconds"] = round(duration, 2)
            if max_duration_seconds is not None and duration > max_duration_seconds:
                result["errors"].append(
                    f"Video exceeds the {max_duration_seconds}-second duration limit."
                )
        except Exception:
            result["errors"].append("Video duration could not be verified.")
    else:
        result["warnings"].append(
            "ffprobe unavailable; duration has not been verified."
        )
        if max_duration_seconds is not None:
            result["errors"].append(
                "A duration-limited platform requires ffprobe validation."
            )

    result["valid"] = not result["errors"]
    return result

def validate_for_platform(video_path, platform):
    limits = {
        "youtube": {"size": 512, "duration": None},
        "tiktok": {"size": 512, "duration": 600},
        "instagram": {"size": 512, "duration": 900},
    }
    platform = str(platform).lower()
    if platform not in limits:
        return {
            "valid": False,
            "errors": ["Unsupported publishing platform."]
        }

    config = limits[platform]
    result = inspect_media(
        video_path,
        max_size_mb=config["size"],
        max_duration_seconds=config["duration"]
    )
    result["platform"] = platform
    return result
