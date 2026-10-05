"""
ENTRY POINT of the Conductor.

Run from the orchestrator folder (with the virtual environment active):
    python src/main.py

What starts:
    main.py  ->  api/app.py (endpoints)  ->  orchestration/pipeline.py (the 7 phases)
"""
from pathlib import Path

import uvicorn

from api.app import create_app
from core.config import get_settings
from core.log_setup import setup_logging


def build_app():
    """Builds the app with settings read from .env. uvicorn calls this."""
    setup_logging()
    return create_app()


if __name__ == "__main__":
    settings = get_settings()
    src_dir = Path(__file__).resolve().parent
    uvicorn.run(
        "main:build_app",
        factory=True,             # call build_app() to get the app
        host=settings.conductor_host,  # 127.0.0.1 = this computer only (CONDUCTOR_HOST in .env)
        port=settings.port,       # 8000
        reload=True,              # restart automatically when you save a file
        app_dir=str(src_dir),
        reload_dirs=[str(src_dir)],
    )
