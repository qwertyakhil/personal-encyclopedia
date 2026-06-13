"""
Phase 1: Categorize
Sends transcript to Ollama (gemma3:27b) and returns bucket, tags, and summary.
"""

import json
import urllib.request
from pipeline import NoteSchema, BUCKETS

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:27b"

SYSTEM_PROMPT = """You are a knowledge categorizer for a personal AI/tech knowledge base.

Given a transcript or article text, return a JSON object with:
- bucket: one of ["news", "tools", "build", "craft"]
  - news: releases, updates, trends — skim to stay current
  - tools: specific tools/services — reference you return to
  - build: project ideas, vibe-coding patterns, how-tos — act on
  - craft: PM thinking, shipping, solo-builder skills — evergreen
- tags: list of 3-6 lowercase keyword strings
- summary: 2-3 sentence summary of the key insight

Return only valid JSON. No explanation."""


def categorize(note: NoteSchema, transcript: str) -> NoteSchema:
    """
    Calls Ollama to fill in bucket, tags, and summary on the note.
    Returns the updated NoteSchema.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nTranscript:\n{transcript[:6000]}"

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())

    raw = result.get("response", "")

    # Strip markdown code fences if present
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    parsed = json.loads(raw.strip())

    note.bucket = parsed.get("bucket", "_unsorted")
    if note.bucket not in BUCKETS:
        note.bucket = "_unsorted"
    note.tags = parsed.get("tags", [])
    note.summary = parsed.get("summary", "")

    return note
