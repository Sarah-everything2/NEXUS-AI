"""NEXUS YouTube discovery and transcript adapter. TESTING ONLY."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TESTING_MODE = True

def _run(args, timeout=45):
    return subprocess.run(
        [sys.executable, "-m", "yt_dlp", *args],
        capture_output=True, text=True, timeout=timeout,
        check=False, encoding="utf-8", errors="replace"
    )

def search_youtube(query, limit=5):
    query = str(query).strip()[:200]
    if not query:
        return []
    limit = max(1, min(int(limit), 10))
    result = _run([
        "--flat-playlist", "--dump-single-json", "--no-warnings",
        "--no-call-home", f"ytsearch{limit}:{query}"
    ])
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
        entries = data.get("entries") or []
    except (json.JSONDecodeError, AttributeError):
        return []
    videos = []
    for item in entries:
        if not item:
            continue
        video_id = item.get("id")
        if not video_id:
            continue
        videos.append({
            "platform": "youtube",
            "video_id": video_id,
            "title": item.get("title", ""),
            "channel": item.get("channel") or item.get("uploader", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "views": item.get("view_count") or 0,
            "duration": item.get("duration"),
            "upload_date": item.get("upload_date"),
            "description": item.get("description", "")
        })
    return videos

def fetch_transcript(url, language="en"):
    if not re.match(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", str(url)):
        raise ValueError("Only YouTube URLs are supported.")
    with tempfile.TemporaryDirectory(prefix="nexus-captions-") as folder:
        output = str(Path(folder) / "caption.%(ext)s")
        result = _run([
            "--skip-download", "--write-auto-subs", "--write-subs",
            "--sub-langs", language, "--sub-format", "vtt",
            "--no-warnings", "--no-call-home", "-o", output, url
        ], timeout=60)
        files = list(Path(folder).glob("caption*.vtt"))
        if not files:
            return {"ok": False, "transcript": "", "error": result.stderr[-500:]}
        content = files[0].read_text(encoding="utf-8", errors="replace")
        lines = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
                continue
            line = re.sub(r"<[^>]+>", "", line)
            if line and (not lines or line != lines[-1]):
                lines.append(line)
        return {"ok": bool(lines), "transcript": " ".join(lines), "language": language}
