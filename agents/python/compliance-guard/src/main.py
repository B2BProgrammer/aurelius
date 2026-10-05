"""
ENTRY POINT of Sentinel (compliance-guard).

Run from the compliance-guard folder (with its virtual environment active):
    python src\\main.py

What starts:
    main.py -> api/app.py (endpoints) -> guards/engine.py (the checks)
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
        port=settings.port,  # 8004
        reload=True,
        app_dir=str(src_dir),
        reload_dirs=[str(src_dir)],
    )
