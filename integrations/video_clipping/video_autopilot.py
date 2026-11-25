import json
import time
import inspect
import hashlib
import traceback
from pathlib import Path

from integrations.video_clipping import engine
from integrations.video_clipping import video_enhancements
from integrations.video_clipping import job_manager


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "workspace" / "video_output"
TRANSCRIPTS = OUTPUT / "transcripts"
SHORTS = OUTPUT / "shorts"
METADATA = OUTPUT / "metadata"

for folder in (OUTPUT, TRANSCRIPTS, SHORTS, METADATA):
    folder.mkdir(parents=True, exist_ok=True)


def _call_adaptively(function, values):
    signature = inspect.signature(function)
    kwargs = {}

    for name, parameter in signature.parameters.items():
        if name in values:
            kwargs[name] = values[name]
        elif parameter.default is inspect.Parameter.empty:
            raise RuntimeError(
                f"Unsupported required engine parameter: {name}"
            )

    return function(**kwargs)


def _segments_from_transcription(result):
    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        for key in ("segments", "results", "transcription"):
            value = result.get(key)
            if isinstance(value, list):
                return value

    raise ValueError("Whisper returned no usable transcript segments")


def _normalize_highlights(items):
    normalized = []

    if not isinstance(items, list):
        return normalized

    for item in items:
        if not isinstance(item, dict):
            continue

        try:
            start = float(item.get("start", item.get("start_seconds")))
            end = float(item.get("end", item.get("end_seconds")))

            if end <= start or start < 0:
                continue

            normalized.append({
                "start": start,
                "end": end,
                "duration": end - start,
                "score": float(item.get("score", item.get("rank", 0))),
                "text": str(item.get("text", item.get("reason", "")))[:1000]
            })
        except (TypeError, ValueError):
            continue

    return normalized


def process_job(job):
    job_id = job["id"]
    source = Path(job["source"]).resolve()

    if not source.is_file():
        raise FileNotFoundError("Source video no longer exists")

    digest = hashlib.sha256(
        str(source).encode("utf-8") +
        str(source.stat().st_size).encode("ascii")
    ).hexdigest()[:16]

    metadata_path = METADATA / f"{job_id}.json"
    transcript_path = TRANSCRIPTS / f"{job_id}.json"

    duplicate = video_enhancements.find_duplicate(source)
    if duplicate["duplicate"]:
        raise RuntimeError("Duplicate source video detected")

    # Probe source video.
    probe = engine.probe_video(str(source))

    if not isinstance(probe, dict):
        raise ValueError("Video probe returned invalid metadata")

    duration = float(
        probe.get("duration", 0) if probe else 0
    )

    if duration <= 0:
        raise ValueError("Video duration is missing or invalid")

    # Transcribe with existing Whisper implementation.
    transcription = _call_adaptively(
        engine.transcribe_video,
        {
            "video_path": str(source),
            "input_path": str(source),
            "model_size": "base",
            "model": "base",
            "language": None
        }
    )

    segments = _segments_from_transcription(transcription)

    transcript_path.write_text(
        json.dumps({
            "job_id": job_id,
            "source": str(source),
            "segments": segments,
            "created_at": time.time()
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Rank highlights using existing engine.
    raw_highlights = engine.detect_highlights(segments, top_k=10)
    highlights = _normalize_highlights(raw_highlights)

    outputs = []

    for index, highlight in enumerate(highlights, start=1):
        start = max(0, highlight["start"])
        end = min(duration, highlight["end"])
        clip_duration = end - start

        if clip_duration < 3:
            continue

        clip_name = f"{job_id}_short_{index:02d}.mp4"
        clip_path = SHORTS / clip_name

        engine.create_vertical_short(
            str(source),
            start,
            clip_duration,
            str(clip_path)
        )

        if not clip_path.is_file():
            continue

        caption_result = video_enhancements.create_captioned_clip(
            str(clip_path),
            segments,
            start,
            clip_duration,
            str(clip_path)
        )

        outputs.append({
            "video": caption_result.get("video", str(clip_path)),
            "subtitle": caption_result.get("subtitle"),
            "caption_status": caption_result.get("status"),
            "start": start,
            "duration": clip_duration,
            "score": highlight["score"],
            "text": highlight["text"],
            "platform_profiles": list(
                video_enhancements.PROFILES.keys()
            )
        })

    report = {
        "job_id": job_id,
        "source": str(source),
        "source_fingerprint": digest,
        "duration": duration,
        "transcript": str(transcript_path),
        "highlights_detected": len(highlights),
        "shorts_created": len(outputs),
        "outputs": outputs,
        "completed_at": time.time()
    }

    metadata_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    try:
        report["manifest"] = video_enhancements.build_manifest(
            job_id, source, segments, outputs
        )
        video_enhancements.register_video(source, {
            "job_id": job_id,
            "duration": duration
        })
    except Exception as exc:
        report["manifest_error"] = type(exc).__name__

    return report


def process_next_job():
    job = job_manager.next_job()

    if not job:
        return {"status": "IDLE"}

    job_id = job["id"]
    job_manager.update_job(job_id, "PROCESSING")

    try:
        result = process_job(job)
        job_manager.update_job(job_id, "COMPLETED")
        return {"status": "COMPLETED", "result": result}

    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:250]}"
        job_manager.update_job(job_id, "FAILED", error=error)
        return {
            "status": "FAILED",
            "job_id": job_id,
            "error": error
        }


def process_queue(max_jobs=1):
    results = []

    for _ in range(max(1, min(int(max_jobs), 3))):
        result = process_next_job()
        if result["status"] == "IDLE":
            break
        results.append(result)

    return results
