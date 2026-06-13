"""
Phase 1: Categorize
Sends transcript to Ollama (gemma4:31b-cloud) and returns domain, bucket, tags, and summary.

Transcript handling:
- Up to 150,000 chars (~3hr video, ~37K tokens): sent in one shot.
- Above 150,000 chars: map-reduce — chunk → summarize each → categorize combined summary.
"""

import json
import urllib.request
from pipeline import NoteSchema, BUCKETS, DOMAINS

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:31b-cloud"

SINGLE_PASS_CHAR_LIMIT = 150_000
CHUNK_SIZE = 30_000

# ── Prompt ─────────────────────────────────────────────────────────────────────

CATEGORIZE_PROMPT = """You are a knowledge categorizer for a personal knowledge base.

Given a transcript or article, return JSON with: domain, bucket, tags (4-6), summary.

━━━ DOMAIN — pick ONE based on intended use ━━━
Ask: "How will I use this information?" Pick based on primary reference value.

- ai-tech    → AI models, LLMs, agents, ML, developer tools, software engineering, coding culture.
              Use when you'd reference it for technical/AI work.
- web-dev    → Frontend, backend, APIs, databases, DevOps, web frameworks, software architecture.
              Use when you'd reference it for software development work.
- data       → Data engineering, analytics, SQL, data pipelines, visualization, BI.
              Use when you'd reference it for data work.
- business   → Startups, GTM, fundraising, product strategy, growth, marketing, market dynamics.
              Use when you'd reference it for business decisions.
- design     → UI/UX, design systems, user research, visual design, Figma, accessibility.
              Use when you'd reference it for design work.
- career     → Job search, personal growth, productivity, leadership, communication, learning.
              Use when you'd reference it for personal/professional development.
- _unsorted  → Genuinely spans multiple domains equally, or does not fit any above.

AMBIGUITY RULE: When content overlaps domains (e.g. "AI startup strategy"), pick based on
intended use — not subject matter. A video on AI fundraising goes to "business" if you'd
reference it for fundraising decisions, "ai-tech" if you'd reference it for AI product thinking.

━━━ BUCKET — pick ONE (same across all domains) ━━━
- news      → Releases, announcements, trends — skim to stay current
- tools     → Specific tools/services — reference when evaluating or using
- build     → How-tos, tutorials, implementation patterns — act on
- research  → Deep technical analysis, papers, benchmarks — study carefully
- strategy  → Frameworks, mental models, decision-making approaches — apply
- craft     → Evergreen skills, mindset, communication — absorb over time
- interview → Person-focused: founder stories, career journeys, conversations

━━━ TAGS (4-6) ━━━
Pick from the vocabulary for the detected domain. Prefer existing terms.
Add new hyphenated terms only if nothing in the vocabulary fits.
All tags must be lowercase and hyphenated (no spaces).

ai-tech vocabulary:
  llm, transformer, rag, fine-tuning, embeddings, vector-db, diffusion, multimodal,
  reasoning, inference, training, benchmark, evaluation, agents, multi-agent, mcp,
  agentic-workflow, tool-use, function-calling, vibe-coding, code-generation,
  prompt-engineering, context-window, retrieval, chunking, openai, anthropic,
  google-deepmind, meta-ai, mistral, claude, gpt, gemini, cursor, github-copilot,
  huggingface, ollama, langchain, gpu, quantization, distillation, computer-vision,
  speech-to-text, text-to-speech, open-source-models, safety, alignment

web-dev vocabulary:
  react, nextjs, typescript, tailwind, shadcn, nodejs, python, api, rest, graphql,
  websockets, sql, postgres, mongodb, redis, supabase, docker, kubernetes, vercel,
  serverless, edge, ci-cd, authentication, state-management, performance, testing,
  component-architecture, monorepo, micro-frontends, web-security, pwa

data vocabulary:
  pandas, spark, dbt, airflow, jupyter, bigquery, snowflake, redshift, etl,
  data-pipeline, analytics, visualization, streaming, data-quality, sql, python,
  feature-engineering, data-warehouse, lakehouse, real-time, batch-processing,
  data-governance, observability, tableau, looker

business vocabulary:
  gtm, growth, marketing, seo, content-marketing, sales, fundraising, revenue,
  pricing, unit-economics, saas-metrics, product-market-fit, positioning,
  competition, partnerships, hiring, team-building, culture, remote-work,
  b2b, b2c, marketplace, community, distribution, retention, churn

design vocabulary:
  ux, ui, design-system, user-research, wireframing, prototyping, figma, framer,
  webflow, typography, color, motion, accessibility, information-architecture,
  interaction-design, usability, design-tokens, responsive-design, mobile-design

career vocabulary:
  job-search, interviewing, resume, networking, personal-brand, learning,
  productivity, communication, leadership, management, mentoring, team-dynamics,
  salary-negotiation, remote-work, career-change, side-project, solopreneur

━━━ SUMMARY ━━━
2-3 sentences capturing the core insight and why it matters.

━━━ TITLE ━━━
If the content has no clear title (e.g. Instagram reel, podcast, video without caption),
generate a concise descriptive title (5-10 words, title case). If a title is obvious from
the content, use it. Otherwise leave as empty string.

━━━ OUTPUT FORMAT ━━━
Return ONLY valid JSON, no explanation:
{
  "title": "...",
  "domain": "...",
  "bucket": "...",
  "tags": ["...", "...", "...", "..."],
  "summary": "..."
}"""

