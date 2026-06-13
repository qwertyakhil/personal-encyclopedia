"""
Knowledge Pipeline — core schema and constants.
Every stage imports from here. Do not change the schema without updating all stages.
"""

from dataclasses import dataclass, field
from typing import Literal, List
from datetime import date


SourceType = Literal["youtube", "instagram", "article", "document", "clipped"]
Bucket = Literal["news", "tools", "build", "research", "strategy", "craft", "interview", "_unsorted"]
Status = Literal["raw", "compiled"]

BUCKETS = ["news", "tools", "build", "research", "strategy", "craft", "interview"]
DOMAINS = ["ai-tech", "web-dev", "data", "business", "design", "career", "_unsorted"]


@dataclass
class NoteSchema:
    """Frontmatter schema — the data contract for every note in the pipeline."""
    title: str = ""
    source_url: str = ""
    source_type: SourceType = "article"
    captured: str = field(default_factory=lambda: str(date.today()))
    domain: str = "_unsorted"      # LLM-determined — never hardcoded at note creation
    channel: str = ""              # YouTube channel name; empty for non-YouTube sources
    bucket: Bucket = "_unsorted"
    tags: List[str] = field(default_factory=list)
    status: Status = "raw"
    summary: str = ""

    def to_frontmatter(self) -> dict:
        fm = {
            "title": self.title,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "captured": self.captured,
            "domain": self.domain,
            "bucket": self.bucket,
            "tags": self.tags,
            "status": self.status,
            "summary": self.summary,
        }
        # Only include channel if it has a value — keeps frontmatter clean for articles
        if self.channel:
            fm["channel"] = self.channel
        return fm
