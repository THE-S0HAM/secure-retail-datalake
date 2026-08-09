"""Create a timestamped PostgreSQL backup with pg_dump."""
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BACKUPS_DIR = Path(__file__).resolve().parent / "backups"


def backup_database():
    previous_umask = os.umask(0o077)
    output = None
    try:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        output = BACKUPS_DIR / f"secure_retail_backup_{timestamp}.sql"
        command = [
            "pg_dump", "-h", os.environ["DB_HOST"], "-p", os.getenv("DB_PORT", "5432"),
            "-U", os.environ["DB_USER"], "-d", os.environ["DB_NAME"], "-f", str(output),
        ]
        environment = os.environ.copy()
        environment["PGPASSWORD"] = os.environ["DB_PASSWORD"]
        subprocess.run(command, check=True, env=environment)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("pg_dump created an empty backup")
    except Exception:
        if output:
            output.unlink(missing_ok=True)
        raise
    finally:
        os.umask(previous_umask)
    print(f"Backup created: {output}")
    return output


if __name__ == "__main__":
    try:
        backup_database()
    except Exception as error:
        print(f"Backup failed: {error}")
        raise SystemExit(1)
