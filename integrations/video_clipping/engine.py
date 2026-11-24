"""NEXUS AI lightweight FFmpeg video clipping engine."""
import json
import os
import shutil
import subprocess
from pathlib import Path

OUTPUT_DIR = Path("workspace/video_clips")


def _binary(name):
    found = shutil.which(name)
    if found:
        return found

    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
    if root.exists():
        for path in root.glob("Gyan.FFmpeg*/ffmpeg-*/bin/" + name + ".exe"):
            if path.is_file():
                return str(path)

    raise FileNotFoundError(
        f"{name} not found. Install FFmpeg and ensure its bin folder is available."
    )


def _run(command, cwd=None):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=cwd
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stdout


def _input_file(video_path):
    path = Path(video_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {path}")
    return path


def _output_file(output_path):
    path = Path(output_path).expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"Output already exists: {path}")
    if path.suffix.lower() != ".mp4":
        raise ValueError("Output must use the .mp4 extension.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def probe_video(video_path):
    source = _input_file(video_path)
    data = _run([
        _binary("ffprobe"), "-v", "error",
        "-show_format", "-show_streams",
        "-of", "json", str(source)
    ])
    metadata = json.loads(data)
    return {
        "file": str(source),
        "format": metadata.get("format", {}),
        "streams": metadata.get("streams", [])
    }


def extract_clip(video_path, start_seconds, duration_seconds, output_path):
    source = _input_file(video_path)
    start = float(start_seconds)
    duration = float(duration_seconds)

    if start < 0 or duration <= 0 or duration > 600:
        raise ValueError("Invalid clip timing. Duration must be between 0 and 600 seconds.")

    output = _output_file(output_path)
    if output == source:
        raise ValueError("Cannot overwrite the original video.")

    _run([
        _binary("ffmpeg"), "-hide_banner", "-y",
        "-ss", str(start), "-i", str(source),
        "-t", str(duration),
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-movflags", "+faststart",
        str(output)
    ])

    return {"created": True, "output": str(output), "type": "clip"}


def create_vertical_short(video_path, start_seconds, duration_seconds, output_path):
    source = _input_file(video_path)
    start = float(start_seconds)
    duration = float(duration_seconds)

    if start < 0 or duration <= 0 or duration > 180:
        raise ValueError("Short duration must be between 0 and 180 seconds.")

    output = _output_file(output_path)
    if output == source:
        raise ValueError("Cannot overwrite the original video.")

    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920"
    )

    _run([
        _binary("ffmpeg"), "-hide_banner", "-y",
        "-ss", str(start), "-i", str(source),
        "-t", str(duration),
        "-map", "0:v:0", "-map", "0:a?",
        "-vf", video_filter,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output)
    ])

    return {
        "created": True,
        "output": str(output),
        "resolution": "1080x1920",
        "type": "vertical_short"
    }


def create_subtitles(segments, output_path):
    """Create an SRT subtitle file from timestamped transcript segments."""
    if not isinstance(segments, list) or not segments:
        raise ValueError("A non-empty list of transcript segments is required.")

    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".srt":
        raise ValueError("Subtitle output must use the .srt extension.")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")

    def timestamp(seconds):
        milliseconds = round(float(seconds) * 1000)
        hours, remainder = divmod(milliseconds, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    entries = []
    previous_end = 0.0

    for index, segment in enumerate(segments, 1):
        if not isinstance(segment, dict):
            raise ValueError("Each segment must be a dictionary.")

        start = float(segment["start"])
        end = float(segment["end"])
        text = str(segment["text"]).strip()

        if start < 0 or end <= start or start < previous_end or not text:
            raise ValueError(f"Invalid subtitle segment at index {index - 1}.")

        entries.append(
            f"{index}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n"
        )
        previous_end = end

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(entries), encoding="utf-8-sig")
    return {"created": True, "output": str(output), "segments": len(entries)}


def burn_subtitles(video_path, subtitle_path, output_path):
    """Render SRT subtitles permanently into an MP4 video."""
    source = _input_file(video_path)
    subtitles = Path(subtitle_path).expanduser().resolve()

    if not subtitles.is_file() or subtitles.suffix.lower() != ".srt":
        raise ValueError("A valid SRT subtitle file is required.")

    if source == Path(output_path).expanduser().resolve():
        raise ValueError("Cannot overwrite the original video.")

    # Restrict the filter filename to avoid FFmpeg filter escaping issues.
    if not all(c.isalnum() or c in "._- " for c in subtitles.name):
        raise ValueError("Subtitle filename contains unsupported characters.")

    output = _output_file(output_path)
    if not all(c.isalnum() or c in "._-" for c in subtitles.name):
        raise ValueError("Subtitle filename must contain only letters, numbers, dots, underscores or hyphens.")

    filter_arg = f"subtitles=filename={subtitles.name}"

    _run([
        _binary("ffmpeg"), "-hide_banner", "-n",
        "-i", str(source),
        "-vf", filter_arg,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-movflags", "+faststart",
        str(output)
    ], cwd=str(subtitles.parent))

    return {
        "created": True,
        "output": str(output),
        "subtitles_burned": True
    }


