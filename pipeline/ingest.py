"""
Ingest stage.
Takes an InboxItem and returns (raw_content, metadata) where:
  - raw_content: transcript/article text as a string
  - metadata: dict with optional keys: title, channel

Each source type has its own handler.
"""

import json
import urllib.request
from pathlib import Path
from pipeline.parser import InboxItem


def ingest(item: InboxItem) -> tuple[str, dict]:
    """
    Dispatch to the right ingest handler based on source_type.
    Returns (content: str, metadata: dict).
    metadata may contain: title, channel
    """
    if item.source_type == "youtube":
        return _ingest_youtube(item.source_url)
    elif item.source_type == "instagram":
        raise NotImplementedError("Instagram ingest — Phase 2")
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
    No API key needed. Returns dict with 'title' and 'channel'.
    Falls back to empty dict on any failure.

    Works for both capture methods:
    - Phone share (bare URL note — no frontmatter title, oEmbed is the only source)
    - Web Clipper (title already in frontmatter — this is a fallback/verification)
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
    Fetch YouTube transcript via youtube-transcript-api.
    Also fetches video title + channel via oEmbed (free, no API key).

    Priority: English captions → translate any available language to English.
    Always returns English text — Hindi/Hinglish is translated at fetch time.

    Returns (transcript_text, metadata_dict).
    """
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    import re

    # Extract video ID — handles watch?v=, youtu.be/, live/, shorts/, embed/
    match = re.search(r"(?:v=|youtu\.be/|live/|shorts/|embed/)([\w-]+)", url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    video_id = match.group(1)

    # Fetch metadata (title, channel) — best effort, never blocks ingest
    metadata = _fetch_youtube_metadata(url)

    api = YouTubeTranscriptApi()

    # Try English captions first (manual or auto-generated)
    try:
        segments = api.fetch(video_id, languages=["en"])
        text = " ".join(seg.text for seg in segments)
        return text.strip(), metadata
    except NoTranscriptFound:
        pass

    # No English captions — find any available transcript and translate to English
    try:
        transcript_list = api.list(video_id)
        available = list(transcript_list)
        if not available:
            raise NoTranscriptFound(video_id, [], [])

        transcript = available[0]
        segments = transcript.translate("en").fetch()
        text = " ".join(seg.text for seg in segments)
        return text.strip(), metadata

    except (NoTranscriptFound, TranscriptsDisabled) as e:
        raise e


# ── Articles ───────────────────────────────────────────────────────────────────

def _ingest_article_url(url: str) -> str:
    """
    Fetch and convert a web article to markdown using markitdown.
    """
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(url)
    return result.text_content.strip()


def _ingest_document(path: Path) -> str:
    """
    Convert a local document (PDF, DOCX, image, etc.) to markdown using markitdown.
    """
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(path))
    return result.text_content.strip()
