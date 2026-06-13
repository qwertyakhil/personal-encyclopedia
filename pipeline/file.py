"""
Phase 1: File
Writes the processed note as a .md file into the correct vault bucket folder.
"""

import re
import yaml
from datetime import datetime
from pathlib import Path
from pipeline import NoteSchema


def file_note(note: NoteSchema, transcript: str, vault_root: str) -> Path:
    """
    Writes note to 10-Raw/ai/<bucket>/<slug>.md inside the vault.
    Returns the path of the written file.
    """
    bucket_dir = Path(vault_root) / "10-Raw" / note.domain / note.bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)

    slug = _make_slug(note)

    # Ensure uniqueness — if slug already exists, append a counter
    note_path = bucket_dir / f"{slug}.md"
    counter = 1
    while note_path.exists():
        note_path = bucket_dir / f"{slug}-{counter}.md"
        counter += 1

    frontmatter = yaml.dump(note.to_frontmatter(), allow_unicode=True, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n## Transcript\n\n{transcript}\n"

    note_path.write_text(content, encoding="utf-8")
    return note_path


def _make_slug(note: NoteSchema) -> str:
    """
    Build a meaningful, unique-enough slug from available metadata.
    Priority: title → URL-derived → date + source_type fallback.
    """
    # Use title if it's meaningful
    if note.title and len(note.title.strip()) > 3:
        return _slugify(note.title)[:60]

    # Derive from URL
    if note.source_url:
        url = note.source_url

        # YouTube: use video ID
        yt_match = re.search(r"(?:v=|live/|shorts/|embed/|youtu\.be/)([\w-]+)", url)
        if yt_match:
            return f"yt-{yt_match.group(1)}"

        # Instagram: use post ID
        ig_match = re.search(r"instagram\.com/(?:p|reel|tv)/([\w-]+)", url)
        if ig_match:
            return f"ig-{ig_match.group(1)}"

        # Generic URL: use domain + path slug
        domain_match = re.search(r"(?:https?://)?(?:www\.)?([^/]+)", url)
        if domain_match:
            domain = domain_match.group(1).replace(".", "-")
            return f"{domain[:30]}-{datetime.now().strftime('%Y%m%d')}"

    # Final fallback: source_type + date
    return f"{note.source_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)   # collapse multiple consecutive dashes
    return text.strip("-") or "note"
