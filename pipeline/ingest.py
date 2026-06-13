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
    Priority: English captions → translate any available language to English.
    Always returns English text — Hindi/Hinglish is translated at fetch time.
    """
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    import re

    # Extract video ID — handles watch?v=, youtu.be/, live/, shorts/, embed/
    match = re.search(r"(?:v=|youtu\.be/|live/|shorts/|embed/)([\w-]+)", url)
    if not match:
        raise ValueError(f"Could not extract video ID from URL: {url}")
    video_id = match.group(1)

    api = YouTubeTranscriptApi()

    # Try English captions first (manual or auto-generated)
    try:
        segments = api.fetch(video_id, languages=["en"])
        text = " ".join(seg.text for seg in segments)
        return text.strip()
    except NoTranscriptFound:
        pass

    # No English captions — find any available transcript and translate to English
    try:
        transcript_list = api.list(video_id)
        available = list(transcript_list)
        if not available:
            raise NoTranscriptFound(video_id, [], [])

        # Pick the first available transcript and translate to English
        transcript = available[0]
        segments = transcript.translate("en").fetch()
        text = " ".join(seg.text for seg in segments)
        return text.strip()

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