def detect_highlights(segments, top_k=5):
    """Rank promising video moments from timestamped transcript segments."""
    if not isinstance(segments, list) or not segments:
        raise ValueError("A non-empty transcript is required.")

    if not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")

    hooks = {
        "secret", "revealed", "amazing", "shocking", "mistake",
        "important", "warning", "never", "truth", "surprising",
        "discover", "incredible", "danger", "best", "worst",
        "breakthrough", "finally", "why", "how"
    }

    ranked = []

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise ValueError("Each segment must be a dictionary.")

        start = float(segment["start"])
        end = float(segment["end"])
        content = str(segment["text"]).strip()

        if start < 0 or end <= start or not content:
            raise ValueError(f"Invalid transcript segment at index {index}.")

        words = content.split()
        lowered = content.lower()
        score = 0
        reasons = []

        matches = [word for word in hooks if word in lowered]
        if matches:
            score += min(3, len(matches))
            reasons.append("engagement_hook")

        if "?" in content:
            score += 2
            reasons.append("question")

        if any(char.isdigit() for char in content):
            score += 1
            reasons.append("contains_numbers")

        if "!" in content:
            score += 1
            reasons.append("emphasis")

        if 8 <= len(words) <= 35:
            score += 2
            reasons.append("concise_segment")

        if len(words) < 4:
            score -= 2

        ranked.append({
            "start": start,
            "end": end,
            "text": content,
            "score": score,
            "reasons": reasons
        })

    ranked.sort(key=lambda item: (-item["score"], item["start"]))

    return {
        "highlights": ranked[:top_k],
        "method": "lightweight_transcript_heuristics",
        "total_segments_analyzed": len(segments)
    }

def transcribe_video(
    video_path,
    output_path,
    language="auto",
    output_format=None,
    model_path="models/whisper/ggml-tiny.bin"
):
    """Transcribe video audio using FFmpeg Whisper on CPU."""

    source = _input_file(video_path)
    model = Path(model_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    root = Path.cwd().resolve()

    if not model.is_file():
        raise FileNotFoundError(f"Whisper model not found: {model}")

    if language not in {
        "auto", "en", "fr", "es", "de", "pt", "it",
        "ja", "ko", "zh", "ar", "hi", "yo"
    }:
        raise ValueError("Unsupported language code.")

    fmt = output_format or output.suffix.lower().lstrip(".")

    if fmt not in {"srt", "json", "text"}:
        raise ValueError("Output format must be srt, json, or text.")

    expected_suffix = ".txt" if fmt == "text" else f".{fmt}"
    if output.suffix.lower() != expected_suffix:
        raise ValueError(f"Output filename must end in {expected_suffix}.")

    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")

    try:
        model_arg = model.relative_to(root).as_posix()
        output_arg = output.relative_to(root).as_posix()
    except ValueError:
        raise ValueError("Model and output must be inside the NEXUS project folder.")

    if not all(c.isalnum() or c in "._/-" for c in model_arg):
        raise ValueError("Unsupported characters in model path.")

    if not all(c.isalnum() or c in "._/-" for c in output_arg):
        raise ValueError("Unsupported characters in output path.")

    output.parent.mkdir(parents=True, exist_ok=True)

    filter_arg = (
        f"whisper=model={model_arg}:"
        f"use_gpu=false:"
        f"language={language}:"
        f"destination={output_arg}:"
        f"format={fmt}"
    )

    try:
        _run([
            _binary("ffmpeg"), "-hide_banner", "-nostats",
            "-i", str(source),
            "-vn",
            "-af", filter_arg,
            "-f", "null", "NUL"
        ])
    except Exception:
        if output.exists():
            output.unlink()
        raise

    if not output.is_file():
        raise RuntimeError("Whisper completed without creating the transcript.")

    return {
        "created": True,
        "output": str(output),
        "format": fmt,
        "language": language,
        "model": str(model),
        "processing": "cpu"
    }

