"""
Ingest stage.
Takes an InboxItem and returns raw transcript/content as a string.
Each source type has its own handler.
"""

from pathlib import Path
from pipeline.parser import InboxItem


def ingest(item: InboxItem) -> str:
    """
    Dispatch to the right ingest handler based on source_type.
    Returns raw content as a string.
    """
    if item.source_type == "youtube":
        return _ingest_youtube(item.source_url)
    elif item.source_type == "instagram":
        raise NotImplementedError("Instagram ingest — Phase 2")
    elif item.source_type == "article":
        return _ingest_article_url(item.source_url)
    elif item.source_type == "document":
        return _ingest_document(item.path)
    elif item.source_type == "clipped":
        return item.existing_content  # already markdown, nothing to fetch
    else:
        raise ValueError(f"Unknown source type: {item.source_type}")


# ── YouTube ────────────────────────────────────────────────────────────────────

def _ingest_youtube(url: str) -> str:
    """
    Fetch YouTube transcript via youtube-transcript-api.
    Priority: English captions → any available.
    Returns clean transcript text (no timestamps).
    """
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    import re

    # Extract video ID — handles watch?v=, youtu.be/, live/, shorts/, embed/
    match = re.search(r"(?:v=|youtu\.be/|live/|shorts/|embed/)([\w-]+)", url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    video_id = match.group(1)

    api = YouTubeTranscriptApi()

    # Try English first
    try:
        segments = api.fetch(video_id, languages=["en"])
    except NoTranscriptFound:
        try:
            # Fall back: try any available language
            transcripts = api.list(video_id)
            # Fetch the first available transcript
            segments = api.fetch(video_id)
        except (NoTranscriptFound, TranscriptsDisabled):
            raise NoTranscriptFound(video_id, [], [])

    text = " ".join(seg.text for seg in segments)
    return text.strip()


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
