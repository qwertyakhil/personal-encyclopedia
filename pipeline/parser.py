"""
Inbox parser.
Reads each item in 00-Inbox and returns a structured InboxItem
so the rest of the pipeline knows what it's dealing with.

Three cases:
  1. .md with a bare URL  → fetch content from the URL
  2. .md with body content (web clipper) → content already here, skip fetch
  3. Non-.md file (PDF, DOCX, image, etc.) → pass to markitdown directly
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional
import frontmatter


# Source type detection patterns
YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
]
INSTAGRAM_PATTERNS = [
    r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w-]+",
]

# File types markitdown can handle directly
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".gif", ".webp"}

SourceType = Literal["youtube", "instagram", "article", "document", "clipped"]


@dataclass
class InboxItem:
    path: Path
    source_type: SourceType
    source_url: Optional[str]      # URL to fetch (None for clipped/document)
    existing_content: Optional[str]  # Already-fetched content (web clipper notes)
    title: Optional[str]            # From frontmatter if present


def parse_inbox_item(path: Path) -> Optional[InboxItem]:
    """
    Parse a single inbox item and return an InboxItem.
    Returns None if the file should be skipped (unsupported type, already processed, etc.)
    """
    suffix = path.suffix.lower()

    # Case 3: non-.md file — pass to markitdown
    if suffix in DOCUMENT_EXTENSIONS:
        return InboxItem(
            path=path,
            source_type="document",
            source_url=None,
            existing_content=None,
            title=path.stem,
        )

    if suffix != ".md":
        return None  # unsupported — skip silently

    # Parse frontmatter + body
    post = frontmatter.load(str(path))
    body = post.content.strip()
    fm = post.metadata

    # Skip if already processed
    if fm.get("status") == "compiled":
        return None

    # Extract URL from frontmatter or body
    url = fm.get("source_url") or _extract_url(body)

    if url:
        source_type = _detect_source_type(url)
        return InboxItem(
            path=path,
            source_type=source_type,
            source_url=_expand_short_url(url),
            existing_content=None,
            title=fm.get("title") or None,
        )

    # Case 2: no URL but has body content → web clipper note
    if len(body) > 100:
        return InboxItem(
            path=path,
            source_type="clipped",
            source_url=fm.get("source_url"),
            existing_content=body,
            title=fm.get("title") or path.stem,
        )

    # Empty or unrecognisable note — skip
    return None


def _extract_url(text: str) -> Optional[str]:
    """Pull the first HTTP/HTTPS URL out of a block of text."""
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(".,)>") if match else None


def _detect_source_type(url: str) -> SourceType:
    for pattern in YOUTUBE_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return "youtube"
    for pattern in INSTAGRAM_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return "instagram"
    return "article"


def _expand_short_url(url: str) -> str:
    """Expand youtu.be short URLs to full youtube.com URLs."""
    match = re.match(r"(?:https?://)?(?:www\.)?youtu\.be/([\w-]+)", url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url
