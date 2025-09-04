# src/config/env_loader.py
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # repo root

# 1) Load .env for defaults
load_dotenv(ROOT / ".env", override=False)

# 2) Only load env.local in *development* (never in production), even if the file exists.
if (
    os.getenv("IGNORE_ENV_LOCAL", "0") != "1"
    and os.getenv("FLASK_ENV", "development") == "development"
    and (ROOT / "env.local").exists()
):
    load_dotenv(ROOT / "env.local", override=True)

# Optional explicit override: ENV_FILE=.env.something
if os.getenv("ENV_FILE"):
    load_dotenv(ROOT / os.environ["ENV_FILE"], override=True)
