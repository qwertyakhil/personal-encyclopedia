"""
Phase 1: File
Writes the processed note as a .md file into the correct vault bucket folder.
"""

import os
import yaml
from pathlib import Path
from pipeline import NoteSchema


def file_note(note: NoteSchema, transcript: str, vault_root: str) -> Path:
    """
    Writes note to 10-Raw/ai/<bucket>/<slug>.md inside the vault.
    Returns the path of the written file.
    """
    bucket_dir = Path(vault_root) / "10-Raw" / note.domain / note.bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(note.title or note.source_url)
    note_path = bucket_dir / f"{slug}.md"

    frontmatter = yaml.dump(note.to_frontmatter(), allow_unicode=True, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n## Transcript\n\n{transcript}\n"

    note_path.write_text(content, encoding="utf-8")
    return note_path


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"https?://[^\s]+", "link", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:60].strip("-") or "note"
