"""
ENTRY POINT of the Librarian (knowledge-rag).

Run from the knowledge-rag folder (with its virtual environment active):
    python src\\main.py

What starts:
    main.py -> api/app.py (endpoints) -> rag/ (retrieve) + llm/answerer.py (answer)
On the first start the index is empty, so the docs folder is ingested
automatically (and the embedding model is downloaded once).
"""
from pathlib import Path

import uvicorn

from api.app import create_app
from core.config import get_settings
from core.log_setup import setup_logging


def build_app():
    setup_logging()
    return create_app()


if __name__ == "__main__":
    settings = get_settings()
    src_dir = Path(__file__).resolve().parent
    uvicorn.run(
        "main:build_app",
        factory=True,
        host="127.0.0.1",
        port=settings.port,  # 8001
        reload=True,
        app_dir=str(src_dir),
        reload_dirs=[str(src_dir)],
    )
