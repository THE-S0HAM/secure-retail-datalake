"""Shared configuration and filesystem helpers."""
from datetime import datetime
from pathlib import Path
import logging
import os
from sqlalchemy.engine import URL
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
DATA_DIR = ROOT_DIR / "data"
RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR = [DATA_DIR / name for name in ("raw", "bronze", "silver", "gold")]
REPORTS_DIR = ROOT_DIR / "reports"
LOGS_DIR = ROOT_DIR / "logs"
BACKUPS_DIR = ROOT_DIR / "backups"
MASTER_DATA_DIR = ROOT_DIR / "master_data"


def ensure_directories():
    for directory in [RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, REPORTS_DIR, LOGS_DIR, BACKUPS_DIR, MASTER_DATA_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def get_run_id():
    return "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def get_count(name, default):
    return int(os.getenv(name, default))


def configure_logging():
    ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(LOGS_DIR / "pipeline.log"), logging.StreamHandler()],
        force=True,
    )
    return logging.getLogger("secure_retail")


def db_url():
    """Build a PostgreSQL URL without exposing special characters in credentials."""
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    )
