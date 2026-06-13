"""
Phase 1: Ingest
Fetches content from a source URL and returns a raw transcript/text.
Populated per source type as phases are built out.
"""

# Phase 1 — youtube-transcript-api
# Phase 2 — yt-dlp + faster-whisper


def ingest(source_url: str, source_type: str) -> str:
    """
    Dispatch to the right ingest handler based on source_type.
    Returns raw transcript text.
    """
    if source_type == "youtube":
        return _ingest_youtube(source_url)
    elif source_type == "instagram":
        return _ingest_instagram(source_url)
    else:
        raise NotImplementedError(f"Ingest not yet implemented for: {source_type}")


def _ingest_youtube(url: str) -> str:
    # TODO Phase 1: use youtube-transcript-api
    raise NotImplementedError("YouTube ingest — Phase 1")


def _ingest_instagram(url: str) -> str:
    # TODO Phase 2: yt-dlp → faster-whisper
    raise NotImplementedError("Instagram ingest — Phase 2")
