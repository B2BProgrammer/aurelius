"""
Prints a short-lived login token (JWT) for local testing.

Usage (from the orchestrator folder, with the venv active):
    python scripts/make_dev_token.py                # advisor "dev-advisor", 60 minutes
    python scripts/make_dev_token.py alice 120      # custom user and minutes

In production the company's identity provider (SSO) issues these tokens.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config import get_settings  # noqa: E402
from security.auth import create_token  # noqa: E402

user = sys.argv[1] if len(sys.argv) > 1 else "dev-advisor"
minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 60
print(create_token(get_settings(), user, minutes))