CHUNK_SUMMARIZE_PROMPT = """Summarize the key topics and insights from this transcript section in 4-5 sentences. Be concise and factual.

Section:
{chunk}

Return only the summary text, no JSON."""


# ── Ollama helpers ─────────────────────────────────────────────────────────────

def _ollama(prompt: str, timeout: int = 180) -> str:
    """Send a prompt to Ollama and return the response string."""
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

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())

    return result.get("response", "").strip()


def _parse_json_response(raw: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _map_reduce(transcript: str) -> str:
    """
    For very long transcripts (>150K chars): split into chunks, summarize each,
    return combined summary for final categorization pass.
    """
    chunks = [transcript[i:i + CHUNK_SIZE] for i in range(0, len(transcript), CHUNK_SIZE)]
    chunk_summaries = []

    for i, chunk in enumerate(chunks):
        prompt = CHUNK_SUMMARIZE_PROMPT.format(chunk=chunk)
        summary = _ollama(prompt, timeout=120)
        chunk_summaries.append(f"[Section {i + 1}]\n{summary}")

    return "\n\n".join(chunk_summaries)


def _clean_tags(tags: list) -> list:
    """
    Normalize tags for Obsidian:
    - lowercase
    - replace spaces with hyphens
    - strip special characters (keep alphanumeric, hyphens, underscores)
    """
    cleaned = []
    for tag in tags:
        tag = tag.lower().strip().replace(" ", "-")
        tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_"))
        if tag:
            cleaned.append(tag)
    return cleaned


# ── Main ───────────────────────────────────────────────────────────────────────

def categorize(note: NoteSchema, transcript: str) -> NoteSchema:
    """
    Calls Ollama to determine domain, bucket, tags, and summary.
    Handles transcripts of any length via map-reduce for very long content.
    Returns the updated NoteSchema.
    """
    # For very long transcripts, reduce via map-reduce first
    if len(transcript) > SINGLE_PASS_CHAR_LIMIT:
        content_for_llm = _map_reduce(transcript)
    else:
        content_for_llm = transcript

    prompt = f"{CATEGORIZE_PROMPT}\n\nTranscript:\n{content_for_llm}"
    raw = _ollama(prompt, timeout=180)
    parsed = _parse_json_response(raw)

    # Title — only fill if not already set (YouTube title comes from oEmbed)
    if not note.title:
        note.title = parsed.get("title", "").strip()

    # Domain — LLM-determined, validated against known list
    domain = parsed.get("domain", "_unsorted")
    note.domain = domain if domain in DOMAINS else "_unsorted"

    # Bucket — validated against known list
    bucket = parsed.get("bucket", "_unsorted")
    note.bucket = bucket if bucket in BUCKETS else "_unsorted"

    # Tags — cleaned and normalized
    note.tags = _clean_tags(parsed.get("tags", []))

    # Summary
    note.summary = parsed.get("summary", "")

    return note
