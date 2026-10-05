"""
ENTRY POINT of the Analyst (portfolio-insights).

Start the MCP server FIRST (mcp-servers\\advisor-tools: python src\\main.py, port 8500),
then run from the portfolio-insights folder (venv active):
    python src\\main.py

What starts:
    main.py -> api/app.py -> mcp_client (tools via MCP) -> analysis/ (math) -> llm/ (words)
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
    uvicorn.run("main:build_app", factory=True, host="127.0.0.1", port=settings.port,  # 8002
                reload=True, app_dir=str(src_dir), reload_dirs=[str(src_dir)])
