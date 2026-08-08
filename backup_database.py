"""Create a timestamped PostgreSQL dump with pg_dump."""
import os
import subprocess
import sys
from datetime import datetime
from config.settings import BACKUPS_DIR, ensure_directories


def backup_database():
    ensure_directories()
    filename = BACKUPS_DIR / f"secure_retail_backup_{datetime.now():%Y%m%d_%H%M%S}.sql"
    command = ["pg_dump", "-h", os.getenv("DB_HOST", "localhost"), "-p", os.getenv("DB_PORT", "5432"), "-U", os.getenv("DB_USER", "postgres"), "-d", os.getenv("DB_NAME", "secure_retail_lakehouse"), "-f", str(filename)]
    environment = os.environ.copy()
    environment["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")
    subprocess.run(command, check=True, env=environment)
    print(f"Backup created: {filename}")


if __name__ == "__main__":
    try: backup_database()
    except Exception as error:
        print(f"Backup failed: {error}")
        sys.exit(1)
