"""
Ingest stage.
Takes an InboxItem and returns (raw_content, metadata) where:
  - raw_content: transcript/article text as a string (always English)
  - metadata: dict with optional keys: title, channel

Source routing:
  youtube   → youtube-transcript-api (captions) → yt-dlp + Whisper fallback
  instagram → yt-dlp + Whisper
  article   → markitdown (URL fetch)
  document  → markitdown (local file)
  clipped   → pass-through (content already in note)
"""

import json
import logging
import tempfile
import urllib.request
from pathlib import Path

from pipeline.parser import InboxItem

log = logging.getLogger(__name__)

# ── Whisper model singleton ────────────────────────────────────────────────────
# Loaded once on first use, reused for all transcriptions in a pipeline run.
# large-v3: most accurate, ~3GB RAM, ~1.5B params. Worth it for a nightly batch.
_whisper_model = None

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        log.info("Loading Whisper large-v3 model (first run may take a moment)...")
        _whisper_model = WhisperModel("large-v3", device="cpu", compute_type="int8")
        log.info("Whisper model loaded.")
    return _whisper_model


# ── Dispatcher ─────────────────────────────────────────────────────────────────

def ingest(item: InboxItem) -> tuple[str, dict]:
    """
    Dispatch to the right ingest handler based on source_type.
    Returns (content: str, metadata: dict).
    metadata may contain: title, channel
    """
    if item.source_type == "youtube":
        return _ingest_youtube(item.source_url)
    elif item.source_type == "instagram":
        return _ingest_instagram(item.source_url)
    elif item.source_type == "article":
        return _ingest_article_url(item.source_url), {}
    elif item.source_type == "document":
        return _ingest_document(item.path), {}
    elif item.source_type == "clipped":
        return item.existing_content, {}
    else:
        raise ValueError(f"Unknown source type: {item.source_type}")


# ── YouTube ────────────────────────────────────────────────────────────────────

def _fetch_youtube_metadata(url: str) -> dict:
    """
    Fetch video title and channel name via YouTube's free oEmbed API.
    No API key needed. Falls back to empty dict on any failure.
    Works for both phone share (no frontmatter title) and Web Clipper (title already set).
    """
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return {
            "title": data.get("title", ""),
            "channel": data.get("author_name", ""),
        }
    except Exception:
        return {}


def _ingest_youtube(url: str) -> tuple[str, dict]:
    """
    YouTube ingest with two-stage fallback:
      1. youtube-transcript-api: captions (instant, no download)
         - English captions → use directly
         - Non-English captions → translate to English via YouTube API
      2. yt-dlp + Whisper: audio transcription (when captions unavailable)
         - Handles live streams, creators who disable captions, any language

    Always returns English text.
    """
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    import re

    match = re.search(r"(?:v=|youtu\.be/|live/|shorts/|embed/)([\w-]+)", url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    video_id = match.group(1)

    # Fetch metadata (title, channel) — best effort, never blocks ingest
    metadata = _fetch_youtube_metadata(url)

    api = YouTubeTranscriptApi()

    # Stage 1a: English captions
    try:
        segments = api.fetch(video_id, languages=["en"])
        text = " ".join(seg.text for seg in segments)
        log.info("  Transcript source: YouTube captions (English)")
        return text.strip(), metadata
    except NoTranscriptFound:
        pass

    # Stage 1b: Non-English captions → translate to English
    try:
        transcript_list = api.list(video_id)
        available = list(transcript_list)
        if available:
            segments = available[0].translate("en").fetch()
            text = " ".join(seg.text for seg in segments)
            log.info(f"  Transcript source: YouTube captions (translated from {available[0].language_code})")
            return text.strip(), metadata
    except (NoTranscriptFound, TranscriptsDisabled):
        pass

    # Stage 2: No captions at all → yt-dlp audio download + Whisper transcription
    log.info("  No captions found — falling back to yt-dlp + Whisper")
    transcript, ydl_info = _audio_to_transcript(url)
    description = ydl_info.get("description", "").strip()
    content = f"[Description]\n{description}\n\n[Transcript]\n{transcript}" if description else transcript
    return content, metadata


# ── Instagram ──────────────────────────────────────────────────────────────────

def _ingest_instagram(url: str) -> tuple[str, dict]:
    """
    Instagram reels/posts: yt-dlp downloads audio, Whisper transcribes.
    Also captures caption/description from the post.
    Returns (caption + transcript, metadata).
    """
    log.info("  Instagram: downloading audio via yt-dlp")
    transcript, ydl_info = _audio_to_transcript(url)

    description = ydl_info.get("description", "").strip()
    content = f"[Caption]\n{description}\n\n[Transcript]\n{transcript}" if description else transcript

    metadata = {
        "title": ydl_info.get("title", ""),
        "channel": ydl_info.get("uploader", "") or ydl_info.get("channel", ""),
    }
    return content, metadata


# ── Shared: audio download + transcription ─────────────────────────────────────

def _audio_to_transcript(url: str) -> tuple[str, dict]:
    """
    Download audio from any yt-dlp-supported URL and transcribe with Whisper large-v3.

    Steps:
      1. Extract metadata (title, description, uploader) without downloading
      2. Download audio to temp dir
      3. Transcribe — auto-translate non-English to English
      4. Clean up temp files

    Returns (transcript, ydl_info_dict).
    ydl_info contains: title, description, uploader, channel, etc.

    Free, local, no usage limits. Requires: yt-dlp, faster-whisper, ffmpeg.
    """
    import yt_dlp
    import os

    # Step 1: Extract metadata only (no download)
    ydl_info = {}
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            ydl_info = {
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "uploader": info.get("uploader", ""),
                "channel": info.get("channel", ""),
            }
            if ydl_info["description"]:
                log.info(f"  Description fetched ({len(ydl_info['description'])} chars)")
    except Exception as e:
        log.warning(f"  Could not fetch metadata: {e}")

    # Step 2: Download audio + transcribe
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",   # mono speech — 64kbps is plenty
            }],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_file = audio_path + ".mp3"
        if not os.path.exists(audio_file):
            # yt-dlp may use a different extension — find whatever was created
            files = [f for f in os.listdir(tmpdir) if f.startswith("audio")]
            if not files:
                raise RuntimeError(f"yt-dlp produced no audio file for: {url}")
            audio_file = os.path.join(tmpdir, files[0])

        # Step 3: Transcribe
        model = _get_whisper_model()

        segments, info = model.transcribe(audio_file, beam_size=5)
        detected_lang = info.language
        log.info(f"  Whisper detected language: {detected_lang}")

        if detected_lang == "en":
            text = " ".join(seg.text for seg in segments)
        else:
            log.info(f"  Translating {detected_lang} → English via Whisper")
            segments, _ = model.transcribe(audio_file, task="translate", beam_size=5)
            text = " ".join(seg.text for seg in segments)

        return text.strip(), ydl_info


# ── Articles ───────────────────────────────────────────────────────────────────

def _ingest_article_url(url: str) -> str:
    """Fetch and convert a web article to markdown using markitdown."""
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(url)
    return result.text_content.strip()


def _ingest_document(path: Path) -> str:
    """Convert a local document (PDF, DOCX, image, etc.) to markdown using markitdown."""
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(path))
    return result.text_content.strip()
