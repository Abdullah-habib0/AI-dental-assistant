"""Loads the clinic's PDFs into the knowledge base: read, chunk, embed, store.

Run it from the backend folder, after adding or changing a PDF:

    python -m scripts.ingest_knowledge

Stop the web server first. Qdrant's local mode lets only one program use its folder at a
time, and the running server holds it.
"""

import sys
import time
from pathlib import Path

from app.core.config import settings
from app.features.knowledge.service import close_knowledge_base, get_knowledge_base


def main() -> None:
    pdfs = sorted(Path(settings.knowledge_dir).glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs found in {settings.knowledge_dir}")

    started = time.perf_counter()
    try:
        knowledge = get_knowledge_base()
    except RuntimeError as exc:
        if "already accessed" in str(exc):
            sys.exit("The Qdrant folder is in use - probably by the running web server. Stop it, then try again.")
        raise

    print(f"Embedding model: {settings.embedding_model}")
    try:
        per_file = knowledge.ingest(pdfs)
    finally:
        close_knowledge_base()
    for name, count in per_file.items():
        print(f"  {name:44} {count:3} chunks")
    print(f"  {'TOTAL':44} {sum(per_file.values()):3} chunks in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
