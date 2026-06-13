"""
Knowledge Pipeline — entrypoint.
launchd calls this nightly. Scans inbox, processes each item end-to-end.
"""

import os
import sys
import logging
from pathlib import Path
import yaml

from pipeline.parser import parse_inbox_item
from pipeline.ingest import ingest
from pipeline.categorize import categorize
from pipeline.file import file_note
from pipeline import NoteSchema


def _brctl_download(path: str):
    """Force iCloud to download any placeholder files before we read them."""
    os.system(f'brctl download "{path}"')


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def setup_logging(vault_root: Path, log_file: str):
    log_path = vault_root / "90-System" / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    cfg = load_config()
    vault_root = Path(cfg["vault"]["root"]).expanduser()
    inbox = vault_root / cfg["vault"]["inbox"]

    setup_logging(vault_root, cfg["pipeline"]["log_file"])
    log = logging.getLogger(__name__)

    log.info("Pipeline run started")

    # Safety net: force iCloud to materialise any placeholder files
    _brctl_download(str(inbox))

    # Scan inbox for all items (.md notes + documents)
    inbox_items = list(inbox.glob("*.md")) + [
        p for p in inbox.iterdir()
        if p.suffix.lower() in {".pdf", ".docx", ".doc", ".pptx", ".jpg", ".jpeg", ".png"}
    ]
    log.info(f"Found {len(inbox_items)} item(s) in inbox")

    retry_queue = []

    for item_path in inbox_items:
        log.info(f"Processing: {item_path.name}")
        try:
            _process_item(item_path, vault_root, cfg, log)
        except NotImplementedError as e:
            log.warning(f"Skipped (not yet implemented): {item_path.name} — {e}")
        except Exception as e:
            log.error(f"Failed: {item_path.name} — {e}")
            retry_queue.append(item_path.name)

    if retry_queue:
        log.warning(f"Retry queue: {retry_queue}")

    log.info("Pipeline run complete")


def _process_item(item_path: Path, vault_root: Path, cfg: dict, log):
    # 1. Parse inbox item
    item = parse_inbox_item(item_path)
    if item is None:
        log.info(f"  Skipped (unrecognised or already processed): {item_path.name}")
        return

    log.info(f"  Type: {item.source_type} | URL: {item.source_url or '(none)'}")

    # 2. Ingest → raw content
    content = ingest(item)
    log.info(f"  Ingested {len(content)} chars")

    # 3. Build note skeleton from item
    note = NoteSchema(
        title=item.title or "",
        source_url=item.source_url or "",
        source_type=item.source_type if item.source_type in ("youtube", "instagram", "article", "document") else "article",
        domain=cfg["domain"]["default"],
    )

    # 4. Categorize → fills bucket, tags, summary
    note = categorize(note, content)
    log.info(f"  Categorized → bucket: {note.bucket} | tags: {note.tags}")

    # 5. File note into vault
    filed_path = file_note(note, content, str(vault_root))
    log.info(f"  Filed → {filed_path.relative_to(vault_root)}")

    # 6. Delete original from inbox
    item_path.unlink()
    log.info(f"  Deleted from inbox")


if __name__ == "__main__":
    main()
