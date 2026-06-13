"""
Knowledge Pipeline — entrypoint.
launchd calls this nightly. Scans inbox, processes each note end-to-end.
"""

import os
import sys
import logging
from pathlib import Path
import yaml

# Ensure iCloud inbox files are downloaded before processing
def _brctl_download(path: str):
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

    # Safety net: force iCloud to download any placeholder files
    _brctl_download(str(inbox))

    inbox_notes = list(inbox.glob("*.md"))
    log.info(f"Found {len(inbox_notes)} note(s) in inbox")

    for note_path in inbox_notes:
        log.info(f"Processing: {note_path.name}")
        try:
            _process_note(note_path, vault_root, cfg, log)
        except Exception as e:
            log.error(f"Failed: {note_path.name} — {e}")

    log.info("Pipeline run complete")


def _process_note(note_path: Path, vault_root: Path, cfg: dict, log):
    # Stub — Phase 1 will fill this in
    # 1. Parse frontmatter to get source_url + source_type
    # 2. ingest.ingest(source_url, source_type) → transcript
    # 3. categorize.categorize(note, transcript) → filled note
    # 4. file.file_note(note, transcript, vault_root) → filed path
    # 5. Delete original from inbox
    log.info(f"  [stub] would process {note_path.name}")


if __name__ == "__main__":
    main()
