---
name: video_clipping
description: Automatically transform long videos into engaging short-form content.
---

# Video Clipping Skill

## Capabilities

1. Detect interesting moments using transcript analysis.
2. Extract selected video clips.
3. Transcribe audio using Whisper.
4. Generate subtitles in SRT, JSON and TXT formats.
5. Burn subtitles into videos.
6. Create vertical 9:16 videos (1080x1920).
7. Generate titles, descriptions and hashtags.
8. Prepare platform-specific content for TikTok, YouTube Shorts and Instagram Reels.
9. Organise finished videos.

## Integrations

- FFmpeg
- FFmpeg Whisper filter (whisper.cpp)
- Local AI transcription
- Speech recognition
- Social media integrations

## Available Tools

- `video_probe`
- `video_transcribe`
- `video_detect_highlights`
- `video_extract_clip`
- `video_create_vertical_short`
- `video_create_subtitles`
- `video_burn_subtitles`

## Autonomous Workflow

When autonomous mode is enabled:

1. Receive an authorised source video.
2. Inspect video metadata.
3. Transcribe audio when appropriate.
4. Analyse transcript segments.
5. Rank interesting moments.
6. Extract promising clips.
7. Create vertical Shorts.
8. Generate and burn subtitles.
9. Organise finished videos.
10. Prepare content for platform-specific publishing.

Autonomous production must use the configured permission manager.

## Whisper Transcription

- Tool: `video_transcribe`
- Engine: FFmpeg Whisper filter (whisper.cpp)
- Model: `models/whisper/ggml-tiny.bin`
- Processing: CPU-only
- Formats: SRT, JSON, TXT
- Language: auto or supported language codes
- Output directory: `workspace/video_clips/`

## Highlight Detection

- Tool: `video_detect_highlights`
- Input: timestamped transcript segments
- Ranking: engagement hooks, questions, numbers, emphasis and concise segments
- Output: ranked highlights with timestamps, scores and reasons.

## Video Export

- Engine: FFmpeg
- Standard clips: MP4
- Vertical format: 1080x1920
- Aspect ratio: 9:16
- Output directory: `workspace/video_clips/`

## Safety and Permissions

- Autonomous transcription, highlight detection, clipping and subtitle processing are permitted through the configured safe-tool permissions.
- Never overwrite original videos.
- Keep original source files safe.
- Respect copyright and creator permissions.
- Only process source material the user is authorised to use.
- Never publish publicly without explicit human approval.
- Never schedule public posts without approval.
- Private YouTube uploads are permitted only through the separately configured private-upload safeguards.
- Never bypass the NEXUS permission manager.
- Never manipulate views, engagement or platform metrics.
- Keep credentials and OAuth tokens secure.

## Operating Principle

NEXUS should be capable of producing and preparing content autonomously while the user is busy, without weakening safeguards around publishing, external actions or account security.
