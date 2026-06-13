# knowledge-pipeline

Personal knowledge pipeline. Captures content (YouTube, Instagram, articles) → transcribes → categorizes → files into an Obsidian vault → compiles a wiki → NotebookLM podcast.

## Structure

```
pipeline/
  __init__.py     # NoteSchema dataclass — the data contract
  ingest.py       # fetch transcript/content from source URL
  categorize.py   # Ollama (gemma3:27b) → bucket + tags + summary
  file.py         # write note into vault bucket folder
config.yaml       # paths, model, thresholds
.env              # secrets (gitignored) — copy from .env.template
run.py            # entrypoint — launchd calls this nightly
requirements.txt  # deps per phase (uncomment as phases are built)
```

## Setup

```bash
cd ~/dev/knowledge-pipeline
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
```

## Run

```bash
python3.11 run.py
```

## Phases

- **Phase 0** — Foundation (this scaffold)
- **Phase 1** — YouTube path end-to-end
- **Phase 2** — Instagram path (yt-dlp + Whisper)
- **Phase 3** — Compile wiki (Claude Code headless)
- **Phase 4** — NotebookLM push + weekly podcast
- **Phase 5** — Watcher / RSS auto-feeds
- **Phase 6** — Lint & health-check
